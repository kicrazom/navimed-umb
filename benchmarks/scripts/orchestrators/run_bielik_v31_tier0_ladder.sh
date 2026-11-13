#!/usr/bin/env bash
# NaviMed-UMB Phase 2 — Bielik 11B v3.1 Instruct (BF16), Tier 0 (single run per cell).
#
# Purpose: first look at v3.1 generation speed against the bielik-11b-v30 golden
# reference, on the same vehicle and the same protocol. Tier 0 = exploratory
# (METHODOLOGY §7.4): one run per (TP, N), no statistics; promote to Tier A
# (REPS=10) before any claim.
#
# Mirrors run_bielik_tierA_n10_sweep.sh except:
#   - one model: bielik-11b-v31 → /home/mozarcik/models/bielik-11b-v31-instruct
#   - N ladder: METHODOLOGY 1.9 canonical CANON_N = {1,10,25,50,100,200,500,1000}
#   - REPS=1
# Unchanged: TP {1,2}, max_model_len 8192, gpu_memory_utilization 0.90,
# 30 s cooldown, §6 standard workload (8 templates × 20 topics, max_tokens=128),
# 1 Hz sampler, vLLM 0.19.0 offline LLM.generate path, env floor from _env.sh.
#
# Output (gitignored, EMBARGOED §11.2/§11.3):
#   benchmarks/results/bielik-11b-v31/thermal-runs/bf16-tp{1,2}-n{N}-r00-*
#
# Usage from repo root:
#   systemd-inhibit --what=sleep:idle --who=navimed-bielik-v31 \
#       --why="Bielik v3.1 Tier-0 ladder" --mode=block \
#       bash benchmarks/scripts/orchestrators/run_bielik_v31_tier0_ladder.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

KEY="bielik-11b-v31"
RESULT_DIR="bielik-11b-v31"
QUANT="bf16"
MODEL_PATH="/home/mozarcik/models/bielik-11b-v31-instruct"
HF_NAME="speakleash/Bielik-11B-v3.1-Instruct"
MAX_LEN=8192
UTIL=0.90
N_LADDER=(1 10 25 50 100 200 500 1000)
TP_LADDER=(1 2)
REPS=1
COOLDOWN_S=30
PER_RUN_TIMEOUT_S=1800

BENCH="$REPO_ROOT/benchmarks/scripts/instrumentation/bench_with_thermals.py"
FINALIZE="$REPO_ROOT/benchmarks/scripts/analysis/finalize_phase2_generic.py"
OUT_DIR="$REPO_ROOT/benchmarks/results/$RESULT_DIR/thermal-runs"
LOG_DIR="$REPO_ROOT/benchmarks/results/_bielik_v31_tier0_logs"
LOG="$LOG_DIR/orchestrator.log"
PROGRESS="/tmp/bielik-v31-tier0-progress.log"
mkdir -p "$OUT_DIR" "$LOG_DIR"

for f in "$LOG" "$PROGRESS"; do
  {
    echo "# EMBARGO=YES — paper-bound (Polish model, METHODOLOGY §11.2/§11.3)"
    echo "# Sweep: Bielik 11B v3.1 BF16, Tier 0, TP={1,2}, N={${N_LADDER[*]}}, reps=$REPS"
    echo "# Started: $(date -Iseconds)"
    echo "# DO NOT COMMIT raw thermal-runs/ until paper acceptance."
  } > "$f"
done
log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }
progress() { echo "[$(date -Iseconds)] $*" >> "$PROGRESS"; }

[[ -f "$MODEL_PATH/config.json" ]] || { echo "ERROR: model not found at $MODEL_PATH" >&2; exit 1; }
stale="$(pgrep -af 'vllm serve|run_concurrent.py' 2>/dev/null || true)"
[[ -z "$stale" ]] || { echo "ERROR: stale vllm/run_concurrent processes — refusing to start:" >&2; echo "$stale" >&2; exit 1; }
python3 -c "import vllm; assert vllm.__version__.startswith('0.19.0'), vllm.__version__"
log "vLLM $(python3 -c 'import vllm; print(vllm.__version__)'); kernel cmdline: $(sed -E 's/(root=UUID=|BOOT_IMAGE=)[^ ]*/\1<masked>/g' /proc/cmdline)"

TOTAL=$(( ${#TP_LADDER[@]} * ${#N_LADDER[@]} * REPS )); DONE=0; T0=$(date +%s)
for TP in "${TP_LADDER[@]}"; do
  for N in "${N_LADDER[@]}"; do
    for ((REP=0; REP<REPS; REP++)); do
      NAME="$(printf '%s-tp%d-n%d-r%02d' "$QUANT" "$TP" "$N" "$REP")"
      DONE=$((DONE + 1)); RS=$(date +%s)
      log "[$DONE/$TOTAL] start $KEY/$NAME"
      if python3 "$BENCH" "$KEY" "$TP" "$N" --quant "$QUANT" --max-len "$MAX_LEN" --util "$UTIL" \
           --name "$NAME" --out-dir "$OUT_DIR" --interval 1.0 --timeout "$PER_RUN_TIMEOUT_S" >> "$LOG" 2>&1; then
        log "  OK   $KEY/$NAME ($(( $(date +%s) - RS ))s wall)"
      else
        log "  FAIL $KEY/$NAME ($(( $(date +%s) - RS ))s wall) — see $OUT_DIR/$NAME-bench.log"
      fi
      EL=$(( $(date +%s) - T0 ))
      progress "PROGRESS done=$DONE/$TOTAL tp=$TP n=$N elapsed_s=$EL eta_s=$(( EL * (TOTAL - DONE) / DONE ))"
      (( DONE < TOTAL )) && sleep "$COOLDOWN_S"
    done
  done
done
log "SWEEP DONE in $(( $(date +%s) - T0 ))s"
progress "SWEEP_COMPLETE"

if [[ -f "$FINALIZE" ]]; then
  if python3 "$FINALIZE" --results-dir "$REPO_ROOT/benchmarks/results/$RESULT_DIR" --model-label "$KEY" \
    --model-name "$HF_NAME" --quant "$QUANT" --max-len "$MAX_LEN" --util "$UTIL" >> "$LOG" 2>&1; then
    log "Finalize OK — benchmarks/results/$RESULT_DIR/SUMMARY.md"
  else
    log "WARN: finalize failed; raw data in $OUT_DIR"
  fi
fi
