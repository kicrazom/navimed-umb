#!/usr/bin/env bash
# =============================================================================
# run_n1_anchor_smallmid.sh
#
# N=1 SINGLE-STREAM ANCHOR (METHODOLOGY §5.2 / §7.4) — small/mid tier.
#
# Measures the single-stream (1 request, sequential decode) latency-regime
# baseline at Tier A (n=10 reps) for the 15 small/mid model×TP configurations,
# reusing the EXACT registry keys + quants of the validated Tier-A sweeps. Only
# two things differ from the canonical sweep:
#   1. N-ladder is {1} (single-stream anchor only);
#   2. output goes to a SEPARATE  benchmarks/results/<key>/n1-anchor/  tree, so
#      the anchor never mixes with the {10..1000} concurrency ladder
#      (§7.4: N=1 is reported separately, excluded from knee / Holm–Bonferroni).
#
# Primitive: bench_with_thermals.py <KEY> <TP> <N> --quant Q --name ... --out-dir
# (keyed runner; same one the Bielik Tier-A sweep uses). Reps are distinguished
# by --name (rNN), no move needed. Smoke-validated 2026-06-21 on bielik-4.5b-v30
# (TP=1, N=1 → ~20.2 tok/s, σ ≈ 0.2%).
#
# HARD RULES: never pkill/kill (REFUSE on stale vllm, memory feedback_kill_isolation);
# port cleanup via scripts/kill_port.sh (setsid). vLLM 0.19.0 PINNED.
# Embargo: EMBARGO=YES paper-bound (Polish models, §11.2/§11.3); results/ gitignored.
#
# Usage (wrap in systemd-inhibit to survive idle-suspend):
#   systemd-inhibit --what=sleep:idle --who=navimed-n1-smallmid \
#     --why="N=1 anchor small/mid" --mode=block \
#     bash benchmarks/scripts/orchestrators/run_n1_anchor_smallmid.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"
export NCCL_P2P_DISABLE=1   # required for any TP=2 on gfx1201 (P2P path unstable); harmless at TP=1

MAX_LEN=8192
UTIL=0.90
REPS=10
COOLDOWN_S=30
PER_RUN_TIMEOUT_S=600

BENCH="$REPO_ROOT/benchmarks/scripts/instrumentation/bench_with_thermals.py"
KILL_PORT="$REPO_ROOT/scripts/kill_port.sh"
RESULTS_ROOT="$REPO_ROOT/benchmarks/results"
GLOBAL_LOG_DIR="$RESULTS_ROOT/_n1_anchor_smallmid_logs"
mkdir -p "$GLOBAL_LOG_DIR"
ORCH_LOG="$GLOBAL_LOG_DIR/orchestrator.log"
PROG_LOG="$GLOBAL_LOG_DIR/progress.log"
SENTINEL="$GLOBAL_LOG_DIR/SWEEP_COMPLETE"

# Roster: "KEY QUANT TP...".  KEYs are bench_with_thermals.py MODELS registry keys.
# 7 models × {TP=1,TP=2} + Qwen baseline (TP=1) = 15 configs.
CONFIGS=(
  "bielik-11b fp16 1 2"
  "bielik-11b-v30 bf16 1 2"
  "bielik-11b-v30-instruct-awq awq 1 2"
  "bielik-4.5b-v30 bf16 1 2"
  "bielik-pl-11b-v30-instruct bf16 1 2"
  "pllum-12b-awq awq 1 2"
  "pllum-8b-awq awq 1 2"
  "qwen3.5-9b bf16 1"
)

write_embargo_header() {
    {
        echo "# EMBARGO=YES — paper-bound (Polish models, METHODOLOGY §11.2/§11.3)"
        echo "# Sweep: N=1 single-stream ANCHOR, small/mid tier, Tier A reps=$REPS"
        echo "# Output: benchmarks/results/<key>/n1-anchor/ (separate from {10..1000} ladder, §7.4)"
        echo "# Started: $(date -Iseconds)"
        echo "# Operator: Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>"
        echo "# DO NOT COMMIT raw n1-anchor/ thermal artifacts until paper acceptance."
        echo "#"
    } > "$1"
}
write_embargo_header "$ORCH_LOG"
write_embargo_header "$PROG_LOG"
log()      { echo "[$(date -Iseconds)] $*" | tee -a "$ORCH_LOG"; }
progress() { echo "[$(date -Iseconds)] $*" >> "$PROG_LOG"; }

# Pre-flight: vLLM pin + REFUSE on stale vllm (never kill, feedback_kill_isolation).
python3 -c "import vllm; assert vllm.__version__.startswith('0.19.0'), f'WRONG vLLM: {vllm.__version__}'"
log "vLLM version OK: $(python3 -c 'import vllm; print(vllm.__version__)')"
stale="$(pgrep -af 'vllm serve|bench_with_thermals.py' 2>/dev/null || true)"
if [[ -n "$stale" ]]; then
    echo "ERROR: stale vllm/bench processes present — refusing to start (NEVER kill):" >&2
    echo "$stale" >&2; exit 1
fi

# Count total runs.
TOTAL=0
for cfg in "${CONFIGS[@]}"; do read -r _k _q tps <<<"$cfg"; for _t in $tps; do TOTAL=$((TOTAL + REPS)); done; done
T_START=$(date +%s); DONE=0

log "============================================================"
log "N=1 single-stream ANCHOR — small/mid tier (Tier A, n=$REPS)"
log "Configs: ${#CONFIGS[@]} models  |  total runs: $TOTAL  |  out: <key>/n1-anchor/"
log "============================================================"
progress "SWEEP_START total_runs=$TOTAL"

for cfg in "${CONFIGS[@]}"; do
    read -r KEY QUANT TPS <<<"$cfg"
    OUT="$RESULTS_ROOT/$KEY/n1-anchor"
    mkdir -p "$OUT"
    log "################  MODEL: $KEY ($QUANT)  TP={$TPS}  ################"
    progress "MODEL_BEGIN key=$KEY quant=$QUANT"
    for TP in $TPS; do
        for ((REP=0; REP<REPS; REP++)); do
            NAME="$(printf '%s-tp%d-n1-r%02d' "$QUANT" "$TP" "$REP")"
            DONE=$((DONE + 1))
            log "[$DONE/$TOTAL] $KEY/$NAME"
            RUN_START=$(date +%s)
            bash "$KILL_PORT" 8100 >/dev/null 2>&1 || true
            if python3 "$BENCH" "$KEY" "$TP" 1 \
                --quant "$QUANT" --max-len "$MAX_LEN" --util "$UTIL" \
                --name "$NAME" --out-dir "$OUT" --interval 1.0 \
                --timeout "$PER_RUN_TIMEOUT_S" >> "$ORCH_LOG" 2>&1
            then log "  OK   $KEY/$NAME ($(( $(date +%s) - RUN_START ))s)"
            else log "  FAIL $KEY/$NAME ($(( $(date +%s) - RUN_START ))s) — see $OUT/${NAME}-bench.log"; fi
            bash "$KILL_PORT" 8100 >/dev/null 2>&1 || true
            ELAPSED=$(( $(date +%s) - T_START )); AVG=$(( ELAPSED / DONE ))
            progress "RUN_DONE key=$KEY name=$NAME done=$DONE/$TOTAL eta_s=$(( AVG * (TOTAL - DONE) ))"
            (( DONE < TOTAL )) && sleep "$COOLDOWN_S"
        done
    done
    progress "MODEL_COMPLETE key=$KEY"
done

T_TOTAL=$(( $(date +%s) - T_START ))
log "============================================================"
log "N=1 anchor (small/mid) complete. Wall: ${T_TOTAL}s ($((T_TOTAL/60)) min). Runs: $DONE/$TOTAL"
log "============================================================"
echo "DONE $(date -Iseconds) runs=$DONE/$TOTAL wall_s=$T_TOTAL" > "$SENTINEL"
progress "SWEEP_END wall_s=$T_TOTAL runs=$DONE/$TOTAL"
log "Sentinel: $SENTINEL"
