#!/usr/bin/env bash
# NaviMed-UMB Phase 2 — canonical-ladder GAP RECOVERY (targeted, OOM recovery).
#
# WHY: the 2026-06-07 completeness audit (audit_paper1_completeness.py + per-cell
# finalize verdict) found that, beyond the 2 Bielik v3.0 refresh models (handled
# by run_bielik_v30_refresh_rerun.sh), five more small models have DEAD or ABSENT
# canonical cells — the high-N {500,1000} + the canonical N=200 point + (for 4.5b)
# the entire TP=2 leg failed OOM in the 2026-06-06 chain collision. The
# 160/160 sentinels lied (continue-on-fail counts ATTEMPTS, not successes).
#
# SCOPE — ONLY the missing/dead (TP,N) cells per model. Cells that already have
# n=10 ok are NOT touched. The 8× 70B family (complete) is NOT touched.
# Canonical ladder only: N ∈ {10,25,50,100,200,500,1000}. Non-canonical N=250
# (already present, succeeded) is left as-is — kept as supplementary data, its
# inclusion in figures decided separately by the N-ladder sensitivity analysis.
#
# Missing-cell matrix (TP:N), n=10 reps each:
#   bielik-11b      (v23,  fp16): 1:200 1:500 1:1000 2:200 2:500 2:1000
#   bielik-11b-v30  (bf16):       1:200 1:500 1:1000 2:200 2:500 2:1000
#   bielik-4.5b-v30 (bf16):       1:200 1:500 1:1000 2:10 2:25 2:50 2:100 2:200 2:500 2:1000
#   pllum-8b-awq    (awq):        1:200 2:200
#   pllum-12b-awq   (awq):        1:200 2:200
#   → 26 cells × 10 reps = 260 runs.
#
# bench_with_thermals.py resolves the model path from the KEY (no --model-path).
# Writes to each model's existing result dir so finalize_phase2_generic.py merges
# the recovered cells with the surviving low-N cells.
#
# Embargo: EMBARGO_paper_bound (Polish models, METHODOLOGY §11.3).
#
# Usage (normally invoked by launch_canonical_recovery_after_v30.sh under
# systemd-inhibit; can be run standalone once the GPU is idle):
#   bash benchmarks/scripts/orchestrators/run_bielik_pllum_canonical_recovery.sh

set -euo pipefail

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
REPS=10
COOLDOWN_S=30
PER_RUN_TIMEOUT_S=1800

# Parallel arrays — index-aligned. CELLS = space-separated TP:N pairs to recover.
MODEL_KEYS=(
    "bielik-11b"
    "bielik-11b-v30"
    "bielik-4.5b-v30"
    "pllum-8b-awq"
    "pllum-12b-awq"
)
RESULT_DIRS=(
    "bielik-11b-v23"
    "bielik-11b-v30"
    "bielik-4.5b-v30"
    "Llama-PLLuM-8B-chat-2512-awq"
    "PLLuM-12B-chat-2512-awq"
)
MODEL_QUANTS=(
    "fp16"
    "bf16"
    "bf16"
    "awq"
    "awq"
)
MODEL_PATHS=(
    "/home/mozarcik/models/bielik-11b-v23"
    "/home/mozarcik/models/bielik-11b-v30"
    "/home/mozarcik/models/bielik-4.5b-v30"
    "/home/mozarcik/models/Llama-PLLuM-8B-chat-2512-awq"
    "/home/mozarcik/models/PLLuM-12B-chat-2512-awq"
)
MODEL_HF_NAMES=(
    "speakleash/Bielik-11B-v2.3-Instruct"
    "speakleash/Bielik-11B-v3.0-Instruct"
    "speakleash/Bielik-4.5B-v3-Instruct"
    "mozarcik/Llama-PLLuM-8B-chat-2512-awq"
    "mozarcik/PLLuM-12B-chat-2512-awq"
)
MODEL_CELLS=(
    "1:200 1:500 1:1000 2:200 2:500 2:1000"
    "1:200 1:500 1:1000 2:200 2:500 2:1000"
    "1:200 1:500 1:1000 2:10 2:25 2:50 2:100 2:200 2:500 2:1000"
    "1:200 2:200"
    "1:200 2:200"
)

BENCH="$REPO_ROOT/benchmarks/scripts/instrumentation/bench_with_thermals.py"
FINALIZE="$REPO_ROOT/benchmarks/scripts/analysis/finalize_phase2_generic.py"

GLOBAL_LOG_DIR="$REPO_ROOT/benchmarks/results/_canonical_recovery_logs"
ORCHESTRATOR_LOG="$GLOBAL_LOG_DIR/orchestrator.log"
PROGRESS_LOG="$GLOBAL_LOG_DIR/progress.log"
mkdir -p "$GLOBAL_LOG_DIR"

# ===========================================================================
# Pre-flight: models present; no stale vLLM (REFUSE — never pkill, per memory
# feedback_kill_isolation). This is the second anti-collision guard.
# ===========================================================================
for mp in "${MODEL_PATHS[@]}"; do
    [[ -d "$mp" ]] || { echo "ERROR: model not found at $mp" >&2; exit 1; }
done
stale_pids="$(pgrep -af 'vllm serve|run_concurrent.py|bench_with_thermals.py' 2>/dev/null || true)"
if [[ -n "$stale_pids" ]]; then
    echo "ERROR: vllm/bench processes present — refusing to start (avoid GPU collision):" >&2
    echo "$stale_pids" >&2
    exit 1
fi

write_embargo_header() {
    local f="$1"
    {
        echo "# EMBARGO=YES — paper-bound (Polish models, METHODOLOGY §11.3)"
        echo "# Sweep: canonical-ladder gap recovery (targeted missing cells)"
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

python3 -c "import vllm; assert vllm.__version__.startswith('0.19.0'), f'WRONG vLLM: {vllm.__version__}'"
log "vLLM version OK: $(python3 -c 'import vllm; print(vllm.__version__)')"

# Total run count for ETA.
TOTAL_RUNS=0
for cells in "${MODEL_CELLS[@]}"; do
    # shellcheck disable=SC2206
    arr=($cells)
    TOTAL_RUNS=$(( TOTAL_RUNS + ${#arr[@]} * REPS ))
done
RUNS_DONE=0
T_START_GLOBAL=$(date +%s)

log "============================================================"
log "Phase 2 — canonical-ladder gap recovery (targeted)"
log "Models:     ${MODEL_KEYS[*]}"
log "Total runs: $TOTAL_RUNS   (26 cells × $REPS reps)"
log "============================================================"
progress "SWEEP_START total_runs=$TOTAL_RUNS"

for ((m=0; m<${#MODEL_KEYS[@]}; m++)); do
    KEY="${MODEL_KEYS[$m]}"
    RESULT_DIR="${RESULT_DIRS[$m]}"
    QUANT="${MODEL_QUANTS[$m]}"
    OUT_DIR="$REPO_ROOT/benchmarks/results/$RESULT_DIR/thermal-runs"
    mkdir -p "$OUT_DIR"
    # shellcheck disable=SC2206
    CELLS=(${MODEL_CELLS[$m]})

    log "################  MODEL: $KEY ($QUANT) → $RESULT_DIR — ${#CELLS[@]} cells  ################"
    progress "MODEL_BEGIN key=$KEY quant=$QUANT cells=${#CELLS[@]}"
    T_MODEL_START=$(date +%s)

    for cell in "${CELLS[@]}"; do
        TP="${cell%%:*}"
        N="${cell##*:}"
        log "----  $KEY TP=$TP N=$N  ----"
        N_OK=0; N_FAIL=0

        for ((REP=0; REP<REPS; REP++)); do
            NAME="$(printf '%s-tp%d-n%d-r%02d' "$QUANT" "$TP" "$N" "$REP")"
            RUNS_DONE=$((RUNS_DONE + 1))
            log "[$RUNS_DONE/$TOTAL_RUNS] starting $KEY/$NAME"
            RUN_START=$(date +%s)

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
                log "  OK  $KEY/$NAME ($(( $(date +%s) - RUN_START ))s wall)"
            else
                N_FAIL=$((N_FAIL + 1))
                log "  FAIL $KEY/$NAME ($(( $(date +%s) - RUN_START ))s wall) — see ${OUT_DIR}/${NAME}-bench.log"
            fi

            if (( RUNS_DONE < TOTAL_RUNS )); then sleep "$COOLDOWN_S"; fi

            ELAPSED=$(( $(date +%s) - T_START_GLOBAL ))
            AVG_S=$((ELAPSED / RUNS_DONE))
            ETA_S=$(( AVG_S * (TOTAL_RUNS - RUNS_DONE) ))
            progress "PROGRESS done=$RUNS_DONE/$TOTAL_RUNS key=$KEY tp=$TP n=$N rep=$REP elapsed_s=$ELAPSED eta_s=$ETA_S"
        done
        log "----  $KEY TP=$TP N=$N DONE: $N_OK ok, $N_FAIL fail  ----"
        progress "CELL_COMPLETE key=$KEY tp=$TP n=$N ok=$N_OK fail=$N_FAIL"
    done

    log "########  MODEL $KEY DONE: $(( ( $(date +%s) - T_MODEL_START ) / 60 )) min  ########"
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
log "Recovery complete. Total wall: ${T_TOTAL}s ($((T_TOTAL / 60)) min)"
log "Runs completed: $RUNS_DONE / $TOTAL_RUNS"
log "============================================================"
progress "SWEEP_END total_wall_s=$T_TOTAL runs_done=$RUNS_DONE total_runs=$TOTAL_RUNS"

echo "DONE $(date -Iseconds) runs=$RUNS_DONE/$TOTAL_RUNS wall_s=$T_TOTAL" > "$GLOBAL_LOG_DIR/SWEEP_COMPLETE"
log "Sentinel: $GLOBAL_LOG_DIR/SWEEP_COMPLETE"
