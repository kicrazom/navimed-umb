#!/usr/bin/env bash
# NaviMed-UMB Phase 2 — Bielik v3.0 Instruct REFRESH re-run (OOM recovery).
#
# WHY THIS SCRIPT EXISTS
#   The 2026-06-06 Tier-A sweep recorded 0/180 ok for BOTH v3.0 Instruct
#   refresh variants. Root cause (confirmed from per-run bench.log):
#     ValueError: Free memory on device cuda:0 (3.15/31.86 GiB) on startup is
#     less than desired GPU memory utilization (0.9, 28.67 GiB).
#   i.e. another vLLM process held ~28 GiB at launch time (overlapping armed
#   chains collided on GPU0). NOT a chat-template bug — the engine never loaded.
#   GPU is clean now → a standalone, non-overlapping re-run recovers the cells.
#
# SCOPE — ONLY the two dead models (the other Tier-A models succeeded and are
# NOT touched here):
#   1. bielik-pl-11b-v30-instruct   (speakleash/Bielik-PL-11B-v3.0-Instruct, bf16)
#   2. bielik-11b-v30-instruct-awq  (speakleash/Bielik-11B-v3.0-Instruct, awq W4A16)
#
# Full canonical ladder in ONE pass (no chained sentinels): the union of what
# the Tier-A + n200 + high-N chains produced for the other Bielik models, so
# v3.0 is comparable within the Bielik family and at the cross-model points:
#   N = {5,10,25,50,100,200,250,500,1000}   (9 pts = METHODOLOGY n_planned=180/model)
#   TP = {1,2}   reps = 10
#
# Mirrors the proven run_bielik_tierA_n10_sweep.sh inner loop (bench_with_thermals.py
# resolves model path from the key; continue-on-fail; 30s cooldown). Writes to the
# SAME result dirs so finalize_phase2_generic.py regenerates phase2_sweep.csv,
# overwriting the failed OOM artefacts cell-for-cell.
#
# Embargo: EMBARGO_paper_bound (Polish model, METHODOLOGY §11.3).
#
# Usage from repo root (wrap in systemd-inhibit to survive idle-suspend):
#   systemd-inhibit --what=sleep:idle --who=navimed-bielik-v30-rerun \
#       --why="Bielik v3.0 refresh OOM re-run" --mode=block \
#       bash benchmarks/scripts/orchestrators/run_bielik_v30_refresh_rerun.sh

set -euo pipefail

# ===========================================================================
# Source the single canonical environment (METHODOLOGY §3.1)
# NB: $SCRIPT_DIR is CLOBBERED by `source _env.sh`. Capture $REPO_ROOT BEFORE
# the source; derive all sibling paths from it.
# ===========================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

# ===========================================================================
# Configuration
# ===========================================================================
MAX_LEN=8192
UTIL=0.90
N_LADDER=(5 10 25 50 100 200 250 500 1000)
TP_LADDER=(1 2)
REPS=10
COOLDOWN_S=30
PER_RUN_TIMEOUT_S=1800       # N=1000 reps are LONG; rc=124 caught, never kills sweep

# Parallel arrays — index-aligned (load-bearing). Key == result dir for both.
MODEL_KEYS=(
    "bielik-pl-11b-v30-instruct"
    "bielik-11b-v30-instruct-awq"
)
RESULT_DIRS=(
    "bielik-pl-11b-v30-instruct"
    "bielik-11b-v30-instruct-awq"
)
MODEL_QUANTS=(
    "bf16"
    "awq"
)
MODEL_PATHS=(
    "/home/mozarcik/models/bielik-pl-11b-v30-instruct"
    "/home/mozarcik/models/bielik-11b-v30-instruct-awq"
)
MODEL_HF_NAMES=(
    "speakleash/Bielik-PL-11B-v3.0-Instruct"
    "speakleash/Bielik-11B-v3.0-Instruct"
)

BENCH="$REPO_ROOT/benchmarks/scripts/instrumentation/bench_with_thermals.py"
FINALIZE="$REPO_ROOT/benchmarks/scripts/analysis/finalize_phase2_generic.py"

GLOBAL_LOG_DIR="$REPO_ROOT/benchmarks/results/_bielik_v30_refresh_rerun_logs"
ORCHESTRATOR_LOG="$GLOBAL_LOG_DIR/orchestrator.log"
PROGRESS_LOG="$GLOBAL_LOG_DIR/progress.log"
mkdir -p "$GLOBAL_LOG_DIR"

# ===========================================================================
# Pre-flight: models present; no stale vLLM for THESE keys (REFUSE — never pkill,
# per memory feedback_kill_isolation). Other sweeps must not overlap (the very
# bug we are recovering from).
# ===========================================================================
for mp in "${MODEL_PATHS[@]}"; do
    if [[ ! -d "$mp" ]]; then
        echo "ERROR: model not found at $mp" >&2
        exit 1
    fi
done

stale_pids="$(pgrep -af 'vllm serve|run_concurrent.py|bench_with_thermals.py' 2>/dev/null || true)"
if [[ -n "$stale_pids" ]]; then
    echo "ERROR: vllm/bench processes present — refusing to start (avoid GPU collision):" >&2
    echo "$stale_pids" >&2
    exit 1
fi

# ===========================================================================
# Embargo headers (per METHODOLOGY §11.4)
# ===========================================================================
write_embargo_header() {
    local f="$1"
    {
        echo "# EMBARGO=YES — paper-bound (Polish model, METHODOLOGY §11.3)"
        echo "# Sweep: Bielik v3.0 refresh re-run {pl-11b-v30-instruct bf16, 11b-v30-instruct-awq}"
        echo "# Ladder: TP={1,2}, N={5,10,25,50,100,200,250,500,1000}, reps=10"
        echo "# Started: $(date -Iseconds)"
        echo "# Operator: Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>"
        echo "# DO NOT COMMIT until paper acceptance."
        echo "#"
    } > "$f"
}
write_embargo_header "$PROGRESS_LOG"
write_embargo_header "$ORCHESTRATOR_LOG"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$ORCHESTRATOR_LOG"; }
progress() { echo "[$(date -Iseconds)] $*" >> "$PROGRESS_LOG"; }

# ===========================================================================
# vLLM version pin (per METHODOLOGY)
# ===========================================================================
python3 -c "import vllm; assert vllm.__version__.startswith('0.19.0'), f'WRONG vLLM: {vllm.__version__}'"
log "vLLM version OK: $(python3 -c 'import vllm; print(vllm.__version__)')"

# ===========================================================================
# Main sweep — model (outer) → TP → N → reps
# ===========================================================================
T_START_GLOBAL=$(date +%s)
TOTAL_RUNS=$(( ${#MODEL_KEYS[@]} * ${#TP_LADDER[@]} * ${#N_LADDER[@]} * REPS ))
RUNS_DONE=0

log "============================================================"
log "Phase 2 — Bielik v3.0 refresh OOM re-run"
log "Models:     ${MODEL_KEYS[*]}"
log "TP ladder:  ${TP_LADDER[*]}"
log "N ladder:   ${N_LADDER[*]}"
log "Reps/cell:  $REPS"
log "Total runs: $TOTAL_RUNS   (${#MODEL_KEYS[@]} models × ${#TP_LADDER[@]} TP × ${#N_LADDER[@]} N × $REPS reps)"
log "Cooldown:   ${COOLDOWN_S}s between runs"
log "============================================================"
progress "SWEEP_START total_runs=$TOTAL_RUNS"

for ((m=0; m<${#MODEL_KEYS[@]}; m++)); do
    KEY="${MODEL_KEYS[$m]}"
    RESULT_DIR="${RESULT_DIRS[$m]}"
    QUANT="${MODEL_QUANTS[$m]}"
    OUT_DIR="$REPO_ROOT/benchmarks/results/$RESULT_DIR/thermal-runs"
    mkdir -p "$OUT_DIR"

    log "################  MODEL: $KEY ($QUANT) → $RESULT_DIR  ################"
    progress "MODEL_BEGIN key=$KEY quant=$QUANT result_dir=$RESULT_DIR"
    T_MODEL_START=$(date +%s)

    for TP in "${TP_LADDER[@]}"; do
        log "================  $KEY  TP=$TP  ================"
        progress "TP_BEGIN key=$KEY tp=$TP"

        for N in "${N_LADDER[@]}"; do
            log "----  $KEY N=$N (TP=$TP)  ----"
            T_N_START=$(date +%s)
            N_OK=0; N_FAIL=0

            for ((REP=0; REP<REPS; REP++)); do
                NAME="$(printf '%s-tp%d-n%d-r%02d' "$QUANT" "$TP" "$N" "$REP")"
                RUNS_DONE=$((RUNS_DONE + 1))
                log "[$RUNS_DONE/$TOTAL_RUNS] starting $KEY/$NAME"
                RUN_START=$(date +%s)

                # continue-on-fail: a transient HIP OOM at large N must not abort.
                if python3 "$BENCH" \
                    "$KEY" "$TP" "$N" \
                    --quant "$QUANT" \
                    --max-len "$MAX_LEN" \
                    --util "$UTIL" \
                    --name "$NAME" \
                    --out-dir "$OUT_DIR" \
                    --interval 1.0 \
                    --timeout "$PER_RUN_TIMEOUT_S" \
                    >> "$ORCHESTRATOR_LOG" 2>&1
                then
                    N_OK=$((N_OK + 1))
                    RUN_S=$(( $(date +%s) - RUN_START ))
                    log "  OK  $KEY/$NAME (${RUN_S}s wall)"
                else
                    N_FAIL=$((N_FAIL + 1))
                    RUN_S=$(( $(date +%s) - RUN_START ))
                    log "  FAIL $KEY/$NAME (${RUN_S}s wall) — see ${OUT_DIR}/${NAME}-bench.log"
                fi

                if (( RUNS_DONE < TOTAL_RUNS )); then
                    sleep "$COOLDOWN_S"
                fi

                T_NOW=$(date +%s)
                ELAPSED=$((T_NOW - T_START_GLOBAL))
                AVG_S=$((ELAPSED / RUNS_DONE))
                REMAINING=$((TOTAL_RUNS - RUNS_DONE))
                ETA_S=$((AVG_S * REMAINING))
                progress "PROGRESS done=$RUNS_DONE/$TOTAL_RUNS key=$KEY tp=$TP n=$N rep=$REP last_run_s=$RUN_S elapsed_s=$ELAPSED eta_s=$ETA_S"
            done

            T_N_END=$(date +%s)
            log "----  $KEY N=$N (TP=$TP) DONE: $N_OK ok, $N_FAIL fail, $((T_N_END - T_N_START))s  ----"
            progress "N_COMPLETE key=$KEY tp=$TP n=$N ok=$N_OK fail=$N_FAIL"
        done
    done

    T_MODEL_END=$(date +%s)
    log "########  MODEL $KEY DONE: $(( (T_MODEL_END - T_MODEL_START) / 60 )) min  ########"

    # Finalize this model → regenerate phase2_sweep.csv + SUMMARY.md from raw runs.
    log "Finalizing $KEY ..."
    if python3 "$FINALIZE" \
        --results-dir "$REPO_ROOT/benchmarks/results/$RESULT_DIR" \
        --model-label "$KEY" \
        --model-name "${MODEL_HF_NAMES[$m]}" \
        --quant "$QUANT" \
        --max-len "$MAX_LEN" \
        --util "$UTIL" \
        >> "$ORCHESTRATOR_LOG" 2>&1
    then
        log "Finalize OK — see benchmarks/results/$RESULT_DIR/SUMMARY.md"
    else
        log "WARN: finalize failed for $KEY; raw data preserved in $OUT_DIR"
    fi
done

T_TOTAL=$(( $(date +%s) - T_START_GLOBAL ))
log "============================================================"
log "Re-run complete. Total wall: ${T_TOTAL}s ($((T_TOTAL / 60)) min)"
log "Runs completed: $RUNS_DONE / $TOTAL_RUNS"
log "============================================================"
progress "SWEEP_END total_wall_s=$T_TOTAL runs_done=$RUNS_DONE total_runs=$TOTAL_RUNS"

echo "DONE $(date -Iseconds) runs=$RUNS_DONE/$TOTAL_RUNS wall_s=$T_TOTAL" > "$GLOBAL_LOG_DIR/SWEEP_COMPLETE"
log "Sentinel: $GLOBAL_LOG_DIR/SWEEP_COMPLETE"
