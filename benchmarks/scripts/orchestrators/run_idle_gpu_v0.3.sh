#!/usr/bin/env bash
# =============================================================================
# run_idle_gpu_v0.3.sh — idle-GPU task: #4 max-context probe + #3 throughput
# sweep for the navimed-umb v0.3 PASS suite (11 models).
#
# Sequential by design (single GPU pair, no collision):
#   PHASE A: probe_max_context.py for every PASS model
#   PHASE B: throughput_sweep_v0.3.py for every PASS model
#
# METHODOLOGY-compliant: env via scripts/_env.sh (§3.1), enforce_eager (§3.2),
# kill via scripts/kill_port.sh setsid (NEVER pkill -f). Outputs land in
# benchmarks/results/ (fully gitignored — embargo §11). No git commit.
#
# Per model that crashes: logged as finding, sweep continues.
#
# Usage:  bash benchmarks/scripts/orchestrators/run_idle_gpu_v0.3.sh
# =============================================================================
set +e   # survive per-model failures, continue suite

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$REPO" || exit 1

RUNNERS="$REPO/benchmarks/scripts/runners"
PROGRESS="$REPO/logs/idle-gpu-v0.3-progress.log"
mkdir -p "$(dirname "$PROGRESS")"

# format: "model_dir|tp|quant|extra_flags"
# 11 PASS models confirmed from environment/sanity-tests/*.json verdicts.
# qwen36-27b-fp8 = Qwen3_5ForConditionalGeneration (hybrid attn) → enforce-eager
# is already suite-default; no extra needed (enforce_eager forced in harness).
MODELS=(
  "bielik-4.5b-v30|1|bf16|"
  "bielik-11b-v23|1|fp16|"
  "bielik-11b-v23-awq|1|awq|"
  "bielik-11b-v30|1|bf16|"
  "bielik-pl-11b-v30-instruct|1|bf16|"
  "llama-pllum-8b-instruct|1|bf16|"
  "pllum-12b-chat|1|bf16|"
  "qwen25-7b-instruct|1|fp16|"
  "bielik-11b-v30-instruct-awq|1|compressed-tensors|"
  "mistral-nemo-instruct-2407|1|bf16|"
  "qwen36-27b-fp8|2|fp8|"
)

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$PROGRESS"; }

# shellcheck source=/dev/null
source "$REPO/scripts/_env.sh"
set +euo pipefail   # _env.sh sets -euo; relax so per-model failures don't abort

log "================================================================"
log "IDLE-GPU v0.3 START — ${#MODELS[@]} models | PHASE A (max-ctx) + PHASE B (throughput)"
log "vLLM $(python3 -c 'import vllm;print(vllm.__version__)' 2>/dev/null) | transformers $(python3 -c 'import transformers;print(transformers.__version__)' 2>/dev/null)"
log "================================================================"

T_GLOBAL=$(date +%s)

# ---------------------------------------------------------------------------
# PHASE A — max-context probing
# ---------------------------------------------------------------------------
log ""
log "########## PHASE A — #4 max-context probing ##########"
for entry in "${MODELS[@]}"; do
  IFS='|' read -r mdir tp quant extra <<< "$entry"
  log "--- [A] $mdir (TP=$tp $quant) ---"
  ta=$(date +%s)
  bash "$REPO/scripts/kill_port.sh" 8100 >/dev/null 2>&1
  python3 "$RUNNERS/probe_max_context.py" "$mdir" "$tp" \
    --quant "$quant" --extra "$extra" 2>&1 | tee -a "$PROGRESS"
  tb=$(date +%s)
  log "--- [A] $mdir DONE in $((tb-ta))s ---"
  bash "$REPO/scripts/kill_port.sh" 8100 >/dev/null 2>&1
done

T_A=$(date +%s)
log ""
log "########## PHASE A complete — $(( (T_A-T_GLOBAL)/60 )) min ##########"

# ---------------------------------------------------------------------------
# PHASE B — throughput sweeps
# ---------------------------------------------------------------------------
log ""
log "########## PHASE B — #3 throughput sweeps ##########"
for entry in "${MODELS[@]}"; do
  IFS='|' read -r mdir tp quant extra <<< "$entry"
  log "--- [B] $mdir (TP=$tp $quant) ---"
  ta=$(date +%s)
  bash "$REPO/scripts/kill_port.sh" 8100 >/dev/null 2>&1
  python3 "$RUNNERS/throughput_sweep_v0.3.py" "$mdir" "$tp" \
    --quant "$quant" --extra "$extra" 2>&1 | tee -a "$PROGRESS"
  tb=$(date +%s)
  log "--- [B] $mdir DONE in $((tb-ta))s ---"
  bash "$REPO/scripts/kill_port.sh" 8100 >/dev/null 2>&1
done

T_END=$(date +%s)
log ""
log "================================================================"
log "IDLE-GPU v0.3 COMPLETE"
log "  Phase A: $(( (T_A-T_GLOBAL)/60 )) min"
log "  Phase B: $(( (T_END-T_A)/60 )) min"
log "  Total:   $(( (T_END-T_GLOBAL)/60 )) min"
log "  Max-ctx records: benchmarks/results/hardware_envelope/*_maxctx.json"
log "  Throughput:      benchmarks/results/<model>/{results_table.csv,SUMMARY.md}"
log "================================================================"
