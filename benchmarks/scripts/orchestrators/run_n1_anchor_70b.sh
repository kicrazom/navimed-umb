#!/usr/bin/env bash
# =============================================================================
# run_n1_anchor_70b.sh
#
# N=1 SINGLE-STREAM ANCHOR (METHODOLOGY §5.2 / §7.4) — Llama-PLLuM-70B AWQ family.
#
# Single-stream (1 request, sequential decode) latency-regime baseline at Tier A
# (n=10 reps) for the 8 70B AWQ configs (TP=2, compressed-tensors), reusing the
# EXACT path-runner config of run_pllum70b_n10_base.sh. Differs only in:
#   1. N-ladder = "1";
#   2. per-rep output moved to  results/<model>/scaling-n1/rep<NN>/  — a SEPARATE
#      tree from the {10..1000} scaling/ ladder (§7.4: anchor reported separately).
#
# Primitive: throughput_scaling_phase2.py <model> <tp> --quant Q --ns "1"
# (writes results/<model>/scaling/{thermal-runs,results_table.csv,SUMMARY.md};
#  this wrapper moves that fresh n1 output into scaling-n1/rep<NN>/ each rep).
#
# HARD RULES: never pkill/kill (REFUSE on stale vllm); kill_port.sh (setsid).
# vLLM 0.19.0 PINNED. NCCL_P2P_DISABLE=1 (TP=2 dual-R9700, gfx1201 P2P unstable).
# Embargo: EMBARGO=YES paper-bound (§11.2/§11.3); results/ gitignored.
#
# Usage (wrap in systemd-inhibit):
#   systemd-inhibit --what=sleep:idle --who=navimed-n1-70b \
#     --why="N=1 anchor 70B" --mode=block \
#     bash benchmarks/scripts/orchestrators/run_n1_anchor_70b.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"
export NCCL_P2P_DISABLE=1   # required for TP=2 dual-R9700 (gfx1201)

QUANT="compressed-tensors"
TP=2
NS="1"                       # single-stream anchor only
REPS=10
INTER_REP_COOLDOWN_S=30

MODEL_DIRS=(
    "Llama-PLLuM-70B-base-2412-awq"
    "Llama-PLLuM-70B-base-2508-awq"
    "Llama-PLLuM-70B-chat-2412-awq"
    "Llama-PLLuM-70B-chat-2508-awq"
    "Llama-PLLuM-70B-chat-2512-awq"
    "Llama-PLLuM-70B-instruct-2412-awq"
    "Llama-PLLuM-70B-instruct-2508-awq"
    "Llama-PLLuM-70B-instruct-2512-awq"
)

# Optional batching: positional args = subset of model dir names (no args = full roster).
if (( $# > 0 )); then
    _want=" $* "; _sub=()
    for _md in "${MODEL_DIRS[@]}"; do [[ "$_want" == *" $_md "* ]] && _sub+=("$_md"); done
    (( ${#_sub[@]} )) || { echo "ERROR: no model dirs match: $*" >&2; exit 1; }
    MODEL_DIRS=("${_sub[@]}")
fi

RUNNER="$REPO_ROOT/benchmarks/scripts/runners/throughput_scaling_phase2.py"
KILL_PORT="$REPO_ROOT/scripts/kill_port.sh"
RESULTS_ROOT="$REPO_ROOT/benchmarks/results"
GLOBAL_LOG_DIR="$RESULTS_ROOT/_n1_anchor_70b_logs"
mkdir -p "$GLOBAL_LOG_DIR"
ORCH_LOG="$GLOBAL_LOG_DIR/orchestrator.log"
PROG_LOG="$GLOBAL_LOG_DIR/progress.log"
SENTINEL="$GLOBAL_LOG_DIR/SWEEP_COMPLETE"

write_embargo_header() {
    {
        echo "# EMBARGO=YES — paper-bound (Polish models, METHODOLOGY §11.2/§11.3)"
        echo "# Sweep: N=1 single-stream ANCHOR, 70B AWQ family, TP=$TP, reps=$REPS"
        echo "# Output: results/<model>/scaling-n1/rep<NN>/ (separate from {10..1000} ladder, §7.4)"
        echo "# Started: $(date -Iseconds)"
        echo "# Operator: Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>"
        echo "# DO NOT COMMIT raw scaling-n1/ thermal artifacts until paper acceptance."
        echo "#"
    } > "$1"
}
write_embargo_header "$ORCH_LOG"
write_embargo_header "$PROG_LOG"
log()      { echo "[$(date -Iseconds)] $*" | tee -a "$ORCH_LOG"; }
progress() { echo "[$(date -Iseconds)] $*" >> "$PROG_LOG"; }

# Pre-flight.
[[ -f "$RUNNER" ]] || { echo "ERROR: runner missing: $RUNNER" >&2; exit 1; }
for md in "${MODEL_DIRS[@]}"; do
    [[ -f "$HOME/models/$md/config.json" ]] || { echo "ERROR: model missing: ~/models/$md" >&2; exit 1; }
done
stale="$(pgrep -af 'vllm serve|throughput_scaling_phase2.py' 2>/dev/null || true)"
if [[ -n "$stale" ]]; then
    echo "ERROR: stale vllm/scaling processes present — refusing to start (NEVER kill):" >&2
    echo "$stale" >&2; exit 1
fi
python3 -c "import vllm; assert vllm.__version__.startswith('0.19.0'), f'WRONG vLLM: {vllm.__version__}'"
log "vLLM OK: $(python3 -c 'import vllm; print(vllm.__version__)')  NCCL_P2P_DISABLE=$NCCL_P2P_DISABLE"

# Move the fresh n1 output from scaling/ root into scaling-n1/rep<NN>/.
move_rep_output() {
    local sdir="$1" rep="$2"
    local repdir; repdir="$(printf '%s-n1/rep%02d' "$sdir" "$rep")"
    mkdir -p "$repdir"
    local moved=0
    for item in thermal-runs results_table.csv SUMMARY.md; do
        [[ -e "$sdir/$item" ]] && { mv "$sdir/$item" "$repdir/" && moved=$((moved + 1)); }
    done
    log "  rep$(printf '%02d' "$rep"): moved $moved artifact(s) → $repdir"
}

T_START=$(date +%s)
TOTAL=$(( ${#MODEL_DIRS[@]} * REPS )); DONE=0

log "============================================================"
log "N=1 single-stream ANCHOR — Llama-PLLuM-70B AWQ family (Tier A, n=$REPS)"
log "Models: ${#MODEL_DIRS[@]}  TP=$TP  N=$NS  quant=$QUANT  total runs: $TOTAL"
log "============================================================"
progress "SWEEP_START total=$TOTAL"

for md in "${MODEL_DIRS[@]}"; do
    SDIR="$RESULTS_ROOT/$md/scaling"
    mkdir -p "$SDIR"
    log "################  MODEL: $md  ################"
    progress "MODEL_BEGIN model=$md"
    for ((REP=0; REP<REPS; REP++)); do
        DONE=$((DONE + 1))
        log "----  $md rep$(printf '%02d' "$REP")  [$DONE/$TOTAL]  ----"
        RUN_START=$(date +%s)
        bash "$KILL_PORT" 8100 >/dev/null 2>&1 || true
        if python3 "$RUNNER" "$md" "$TP" --quant "$QUANT" --ns "$NS" >> "$ORCH_LOG" 2>&1; then
            log "  OK   $md rep$(printf '%02d' "$REP") ($(( $(date +%s) - RUN_START ))s)"
        else
            log "  FAIL $md rep$(printf '%02d' "$REP") rc!=0 ($(( $(date +%s) - RUN_START ))s) — see $ORCH_LOG"
        fi
        move_rep_output "$SDIR" "$REP"
        bash "$KILL_PORT" 8100 >/dev/null 2>&1 || true
        ELAPSED=$(( $(date +%s) - T_START )); AVG=$(( ELAPSED / DONE ))
        progress "RUN_DONE model=$md rep=$REP done=$DONE/$TOTAL eta_s=$(( AVG * (TOTAL - DONE) ))"
        (( DONE < TOTAL )) && sleep "$INTER_REP_COOLDOWN_S"
    done
    progress "MODEL_COMPLETE model=$md"
done

T_TOTAL=$(( $(date +%s) - T_START ))
log "============================================================"
log "N=1 anchor (70B) complete. Wall: ${T_TOTAL}s ($((T_TOTAL/60)) min). Runs: $DONE/$TOTAL"
log "============================================================"
echo "DONE $(date -Iseconds) runs=$DONE/$TOTAL wall_s=$T_TOTAL" > "$SENTINEL"
progress "SWEEP_END wall_s=$T_TOTAL runs=$DONE/$TOTAL"
log "Sentinel: $SENTINEL"
