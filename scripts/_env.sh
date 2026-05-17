#!/usr/bin/env bash
# scripts/_env.sh
# Single source of mandatory environment for all NaviMed-UMB / LLM Wiki scripts.
# Every script must: source "$(dirname "$0")/_env.sh"

set -euo pipefail

# === XDG snap guard (defensive, repeat from .bashrc for non-interactive) ===
if [[ "${XDG_CACHE_HOME:-}" == */snap/* ]]; then
    export XDG_CACHE_HOME="$HOME/.cache"
    export HF_HOME="$HOME/.cache/huggingface"
fi

# === ROCm / vLLM mandatory per METHODOLOGY.md §3.1 ===
unset PYTORCH_ALLOC_CONF
export VLLM_ROCM_USE_AITER=0
export AMD_SERIALIZE_KERNEL=1
export HIP_LAUNCH_BLOCKING=1
export ROCR_VISIBLE_DEVICES=0,1

# === Venv guard ===
export VLLM_VENV="$HOME/venvs/vllm"
if [[ ! -d "$VLLM_VENV" ]]; then
    echo "ERROR: VLLM_VENV not found at $VLLM_VENV" >&2
    exit 1
fi
export PATH="$VLLM_VENV/bin:$PATH"

# Sanity
if ! command -v huggingface-cli &>/dev/null; then
    echo "ERROR: huggingface-cli not on PATH after venv activation" >&2
    exit 1
fi

# === Source ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAVIMED_ROOT="$(dirname "$SCRIPT_DIR")"
export NAVIMED_ROOT

echo "[_env.sh] sourced: ROCm vars set, VLLM_VENV active, NAVIMED_ROOT=$NAVIMED_ROOT" >&2
