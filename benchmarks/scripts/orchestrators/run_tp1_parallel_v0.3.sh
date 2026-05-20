#!/usr/bin/env bash
# =============================================================================
# run_tp1_parallel_v0.3.sh — idle-GPU task VARIANT C: #3 throughput sweep in the
# co-located TP=1‖TP=1 configuration for the navimed-umb v0.3 PASS suite.
#
# Complements run_idle_gpu_v0.3.sh (which does Phase A max-context + Phase B
# sequential TP=2/TP=1). This orchestrator pairs models two-at-a-time: each pair
# runs two vLLM engines simultaneously, each TP=1, each pinned to one physical
# R9700 (HIP_VISIBLE_DEVICES 0 and 1). ~2x faster than serial TP=1 and captures
# memory-bus / power-budget contention (kyuz0 models.py pattern TP:[1,2]).
#
# SCOPE: only models that fit on a single 32 GB R9700. qwen36-27b-fp8 (29 GB
# weights) is EXCLUDED — no KV-cache room on one card; it stays TP=2-only.
# 10 PASS models -> 5 pairs.
#
# METHODOLOGY-compliant: env via scripts/_env.sh (§3.1), enforce_eager (§3.2),
# cleanup via scripts/kill_port.sh setsid (NEVER pkill -f). TWO ports: 8101 &
# 8102. Outputs in benchmarks/results/<model>/tp1-parallel/ (gitignored §11).
# No git commit. Per-model crash -> finding, sweep continues.
#
# Usage:  bash benchmarks/scripts/orchestrators/run_tp1_parallel_v0.3.sh
# =============================================================================
set +e   # survive per-pair failures, continue suite

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO" || exit 1

RUNNERS="$REPO/benchmarks/scripts/runners"
PROGRESS="$REPO/logs/tp1-parallel-v0.3-progress.log"
mkdir -p "$(dirname "$PROGRESS")"

# Pairs: "gpu0_spec ## gpu1_spec", each spec = "model_dir|quant|extra".
# Sizes balanced within each pair so neither card idles waiting for the other.
#   ~5.8 GB: bielik-11b-v23-awq, bielik-11b-v30-instruct-awq
#   ~9  GB:  bielik-4.5b-v30
#   ~15 GB:  llama-pllum-8b-instruct, qwen25-7b-instruct
#   ~21 GB:  bielik-11b-v23, bielik-11b-v30, bielik-pl-11b-v30-instruct
#   ~23 GB:  pllum-12b-chat, mistral-nemo-instruct-2407
PAIRS=(
  "bielik-11b-v23-awq|awq| ## bielik-11b-v30-instruct-awq|compressed-tensors|"
  "bielik-4.5b-v30|bf16| ## qwen25-7b-instruct|fp16|"
  "llama-pllum-8b-instruct|bf16| ## bielik-11b-v23|fp16|"
  "bielik-11b-v30|bf16| ## bielik-pl-11b-v30-instruct|bf16|"
  "pllum-12b-chat|bf16| ## mistral-nemo-instruct-2407|bf16|"
)

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$PROGRESS"; }

# shellcheck source=/dev/null
source "$REPO/scripts/_env.sh"
set +euo pipefail   # _env.sh sets -euo; relax so per-pair failures don't abort

log "================================================================"
log "TP=1‖TP=1 PARALLEL SWEEP v0.3 START — ${#PAIRS[@]} pairs (10 models)"
log "vLLM $(python3 -c 'import vllm;print(vllm.__version__)' 2>/dev/null) | transformers $(python3 -c 'import transformers;print(transformers.__version__)' 2>/dev/null)"
log "EXCLUDED (too large for single 32 GB R9700): qwen36-27b-fp8 (TP=2-only)"
log "================================================================"

T_GLOBAL=$(date +%s)

bash "$REPO/scripts/kill_port.sh" 8101 >/dev/null 2>&1
bash "$REPO/scripts/kill_port.sh" 8102 >/dev/null 2>&1

idx=0
for pair in "${PAIRS[@]}"; do
  idx=$((idx+1))
  g0="${pair%% ## *}"
  g1="${pair##* ## }"
  log ""
  log "########## PAIR $idx/${#PAIRS[@]} — GPU0:[$g0]  ‖  GPU1:[$g1] ##########"
  ta=$(date +%s)
  bash "$REPO/scripts/kill_port.sh" 8101 >/dev/null 2>&1
  bash "$REPO/scripts/kill_port.sh" 8102 >/dev/null 2>&1
  python3 "$RUNNERS/throughput_sweep_tp1_parallel.py" \
    --gpu0 "$g0" --gpu1 "$g1" 2>&1 | tee -a "$PROGRESS"
  tb=$(date +%s)
  log "########## PAIR $idx DONE in $(( (tb-ta)/60 )) min ##########"
  bash "$REPO/scripts/kill_port.sh" 8101 >/dev/null 2>&1
  bash "$REPO/scripts/kill_port.sh" 8102 >/dev/null 2>&1
done

T_END=$(date +%s)
log ""
log "================================================================"
log "TP=1‖TP=1 PARALLEL SWEEP COMPLETE — total $(( (T_END-T_GLOBAL)/60 )) min"
log "  Outputs: benchmarks/results/<model>/tp1-parallel/{results_table.csv,SUMMARY.md}"
log "================================================================"
