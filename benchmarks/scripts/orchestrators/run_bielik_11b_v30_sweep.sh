#!/usr/bin/env bash
# NaviMed-UMB Phase 2 sweep — Bielik 11B v3.0 BF16, TP=1 + TP=2, n=10 reps/cell.
#
# Per METHODOLOGY.md v1.0 §5.2 (with operator-modified N ladder for overnight
# wall time budget, 6-12h):
#   - N ladder: {5, 10, 25, 50, 100, 250}      (spec-modified, see SUMMARY note)
#   - Reps per cell: 10                         (statistical n for medians/p99)
#   - Cooldown between runs: 30s
#   - Background thermal sampling at 1 Hz
#   - TP=1 sweep fully completes before TP=2 begins (sequential, not parallel)
#
# Phase 1 envelope reference (2026-05-17):
#   environment/sanity-tests/2026-05-17-bielik-11b-v30-vllm-tp{1,2}-bf16.json
#
# Output dir (gitignored under benchmarks/results/ — EMBARGOED):
#   benchmarks/results/bielik-11b-v30/thermal-runs/
#     bf16-tp{1,2}-n{5,10,25,50,100,250}-r{00..09}-{bench.log,events.json,thermals.jsonl,thermals.png}
#
# Embargo: EMBARGO_paper_bound (Polish model, METHODOLOGY §11.3).
# Per-file EMBARGO=YES header written to logs and progress files.
#
# Usage from repo root:
#   bash benchmarks/scripts/orchestrators/run_bielik_11b_v30_sweep.sh

set -euo pipefail

# ===========================================================================
# Source the single canonical environment (METHODOLOGY §3.1)
# ===========================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

# ===========================================================================
# Configuration
# ===========================================================================
QUANT="bf16"
MODEL_PATH="/home/mozarcik/models/bielik-11b-v30"
MAX_LEN=8192
UTIL=0.90
N_LADDER=(5 10 25 50 100 250)
TP_LADDER=(1 2)
REPS=10
COOLDOWN_S=30
PER_RUN_TIMEOUT_S=900       # safety: N=250 with preemption ≤ ~5min; 15min = 3× headroom

OUT_DIR="$REPO_ROOT/benchmarks/results/bielik-11b-v30/thermal-runs"
RESULTS_DIR="$REPO_ROOT/benchmarks/results/bielik-11b-v30"
LOG_DIR="$RESULTS_DIR/logs"
PROGRESS_LOG="/tmp/agent4-progress.log"
ORCHESTRATOR_LOG="$LOG_DIR/orchestrator.log"

mkdir -p "$OUT_DIR" "$LOG_DIR"

# ===========================================================================
# Pre-flight: ensure no stale vLLM running, model present
# ===========================================================================
if [[ ! -d "$MODEL_PATH" ]]; then
    echo "ERROR: model not found at $MODEL_PATH" >&2
    exit 1
fi

stale_pids="$(pgrep -af 'vllm serve|run_concurrent.py bielik-11b-v30' 2>/dev/null || true)"
if [[ -n "$stale_pids" ]]; then
    echo "ERROR: stale vllm processes present — refusing to start:" >&2
    echo "$stale_pids" >&2
    exit 1
fi

# ===========================================================================
# Embargo header (per METHODOLOGY §11.4)
# ===========================================================================
write_embargo_header() {
    local f="$1"
    {
        echo "# EMBARGO=YES — paper-bound (Polish model, METHODOLOGY §11.3)"
        echo "# Sweep: bielik-11b-v30 BF16, TP={1,2}, N={5,10,25,50,100,250}, reps=10"
        echo "# Started: $(date -Iseconds)"
        echo "# Operator: Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>"
        echo "# DO NOT COMMIT until paper acceptance."
        echo "#"
    } > "$f"
}

write_embargo_header "$PROGRESS_LOG"
write_embargo_header "$ORCHESTRATOR_LOG"

# ===========================================================================
# Logging helpers
# ===========================================================================
log() {
    local msg="$*"
    local ts
    ts="$(date -Iseconds)"
    echo "[$ts] $msg" | tee -a "$ORCHESTRATOR_LOG"
}

progress() {
    local msg="$*"
    local ts
    ts="$(date -Iseconds)"
    echo "[$ts] $msg" >> "$PROGRESS_LOG"
}

# ===========================================================================
# Sanity: vLLM version pin (per METHODOLOGY)
# ===========================================================================
python3 -c "import vllm; assert vllm.__version__.startswith('0.19.0'), f'WRONG vLLM: {vllm.__version__}'"
log "vLLM version OK: $(python3 -c 'import vllm; print(vllm.__version__)')"

# ===========================================================================
# Main sweep loop
# ===========================================================================
T_START_GLOBAL=$(date +%s)

# Total run count for ETA
TOTAL_RUNS=$((${#TP_LADDER[@]} * ${#N_LADDER[@]} * REPS))
RUNS_DONE=0

log "============================================================"
log "Phase 2 sweep — Bielik 11B v3.0 BF16"
log "TP ladder:  ${TP_LADDER[*]}"
log "N ladder:   ${N_LADDER[*]}"
log "Reps/cell:  $REPS"
log "Total runs: $TOTAL_RUNS"
log "Cooldown:   ${COOLDOWN_S}s between runs"
log "Output dir: $OUT_DIR (gitignored, EMBARGOED)"
log "============================================================"

progress "SWEEP_START total_runs=$TOTAL_RUNS"

for TP in "${TP_LADDER[@]}"; do
    log "================  TP=$TP  ================"
    progress "TP_BEGIN tp=$TP"

    T_TP_START=$(date +%s)

    for N in "${N_LADDER[@]}"; do
        log "----  N=$N (TP=$TP)  ----"
        T_N_START=$(date +%s)
        N_OK=0
        N_FAIL=0

        for ((REP=0; REP<REPS; REP++)); do
            NAME="$(printf '%s-tp%d-n%d-r%02d' "$QUANT" "$TP" "$N" "$REP")"
            RUNS_DONE=$((RUNS_DONE + 1))

            log "[$RUNS_DONE/$TOTAL_RUNS] starting $NAME"

            RUN_START=$(date +%s)

            # Single replication. We use 'continue' on failure rather than abort
            # so a transient HIP OOM at large N does not kill the whole sweep.
            if python3 \
                "$REPO_ROOT/benchmarks/scripts/instrumentation/bench_with_thermals.py" \
                bielik-11b-v30 "$TP" "$N" \
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
                RUN_END=$(date +%s)
                RUN_S=$((RUN_END - RUN_START))
                log "  OK  $NAME (${RUN_S}s wall)"
            else
                N_FAIL=$((N_FAIL + 1))
                RUN_END=$(date +%s)
                RUN_S=$((RUN_END - RUN_START))
                log "  FAIL $NAME (${RUN_S}s wall) — see ${OUT_DIR}/${NAME}-bench.log"
            fi

            # Cooldown between runs (skip after the last rep of the last N of
            # the last TP — we're done)
            if (( RUNS_DONE < TOTAL_RUNS )); then
                sleep "$COOLDOWN_S"
            fi

            # Periodic progress checkpoint (every run; cheap)
            T_NOW=$(date +%s)
            ELAPSED=$((T_NOW - T_START_GLOBAL))
            if (( RUNS_DONE > 0 )); then
                AVG_S=$((ELAPSED / RUNS_DONE))
                REMAINING=$((TOTAL_RUNS - RUNS_DONE))
                ETA_S=$((AVG_S * REMAINING))
                progress "PROGRESS done=$RUNS_DONE/$TOTAL_RUNS tp=$TP n=$N rep=$REP last_run_s=$RUN_S elapsed_s=$ELAPSED eta_s=$ETA_S"
            fi
        done

        T_N_END=$(date +%s)
        N_WALL=$((T_N_END - T_N_START))
        log "----  N=$N (TP=$TP) DONE: $N_OK ok, $N_FAIL fail, ${N_WALL}s wall  ----"
        progress "N_COMPLETE tp=$TP n=$N ok=$N_OK fail=$N_FAIL wall_s=$N_WALL"
    done

    T_TP_END=$(date +%s)
    TP_WALL=$((T_TP_END - T_TP_START))
    log "================  TP=$TP DONE: ${TP_WALL}s ($((TP_WALL / 60)) min)  ================"
    progress "TP_COMPLETE tp=$TP wall_s=$TP_WALL"
done

T_END_GLOBAL=$(date +%s)
T_TOTAL=$((T_END_GLOBAL - T_START_GLOBAL))

log "============================================================"
log "Sweep complete. Total wall: ${T_TOTAL}s ($((T_TOTAL / 60)) min)"
log "Runs completed: $RUNS_DONE / $TOTAL_RUNS"
log "Output: $OUT_DIR"
log "============================================================"

progress "SWEEP_END total_wall_s=$T_TOTAL runs_done=$RUNS_DONE total_runs=$TOTAL_RUNS"

# ===========================================================================
# Aggregate (delegated to finalize_bielik_11b_v30_phase2.py)
# ===========================================================================
log "Running finalize script..."
if python3 "$REPO_ROOT/benchmarks/scripts/analysis/finalize_bielik_11b_v30_phase2.py" \
    >> "$ORCHESTRATOR_LOG" 2>&1
then
    log "Finalize OK — see $RESULTS_DIR/SUMMARY.md"
else
    log "WARN: finalize failed; raw data still in $OUT_DIR"
fi

log "Done."
