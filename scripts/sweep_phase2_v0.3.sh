#!/usr/bin/env bash
# sweep_phase2_v0.3.sh
# Phase 2 sweep — model refresh + new contenders + multimodal probe
# Target HW: 2× AMD Radeon AI PRO R9700 (64 GB VRAM), ROCm 7.2.0, vLLM 0.19.0+rocm721
# Generated: 2026-05-17

# Single source of env per scripts/_env.sh (ROCm §3.1 + venv + XDG guard)
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"

MODELS_DIR="${MODELS_DIR:-$HOME/models}"
LOG_DIR="${LOG_DIR:-$HOME/Vaults-main/10_Projekty/0001-navimed-umb/logs/phase2_v0.3}"
PORT="${PORT:-8000}"
mkdir -p "$LOG_DIR"

# Common vLLM flags — keep consistent across runs for reproducibility
# Note: --disable-log-requests removed in vLLM 0.19 (silently rejected as
# unrecognized argument). Verified empirically during bielik-11b-v30 sanity
# 2026-05-17. Use --uvicorn-log-level=warning instead if needed.
COMMON_FLAGS=(
  --port "$PORT"
  --max-model-len 8192
  --gpu-memory-utilization 0.9
)

# gfx1201 stability: TP=2 needs enforce_eager for hybrid-attention families
# (Qwen 3.5/3.6, Kimi-Linear). Cost: -15-25% throughput vs graph mode.
# Per-call --enforce-eager applied inline (see serve_examples below).

download() {
  local repo="$1" dest="$2"
  if [[ -d "$MODELS_DIR/$dest" && -f "$MODELS_DIR/$dest/config.json" ]]; then
    echo "[skip] $dest already present"
    return
  fi
  echo "[pull] $repo -> $dest"
  if ! huggingface-cli download "$repo" --local-dir "$MODELS_DIR/$dest" --local-dir-use-symlinks False; then
    echo "[fail] $repo — check https://huggingface.co/$repo (gated repo? user mozarcik needs 'Request access')" >&2
    return 1
  fi
}

stop_vllm() {
  local pidfile="$1"
  if [[ -f "$pidfile" ]]; then
    local pid; pid=$(cat "$pidfile")
    pkill -P "$pid" 2>/dev/null || true
    kill "$pid" 2>/dev/null || true
    rm -f "$pidfile"
  fi
}

serve() {
  local model_path="$1" tp="$2" extra_flags="${3:-}"
  local name; name=$(basename "$model_path")
  local pidfile="$LOG_DIR/vllm-${name}.pid"
  local logfile="$LOG_DIR/${name}.log"

  echo "[serve] $name (TP=$tp) -> log: $logfile, pidfile: $pidfile"

  # shellcheck disable=SC2086  # intentional word splitting of extra_flags
  vllm serve "$model_path" \
    "${COMMON_FLAGS[@]}" \
    --tensor-parallel-size "$tp" \
    $extra_flags \
    >"$logfile" 2>&1 &
  echo $! > "$pidfile"

  # shellcheck disable=SC2064  # intentional: expand pidfile NOW per-invocation
  trap "stop_vllm '$pidfile'" RETURN

  # Wait for vLLM ready (max 5 min)
  local elapsed=0
  until curl -sf "http://localhost:$PORT/v1/models" >/dev/null 2>&1; do
    sleep 2; elapsed=$((elapsed + 2))
    if (( elapsed > 300 )); then
      echo "[fail] $name didn't become ready in 5 min" >&2
      return 1
    fi
  done
  echo "[ready] $name @ port $PORT (after ${elapsed}s)"
}

# ============================================================================
# PHASE A — refresh existing models (goes to current Phase 2 paper)
# Embargo: YES — same as Phase 2 paper, do not publish numbers pre-acceptance
# ============================================================================
phase_a_download() {
  # HF repo identifiers — flagged by detect-secrets as high-entropy strings (false positive)
  download "speakleash/Bielik-PL-11B-v3.0-Instruct"            "bielik-pl-11b-v30-instruct"     # pragma: allowlist secret
  download "speakleash/Bielik-11B-v3.0-Instruct-awq"           "bielik-11b-v30-instruct-awq"    # pragma: allowlist secret
  download "CYFRAGOVPL/Llama-PLLuM-70B-base-250801"            "llama-pllum-70b-base-250801"    # pragma: allowlist secret
  download "CYFRAGOVPL/Llama-PLLuM-70B-chat-250801"            "llama-pllum-70b-chat-250801"    # pragma: allowlist secret
  download "Qwen/Qwen3.5-9B"                                   "qwen3.5-9b"
}

phase_a_serve_examples() {
  # Bielik PL 11B v3 (BF16) — TP=1 fits in 32 GB easily, TP=2 for headroom
  serve "$MODELS_DIR/bielik-pl-11b-v30-instruct" 1

  # Bielik 11B v3 AWQ Q4 — TP=1, single-card test for direct A/B vs v2.3-awq baseline
  serve "$MODELS_DIR/bielik-11b-v30-instruct-awq" 1

  # Llama-PLLuM 70B base/chat refresh — TP=2 mandatory, AWQ/BF16 depending on what's available
  serve "$MODELS_DIR/llama-pllum-70b-chat-250801" 2

  # Qwen 3.5-9B — TP=1 baseline replacing qwen25-7b-instruct
  # NOTE: hybrid attention → enforce_eager=True
  serve "$MODELS_DIR/qwen3.5-9b" 1 "--enforce-eager"
}

# ============================================================================
# PHASE B — new contenders (follow-up paper, internal benchmark first)
# Embargo: SEPARATE — different manuscript, can run independently
# ============================================================================
phase_b_download() {
  download "moonshotai/Kimi-Dev-72B"                           "kimi-dev-72b"
  download "moonshotai/Kimi-Linear-48B-A3B-Instruct"           "kimi-linear-48b-a3b-instruct"
  download "Qwen/Qwen3.6-35B-A3B-FP8"                          "qwen3.6-35b-a3b-fp8"
}

phase_b_serve_examples() {
  # Kimi-Dev-72B (Qwen2.5-72B base, dense) — TP=2, head-to-head vs qwen25-72b-awq
  # No AWQ version on HF as of 2026-05-17 → either BF16 (won't fit 64 GB) or quantize locally
  # Quick win: serve BF16 with --quantization awq_marlin after running AutoAWQ ourselves
  serve "$MODELS_DIR/kimi-dev-72b" 2 "--quantization awq_marlin --enforce-eager"

  # Kimi-Linear 48B A3B (MoE, linear attention) — TP=2, eager mandatory for linear kernel
  # gotcha: prefix caching may interact badly with linear attention — start without it
  serve "$MODELS_DIR/kimi-linear-48b-a3b-instruct" 2 \
    "--enforce-eager --no-enable-prefix-caching"

  # Qwen 3.6 35B A3B FP8 — MoE benchmark on gfx1201
  # gotcha: FP8 kernels slower than BF16 on R9700 (~75% diff) until AITER lands.
  # Run BOTH FP8 and BF16 for comparison.
  serve "$MODELS_DIR/qwen3.6-35b-a3b-fp8" 2 "--enforce-eager"
}

# ============================================================================
# PHASE C — multimodal probe (Broncho-Nome scoping, follow-up paper)
# Embargo: SEPARATE — explicitly tagged "VL" in benchmark dataset
# ============================================================================
phase_c_download() {
  download "moonshotai/Kimi-VL-A3B-Thinking-2506"              "kimi-vl-a3b-thinking-2506"
  download "meta-llama/Llama-4-Scout-17B-16E-Instruct"         "llama-4-scout-17b-16e-instruct"
}

phase_c_serve_examples() {
  # Kimi-VL A3B Thinking — vision + reasoning, small MoE → TP=1 sufficient
  serve "$MODELS_DIR/kimi-vl-a3b-thinking-2506" 1 \
    "--trust-remote-code --enforce-eager"

  # Llama-4-Scout 17B/16E — natively multimodal, MoE → TP=2
  # gotcha: vLLM Llama-4 support stabilized in 0.18+, verify version
  serve "$MODELS_DIR/llama-4-scout-17b-16e-instruct" 2 "--enforce-eager"
}

# ============================================================================
# Entry point — dispatch by phase
# ============================================================================
case "${1:-}" in
  download-a) phase_a_download ;;
  download-b) phase_b_download ;;
  download-c) phase_c_download ;;
  download-all) phase_a_download; phase_b_download; phase_c_download ;;
  serve-a) phase_a_serve_examples ;;
  serve-b) phase_b_serve_examples ;;
  serve-c) phase_c_serve_examples ;;
  *)
    cat <<EOF
Usage: $0 {download-a|download-b|download-c|download-all|serve-a|serve-b|serve-c}

Download targets land in:  $MODELS_DIR
Serve logs land in:        $LOG_DIR

Run order for full sweep:
  $0 download-all
  $0 serve-a    # Phase 2 paper refresh
  $0 serve-b    # follow-up: new contenders
  $0 serve-c    # follow-up: multimodal probe

Serve commands above are SINGLE-MODEL examples (sequential).
For actual N-points sweep (10..1000), integrate with hvezda.py harness.
EOF
    exit 1
    ;;
esac
