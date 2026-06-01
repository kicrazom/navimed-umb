#!/usr/bin/env bash
# NaviMed-UMB Phase 2 — Run-3 HIGH-N extension (N={500,1000}) at n=10 reps/cell.
#
# WHY: the Run-3 8B/12B sweep used the operator ladder {5,10,25,50,100,250} and
# was still climbing at N=250 (knee not reached). This extends the ladder into
# the high-N / preemption regime so the knee + plateau are captured, matching the
# 70B family's {10..1000}. Output joins the existing
# benchmarks/results/<model>/thermal-runs/ so the FULL ladder
# {5,10,25,50,100,250,500,1000} can be aggregated (finalize re-run with --n-ladder).
#
# Models: pllum-8b-awq, pllum-12b-awq (keyed entries already in run_concurrent.py /
# bench_with_thermals.py). TP={1,2}, max_len=8192, util=0.90, reps=10.
# 2 models × 2 TP × 2 N × 10 reps = 80 runs. Embargo EMBARGO_paper_bound §11.2/§11.3.
#
# Runs AFTER the 70B rerun via launch_run3_highN_after_70b.sh (chained). Wrap in
# systemd-inhibit. NEVER pkill (memory feedback_kill_isolation).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"
export NCCL_P2P_DISABLE=1   # required for TP=2 on dual R9700

QUANT="awq"
MAX_LEN=8192
UTIL=0.90
N_LADDER=(500 1000)
TP_LADDER=(1 2)
REPS=10
COOLDOWN_S=30
PER_RUN_TIMEOUT_S=1800           # N=1000 reps are long; caught as rc=124, never kills
FULL_LADDER="5,10,25,50,100,250,500,1000"

MODEL_KEYS=("pllum-8b-awq" "pllum-12b-awq")
RESULT_DIRS=("Llama-PLLuM-8B-chat-2512-awq" "PLLuM-12B-chat-2512-awq")
MODEL_PATHS=(
    "/home/mozarcik/models/Llama-PLLuM-8B-chat-2512-awq"
    "/home/mozarcik/models/PLLuM-12B-chat-2512-awq"
)
MODEL_HF_NAMES=(
    "mozarcik/Llama-PLLuM-8B-chat-2512-awq"
    "mozarcik/PLLuM-12B-chat-2512-awq"
)

BENCH="$REPO_ROOT/benchmarks/scripts/instrumentation/bench_with_thermals.py"
FINALIZE="$REPO_ROOT/benchmarks/scripts/analysis/finalize_phase2_generic.py"
PROGRESS_LOG="/tmp/run3-highN-progress.log"
GLOBAL_LOG_DIR="$REPO_ROOT/benchmarks/results/_run3_highN_logs"
mkdir -p "$GLOBAL_LOG_DIR"
ORCHESTRATOR_LOG="$GLOBAL_LOG_DIR/orchestrator.log"
SENTINEL="$GLOBAL_LOG_DIR/HIGHN_COMPLETE"

write_embargo_header() {
    {
        echo "# EMBARGO=YES — paper-bound (Polish model, METHODOLOGY §11.2/§11.3)"
        echo "# Sweep: Run-3 HIGH-N {8B,12B}, TP={1,2}, N={500,1000}, reps=10"
        echo "# Started: $(date -Iseconds)"
        echo "# DO NOT COMMIT raw thermal-runs/ until paper acceptance."
        echo "#"
    } > "$1"
}
write_embargo_header "$PROGRESS_LOG"
write_embargo_header "$ORCHESTRATOR_LOG"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$ORCHESTRATOR_LOG"; }
progress() { echo "[$(date -Iseconds)] $*" >> "$PROGRESS_LOG"; }

# Pre-flight: models present, no stale vLLM (REFUSE — never kill).
for mp in "${MODEL_PATHS[@]}"; do
    if [[ ! -f "$mp/config.json" ]]; then
        echo "ERROR: model not found at $mp" >&2
        exit 1
    fi
done
stale_pids="$(pgrep -af 'vllm serve|run_concurrent.py (pllum-8b-awq|pllum-12b-awq)' 2>/dev/null || true)"
if [[ -n "$stale_pids" ]]; then
    echo "ERROR: stale vllm/run_concurrent present — refusing (never kill):" >&2
    echo "$stale_pids" >&2
    exit 1
fi
python3 -c "import vllm; assert vllm.__version__.startswith('0.19.0'), vllm.__version__"
log "vLLM $(python3 -c 'import vllm; print(vllm.__version__)') | NCCL_P2P_DISABLE=$NCCL_P2P_DISABLE"

T_START=$(date +%s)
TOTAL=$(( ${#MODEL_KEYS[@]} * ${#TP_LADDER[@]} * ${#N_LADDER[@]} * REPS ))
DONE=0
log "Run-3 HIGH-N: ${MODEL_KEYS[*]} × TP{${TP_LADDER[*]}} × N{${N_LADDER[*]}} × ${REPS} = ${TOTAL} runs"
progress "SWEEP_START total=$TOTAL"

for ((m = 0; m < ${#MODEL_KEYS[@]}; m++)); do
    KEY="${MODEL_KEYS[$m]}"
    RDIR="${RESULT_DIRS[$m]}"
    OUT="$REPO_ROOT/benchmarks/results/$RDIR/thermal-runs"
    mkdir -p "$OUT"
    log "################  $KEY → $RDIR  ################"
    progress "MODEL_BEGIN key=$KEY"

    for TP in "${TP_LADDER[@]}"; do
        for N in "${N_LADDER[@]}"; do
            T_N=$(date +%s)
            OKN=0
            FAILN=0
            for ((REP = 0; REP < REPS; REP++)); do
                NAME="$(printf '%s-tp%d-n%d-r%02d' "$QUANT" "$TP" "$N" "$REP")"
                DONE=$((DONE + 1))
                RS=$(date +%s)
                log "[$DONE/$TOTAL] starting $KEY/$NAME"
                if python3 "$BENCH" "$KEY" "$TP" "$N" \
                    --quant "$QUANT" --max-len "$MAX_LEN" --util "$UTIL" \
                    --name "$NAME" --out-dir "$OUT" --interval 1.0 \
                    --timeout "$PER_RUN_TIMEOUT_S" >> "$ORCHESTRATOR_LOG" 2>&1; then
                    OKN=$((OKN + 1))
                    log "  OK  $KEY/$NAME ($(($(date +%s) - RS))s)"
                else
                    FAILN=$((FAILN + 1))
                    log "  FAIL $KEY/$NAME ($(($(date +%s) - RS))s)"
                fi
                if ((DONE < TOTAL)); then
                    sleep "$COOLDOWN_S"
                fi
                progress "PROGRESS done=$DONE/$TOTAL model=$KEY tp=$TP n=$N rep=$REP elapsed_s=$(($(date +%s) - T_START))"
            done
            log "----  $KEY N=$N (TP=$TP): $OKN ok, $FAILN fail, $(($(date +%s) - T_N))s  ----"
            progress "N_COMPLETE key=$KEY tp=$TP n=$N ok=$OKN fail=$FAILN"
        done
    done

    # Re-finalize with the FULL merged ladder so the {5..1000} curve is produced.
    if [[ -f "$FINALIZE" ]]; then
        log "Finalizing $KEY over full ladder $FULL_LADDER ..."
        if python3 "$FINALIZE" \
            --results-dir "$REPO_ROOT/benchmarks/results/$RDIR" \
            --model-label "$KEY" --model-name "${MODEL_HF_NAMES[$m]}" \
            --quant "$QUANT" --max-len "$MAX_LEN" --util "$UTIL" \
            --n-ladder "$FULL_LADDER" >> "$ORCHESTRATOR_LOG" 2>&1; then
            log "  finalize OK — benchmarks/results/$RDIR/SUMMARY.md"
        else
            log "  WARN: finalize failed for $KEY; raw data preserved in $OUT"
        fi
    fi
    progress "MODEL_COMPLETE key=$KEY"
done

T_TOTAL=$(($(date +%s) - T_START))
log "============================================================"
log "Run-3 HIGH-N complete: $DONE / $TOTAL runs, ${T_TOTAL}s ($((T_TOTAL / 60)) min)"
log "============================================================"
echo "DONE $(date -Iseconds) runs=$DONE/$TOTAL wall_s=$T_TOTAL" > "$SENTINEL"
progress "SWEEP_END done=$DONE total=$TOTAL wall_s=$T_TOTAL"
log "Sentinel: $SENTINEL"
