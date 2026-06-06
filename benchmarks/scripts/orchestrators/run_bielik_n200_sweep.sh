#!/usr/bin/env bash
# NaviMed-UMB Phase 2 sweep — single-shot POLISH Bielik variants → Tier-A n=10
# (METHODOLOGY §7.4/§7.5). Brings the Bielik family up to the same statistical
# rigour as the golden reference bielik-11b-v30 (already n=10).
#
# Four Polish Bielik variants, all local on 2× R9700 (gfx1201), TP={1,2}:
#   1. bielik-11b                 → bielik-11b-v23           (Mistral, FP16, AutoAWQ-free fp16 path)
#   2. bielik-4.5b-v30            → bielik-4.5b-v30          (Llama, BF16)
#   3. bielik-pl-11b-v30-instruct → bielik-pl-11b-v30-instruct (Llama, BF16)
#   4. bielik-11b-v30-instruct-awq→ bielik-11b-v30-instruct-awq (Llama, compressed-tensors W4A16)
#
# International Qwen/Mistral/Kimi are OUT of scope (owner's Polish-first priority).
#
# Per METHODOLOGY.md §7.4/§7.5, mirroring run_pllum_run3_sweep.sh AND matching the
# bielik-11b-v30 golden-reference cell for cross-model comparability:
#   - N ladder:  {5, 10, 25, 50, 100, 250}   (== bielik-11b-v30/thermal-runs, verified)
#   - TP ladder: {1, 2}
#   - Reps/cell: 10                           (statistical n for medians/p99)
#   - Cooldown:  30s between runs
#   - max_model_len 8192, gpu_memory_utilization 0.90  (suite default == v30 cell)
#   - Workload: METHODOLOGY §6 standard (8 templates × 20 topics, max_tokens=128)
#   - Background thermal sampling at 1 Hz
#   - Each model sweep fully completes before the next begins (sequential;
#     partial results available between models)
#
# Per-model quant differs: bielik-11b → fp16; the two v3.0 base/instruct → bf16;
# the v3.0 instruct AWQ → awq (compressed-tensors auto-detected by vLLM).
#
# Inner path: bench_with_thermals.py <key> <tp> <n> → run_concurrent.py (offline
# LLM.generate, NOT the chat HTTP endpoint — chat-template issue is irrelevant).
# This path is INDEPENDENT of the 70B path-based throughput_scaling_phase2.py.
#
# Output dir (gitignored under benchmarks/results/*/thermal-runs/ — EMBARGOED):
#   benchmarks/results/<RESULT_DIR>/thermal-runs/
#     <quant>-tp{1,2}-n{5,10,25,50,100,250}-r{00..09}-{bench.log,events.json,thermals.jsonl,thermals.png}
#
# Embargo: EMBARGO_paper_bound (Polish model, METHODOLOGY §11.2/§11.3).
# Per-file EMBARGO=YES header written to logs and progress files. DO NOT COMMIT
# raw thermal-runs/ data until paper acceptance.
#
# Usage from repo root (wrap in systemd-inhibit to survive idle-suspend):
#   systemd-inhibit --what=sleep:idle --who=navimed-bielik-tierA \
#       --why="Bielik Tier-A n=10 sweep" --mode=block \
#       bash benchmarks/scripts/orchestrators/run_bielik_tierA_n10_sweep.sh

set -euo pipefail

# ===========================================================================
# Source the single canonical environment (METHODOLOGY §3.1)
# NB: $SCRIPT_DIR is CLOBBERED by `source _env.sh` (it sets its own
# SCRIPT_DIR=.../scripts). $REPO_ROOT is captured BEFORE the source and all
# sibling paths derive from it — never from $SCRIPT_DIR after this point.
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
N_LADDER=(200)              # UNIFORMITY: add n200 (70B/paper §3.3 canonical point) to Bielik
TP_LADDER=(1 2)
REPS=10
COOLDOWN_S=30
PER_RUN_TIMEOUT_S=900       # caught as rc=124 (catch_timeout) — never kills sweep

# Parallel arrays: model key → result dir → per-model quant → HF name.
# Index alignment is load-bearing; keep all four arrays in lock-step.
MODEL_KEYS=(
    "bielik-11b"
    "bielik-4.5b-v30"
    "bielik-pl-11b-v30-instruct"
    "bielik-11b-v30-instruct-awq"
)
RESULT_DIRS=(
    "bielik-11b-v23"
    "bielik-4.5b-v30"
    "bielik-pl-11b-v30-instruct"
    "bielik-11b-v30-instruct-awq"
)
MODEL_QUANTS=(
    "fp16"
    "bf16"
    "bf16"
    "awq"
)
MODEL_PATHS=(
    "/home/mozarcik/models/bielik-11b-v23"
    "/home/mozarcik/models/bielik-4.5b-v30"
    "/home/mozarcik/models/bielik-pl-11b-v30-instruct"
    "/home/mozarcik/models/bielik-11b-v30-instruct-awq"
)
MODEL_HF_NAMES=(
    "speakleash/Bielik-11B-v2.3-Instruct"
    "speakleash/Bielik-4.5B-v3-Instruct"
    "speakleash/Bielik-PL-11B-v3.0-Instruct"
    "speakleash/Bielik-11B-v3.0-Instruct"
)

BENCH="$REPO_ROOT/benchmarks/scripts/instrumentation/bench_with_thermals.py"
FINALIZE="$REPO_ROOT/benchmarks/scripts/analysis/finalize_phase2_generic.py"
PROGRESS_LOG="/tmp/bielik-n200-sweep-progress.log"
GLOBAL_LOG_DIR="$REPO_ROOT/benchmarks/results/_bielik_n200_logs"
mkdir -p "$GLOBAL_LOG_DIR"
ORCHESTRATOR_LOG="$GLOBAL_LOG_DIR/orchestrator.log"

# ===========================================================================
# Embargo header (per METHODOLOGY §11.4)
# ===========================================================================
write_embargo_header() {
    local f="$1"
    {
        echo "# EMBARGO=YES — paper-bound (Polish model, METHODOLOGY §11.2/§11.3)"
        echo "# Sweep: Bielik n=10 UNIFORMITY n200 {11b-v23,4.5b-v30,pl-11b-v30,11b-v30-awq},"
        echo "#        TP={1,2}, N={200}, reps=10  (fills the 70B/§3.3 canonical mid-point)"
        echo "# Started: $(date -Iseconds)"
        echo "# Operator: Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>"
        echo "# DO NOT COMMIT raw thermal-runs/ until paper acceptance."
        echo "#"
    } > "$f"
}
write_embargo_header "$PROGRESS_LOG"
write_embargo_header "$ORCHESTRATOR_LOG"

log() {
    local ts; ts="$(date -Iseconds)"
    echo "[$ts] $*" | tee -a "$ORCHESTRATOR_LOG"
}
progress() {
    local ts; ts="$(date -Iseconds)"
    echo "[$ts] $*" >> "$PROGRESS_LOG"
}

# ===========================================================================
# Pre-flight: models present, no stale vLLM (REFUSE — never pkill, per
# memory feedback_kill_isolation). The sweep refuses rather than killing.
# ===========================================================================
for mp in "${MODEL_PATHS[@]}"; do
    if [[ ! -f "$mp/config.json" ]]; then
        echo "ERROR: model not found at $mp" >&2
        exit 1
    fi
done

stale_pids="$(pgrep -af 'vllm serve|run_concurrent.py (bielik-11b|bielik-4.5b-v30|bielik-pl-11b-v30-instruct|bielik-11b-v30-instruct-awq)' 2>/dev/null || true)"
if [[ -n "$stale_pids" ]]; then
    echo "ERROR: stale vllm/run_concurrent processes present — refusing to start:" >&2
    echo "$stale_pids" >&2
    exit 1
fi

# vLLM version pin assert (per METHODOLOGY — 0.19.0+rocm721 PINNED)
python3 -c "import vllm; assert vllm.__version__.startswith('0.19.0'), f'WRONG vLLM: {vllm.__version__}'"
log "vLLM version OK: $(python3 -c 'import vllm; print(vllm.__version__)')"

# ===========================================================================
# ETA bookkeeping
# ===========================================================================
T_START_GLOBAL=$(date +%s)
TOTAL_RUNS=$(( ${#MODEL_KEYS[@]} * ${#TP_LADDER[@]} * ${#N_LADDER[@]} * REPS ))
RUNS_DONE=0

log "============================================================"
log "Phase 2 sweep — Bielik Tier-A n=10 (Polish single-shot variants)"
log "Models:     ${MODEL_KEYS[*]}"
log "TP ladder:  ${TP_LADDER[*]}"
log "N ladder:   ${N_LADDER[*]}"
log "Reps/cell:  $REPS    max_len: $MAX_LEN    util: $UTIL"
log "Total runs: $TOTAL_RUNS   (${#MODEL_KEYS[@]} models × ${#TP_LADDER[@]} TP × ${#N_LADDER[@]} N × $REPS reps)"
log "Cooldown:   ${COOLDOWN_S}s between runs"
log "============================================================"
progress "SWEEP_START total_runs=$TOTAL_RUNS"

# ===========================================================================
# Main sweep — model (outer) → TP → N → reps
# ===========================================================================
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

                # 'continue' on failure: a transient HIP OOM at large N must not
                # abort the whole overnight sweep.
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
                progress "PROGRESS done=$RUNS_DONE/$TOTAL_RUNS model=$KEY tp=$TP n=$N rep=$REP last_run_s=$RUN_S elapsed_s=$ELAPSED eta_s=$ETA_S"
            done

            N_WALL=$(( $(date +%s) - T_N_START ))
            log "----  $KEY N=$N (TP=$TP) DONE: $N_OK ok, $N_FAIL fail, ${N_WALL}s wall  ----"
            progress "N_COMPLETE key=$KEY tp=$TP n=$N ok=$N_OK fail=$N_FAIL wall_s=$N_WALL"
        done
        progress "TP_COMPLETE key=$KEY tp=$TP"
    done

    T_MODEL_WALL=$(( $(date +%s) - T_MODEL_START ))
    log "################  $KEY DONE: ${T_MODEL_WALL}s ($((T_MODEL_WALL / 60)) min)  ################"
    progress "MODEL_COMPLETE key=$KEY wall_s=$T_MODEL_WALL"

    # Per-model finalize — best-effort, OFF the critical path. Raw data in
    # OUT_DIR is the deliverable; aggregation can be (re)run later by hand.
    # This n200 sweep runs LAST (chained after Tier-A {5..250} + high-N {500,1000}),
    # so by finalize time the model dir holds the FULL 9-point ladder. Aggregate over it.
    if [[ -f "$FINALIZE" ]]; then
        log "Finalizing $KEY (full 9-pt ladder incl. n200) ..."
        if python3 "$FINALIZE" \
            --results-dir "$REPO_ROOT/benchmarks/results/$RESULT_DIR" \
            --model-label "$KEY" \
            --model-name "${MODEL_HF_NAMES[$m]}" \
            --quant "$QUANT" \
            --max-len "$MAX_LEN" \
            --util "$UTIL" \
            --n-ladder 5,10,25,50,100,200,250,500,1000 \
            >> "$ORCHESTRATOR_LOG" 2>&1
        then
            log "Finalize OK — see benchmarks/results/$RESULT_DIR/SUMMARY.md"
        else
            log "WARN: finalize failed for $KEY; raw data preserved in $OUT_DIR"
        fi
    else
        log "NOTE: finalize script not present ($FINALIZE) — raw data in $OUT_DIR, aggregate later"
    fi
done

T_TOTAL=$(( $(date +%s) - T_START_GLOBAL ))
log "============================================================"
log "Sweep complete. Total wall: ${T_TOTAL}s ($((T_TOTAL / 60)) min)"
log "Runs completed: $RUNS_DONE / $TOTAL_RUNS"
log "============================================================"
progress "SWEEP_END total_wall_s=$T_TOTAL runs_done=$RUNS_DONE total_runs=$TOTAL_RUNS"

# Sentinel for the orchestrator/monitor — mirrors hf-download-watchdog pattern.
echo "DONE $(date -Iseconds) runs=$RUNS_DONE/$TOTAL_RUNS wall_s=$T_TOTAL" \
    > "$GLOBAL_LOG_DIR/SWEEP_COMPLETE"
log "Sentinel written: $GLOBAL_LOG_DIR/SWEEP_COMPLETE"
