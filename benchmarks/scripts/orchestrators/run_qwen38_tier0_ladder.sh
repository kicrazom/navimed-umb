#!/usr/bin/env bash
# NaviMed-UMB Phase 2 — Qwen 3.8 27B (BF16), Tier 0 (single run per cell), TP=2 only.
# Same protocol as run_bielik_v31_tier0_ladder.sh except max_model_len 1024 and
# gpu_memory_utilization 0.95: the only BF16 setting that fits 2x 32 GB (as for qwen36-27b).
# N ladder: METHODOLOGY 1.9 CANON_N. Output: benchmarks/results/qwen38-27b/thermal-runs/ (gitignored).
# Usage: systemd-inhibit --what=sleep:idle --mode=block bash benchmarks/scripts/orchestrators/run_qwen38_tier0_ladder.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

KEY="qwen38-27b"
RESULT_DIR="qwen38-27b"
QUANT="bf16"
MODEL_PATH="/home/mozarcik/models/qwen3.8-27b"
HF_NAME="Qwen/Qwen3.8-27B"
MAX_LEN=1024
UTIL=0.95
N_LADDER=(1 10 25 50 100 200 500 1000)
TP_LADDER=(2)
REPS=1
COOLDOWN_S=30
PER_RUN_TIMEOUT_S=1800

BENCH="$REPO_ROOT/benchmarks/scripts/instrumentation/bench_with_thermals.py"
FINALIZE="$REPO_ROOT/benchmarks/scripts/analysis/finalize_phase2_generic.py"
OUT_DIR="$REPO_ROOT/benchmarks/results/$RESULT_DIR/thermal-runs"
LOG_DIR="$REPO_ROOT/benchmarks/results/_qwen38_tier0_logs"
LOG="$LOG_DIR/orchestrator.log"
PROGRESS="/tmp/qwen38-tier0-progress.log"
mkdir -p "$OUT_DIR" "$LOG_DIR"

for f in "$LOG" "$PROGRESS"; do
  {
    echo "# EMBARGO=YES — paper-bound until decided otherwise (METHODOLOGY §11.2/§11.3)"
    echo "# Sweep: Qwen 3.8 27B BF16, Tier 0, TP=2, N={${N_LADDER[*]}}, reps=$REPS"
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
