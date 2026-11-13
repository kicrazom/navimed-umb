#!/usr/bin/env bash
# Vehicle-drift control, 2026-11-13. Re-measures Bielik-PL-11B-v3.0-Instruct (BF16), an
# architecture-identical sibling of Bielik 11B v3.0/v3.1, at cells measured in June 2026
# (BIOS 1715 era), with the same protocol. If today's numbers are lower by the same few
# percent as v3.1 vs v3.0, the v3.1 gap is vehicle drift, not the model.
# Cells: TP=1, N={25,100,500}, 2 reps. Output kept apart from the Tier-A data:
#   benchmarks/results/bielik-pl-11b-v30-instruct/bridging-2026-11-13/   (EMBARGOED, gitignored)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO_ROOT"
# shellcheck source=/dev/null
source "$REPO_ROOT/scripts/_env.sh"

KEY="bielik-pl-11b-v30-instruct"; QUANT="bf16"; TP=1; N_LADDER=(25 100 500); REPS=2
BENCH="$REPO_ROOT/benchmarks/scripts/instrumentation/bench_with_thermals.py"
OUT_DIR="$REPO_ROOT/benchmarks/results/$KEY/bridging-2026-11-13"
LOG="$OUT_DIR/orchestrator.log"
mkdir -p "$OUT_DIR"
echo "# EMBARGO=YES — paper-bound (METHODOLOGY §11.2/§11.3). Drift control $(date -Iseconds)" > "$LOG"
log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

stale="$(pgrep -af 'vllm serve|run_concurrent.py' 2>/dev/null || true)"
[[ -z "$stale" ]] || { echo "ERROR: stale vllm/run_concurrent processes:" >&2; echo "$stale" >&2; exit 1; }
log "vLLM $(python3 -c 'import vllm; print(vllm.__version__)'); kernel cmdline: $(sed -E 's/(root=UUID=|BOOT_IMAGE=)[^ ]*/\1<masked>/g' /proc/cmdline)"

for N in "${N_LADDER[@]}"; do
  for ((REP=0; REP<REPS; REP++)); do
    NAME="$(printf '%s-tp%d-n%d-r%02d' "$QUANT" "$TP" "$N" "$REP")"; RS=$(date +%s)
    if python3 "$BENCH" "$KEY" "$TP" "$N" --quant "$QUANT" --max-len 8192 --util 0.90 \
         --name "$NAME" --out-dir "$OUT_DIR" --interval 1.0 --timeout 1800 >> "$LOG" 2>&1; then
      log "OK   $NAME ($(( $(date +%s) - RS ))s)"
    else
      log "FAIL $NAME ($(( $(date +%s) - RS ))s)"
    fi
    sleep 30
  done
done
log "CONTROL DONE"
