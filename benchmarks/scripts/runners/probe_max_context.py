#!/usr/bin/env python3
"""
probe_max_context.py — KROK A (#4): max-context probing for navimed-umb v0.3.

For ONE model, binary-search the largest ``max_model_len`` that loads and serves
a single sanity prompt stably on the navimed stack (vLLM 0.19.0+rocm721, gfx1201).

Method (METHODOLOGY §5.1 Phase 1 — hardware envelope):
  - Probe is a load + single sanity-prompt generation, just like batch_sanity.
  - max_model_len is bounded above by the model's own max_position_embeddings.
  - Binary search over a token ladder; success = vLLM constructs LLM(), KV cache
    pool > 0, and one sanity prompt produces non-empty coherent content.
  - enforce_eager=True suite-wide conservative default (§3.2); mandatory for the
    Qwen3.5/3.6 hybrid-attention family — qwen36-27b-fp8 is Qwen3_5ForConditionalGeneration.
  - gpu_memory_utilization fixed at 0.90 (suite default). The probe answers
    "max context at the standard util", not "max context at any util".

Each probe attempt runs in a fresh subprocess (one LLM() per process — vLLM TP
worker model re-import requires process isolation, and a failed/OOM construction
leaves the engine unrecoverable in-process).

Output: benchmarks/results/hardware_envelope/<model>_maxctx.json   (PUBLIC §11.1)

Usage:
    python probe_max_context.py <model_dir> <tp> [--quant Q] [--extra "flags"]

Embargo: PUBLIC — envelope data §11.1 (load y/n, KV tokens, max_concurrency).
Author: Claude Code (navimed-umb idle-GPU subagent), 2026-05-20.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

# vLLM engine logs KV pool + max_concurrency at init; attribute path is
# version-fragile, so parse log lines (same as batch_sanity_v0.3.sh).
RE_KV = re.compile(r"GPU KV cache size:\s*([\d,]+)\s*tokens")
RE_MAXC = re.compile(r"Maximum concurrency for [\d,]+ tokens per request:\s*([\d.]+)x")

REPO = Path(__file__).resolve().parents[3]
MODELS_DIR = Path.home() / "models"
ENVELOPE_DIR = REPO / "benchmarks" / "results" / "hardware_envelope"
KILL_PORT = REPO / "scripts" / "kill_port.sh"

SANITY_PROMPT = (
    "Rozwiń skrót PEEP w kontekście wentylacji mechanicznej i wyjaśnij jego rolę."
)
UTIL = 0.90
# Token ladder — candidate max_model_len values. Binary search picks within
# [floor, ceil(model max_position_embeddings)].
LADDER = [2048, 4096, 8192, 16384, 24576, 32768, 49152, 65536, 98304, 131072]
PROBE_TIMEOUT_S = 600  # per construct+sanity attempt; large ctx alloc is slow


def stack_versions() -> dict:
    try:
        import torch
        import vllm

        return {
            "vllm_version": vllm.__version__,
            "torch_version": torch.__version__,
            "torch_hip_version": getattr(torch.version, "hip", None),
        }
    except Exception:
        return {}


def model_max_pos(model_path: Path) -> int:
    """Return max_position_embeddings (handles nested text_config)."""
    cfg = json.loads((model_path / "config.json").read_text())
    if "max_position_embeddings" in cfg:
        return int(cfg["max_position_embeddings"])
    tc = cfg.get("text_config") or {}
    if "max_position_embeddings" in tc:
        return int(tc["max_position_embeddings"])
    return 32768  # conservative fallback


# ---------------------------------------------------------------------------
# Child-process probe: one LLM() construction + one sanity prompt.
# Invoked as `python probe_max_context.py --child ...`.
# Prints a single JSON line to stdout: {"loaded":bool, ...}.
# ---------------------------------------------------------------------------
def run_child(model_path: str, tp: int, max_len: int, extra: str) -> int:
    result = {
        "loaded": False,
        "error_class": None,
        "error": None,
        "load_time_s": None,
        "kv_cache_tokens": None,
        "max_concurrency": None,
        "sanity_ok": False,
        "sanity_throughput_tok_s": None,
        "sanity_preview": None,
    }
    try:
        from vllm import LLM, SamplingParams

        kwargs = dict(
            model=model_path,
            max_model_len=max_len,
            gpu_memory_utilization=UTIL,
            enforce_eager=True,
            tensor_parallel_size=tp,
        )
        # extra: parse known flags relevant to construction
        if "--enforce-eager" in extra:
            kwargs["enforce_eager"] = True
        if "awq_marlin" in extra:
            kwargs["quantization"] = "awq_marlin"
        if "--no-enable-prefix-caching" in extra:
            kwargs["enable_prefix_caching"] = False

        t0 = time.time()
        llm = LLM(**kwargs)
        result["load_time_s"] = round(time.time() - t0, 2)
        result["loaded"] = True

        # KV cache pool + max_concurrency from engine config
        try:
            ec = llm.llm_engine.cache_config
            num_blocks = getattr(ec, "num_gpu_blocks", None)
            block_size = getattr(ec, "block_size", None)
            if num_blocks and block_size:
                kv_tokens = int(num_blocks) * int(block_size)
                result["kv_cache_tokens"] = kv_tokens
                result["max_concurrency"] = round(kv_tokens / max_len, 2)
        except Exception:
            pass

        sp = SamplingParams(temperature=0.7, max_tokens=128)
        tg0 = time.time()
        outs = llm.generate([SANITY_PROMPT], sp)
        tg = time.time() - tg0
        text = outs[0].outputs[0].text if outs and outs[0].outputs else ""
        ntok = len(outs[0].outputs[0].token_ids) if outs and outs[0].outputs else 0
        if text.strip():
            result["sanity_ok"] = True
            result["sanity_preview"] = text.strip()[:200].replace("\n", " ")
            if tg > 0:
                result["sanity_throughput_tok_s"] = round(ntok / tg, 2)
    except Exception as e:  # noqa: BLE001
        result["error_class"] = type(e).__name__
        result["error"] = str(e)[:500]
    print("PROBE_RESULT_JSON=" + json.dumps(result))
    return 0


def probe_once(model_path: Path, tp: int, max_len: int, extra: str) -> dict:
    """Spawn a child process for one (max_len) attempt. Returns result dict."""
    subprocess.run([str(KILL_PORT), "8100"], check=False, capture_output=True)
    cmd = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "--child",
        "--model-path",
        str(model_path),
        "--tp",
        str(tp),
        "--max-len",
        str(max_len),
        "--extra",
        extra,
    ]
    env = os.environ.copy()
    env.pop("ROCR_VISIBLE_DEVICES", None)  # let vLLM see both cards for TP
    try:
        cp = subprocess.run(
            cmd, capture_output=True, text=True, env=env, timeout=PROBE_TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        return {
            "loaded": False,
            "error_class": "TimeoutExpired",
            "error": f"probe exceeded {PROBE_TIMEOUT_S}s",
            "sanity_ok": False,
        }
    combined = (cp.stdout or "") + "\n" + (cp.stderr or "")
    result = None
    for line in (cp.stdout or "").splitlines():
        if line.startswith("PROBE_RESULT_JSON="):
            result = json.loads(line[len("PROBE_RESULT_JSON=") :])
            break
    if result is None:
        # No structured result — child crashed before printing
        tail = (cp.stderr or cp.stdout or "")[-500:]
        return {
            "loaded": False,
            "error_class": "ChildCrash",
            "error": f"rc={cp.returncode}; tail: {tail}",
            "sanity_ok": False,
        }
    # Backfill KV/maxc from engine log lines if in-process introspection missed.
    m = RE_KV.search(combined)
    if m and result.get("kv_cache_tokens") is None:
        result["kv_cache_tokens"] = int(m.group(1).replace(",", ""))
    m = RE_MAXC.search(combined)
    if m and result.get("max_concurrency") is None:
        result["max_concurrency"] = float(m.group(1))
    return result


def is_success(r: dict) -> bool:
    return bool(r.get("loaded")) and bool(r.get("sanity_ok"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model_dir", nargs="?", help="Model directory name under ~/models")
    ap.add_argument("tp", nargs="?", type=int, help="Tensor parallel size")
    ap.add_argument("--quant", default="auto")
    ap.add_argument("--extra", default="")
    # child-mode args
    ap.add_argument("--child", action="store_true")
    ap.add_argument("--model-path")
    ap.add_argument("--tp", dest="tp_opt", type=int, help="child-mode TP")
    ap.add_argument("--max-len", type=int)
    args = ap.parse_args()

    if args.child:
        return run_child(args.model_path, args.tp_opt, args.max_len, args.extra)

    if not args.model_dir or args.tp is None:
        ap.error("model_dir and tp required in parent mode")

    model_path = MODELS_DIR / args.model_dir
    if not (model_path / "config.json").exists():
        print(f"ERROR: {model_path}/config.json missing", file=sys.stderr)
        return 1

    ENVELOPE_DIR.mkdir(parents=True, exist_ok=True)
    cap = model_max_pos(model_path)
    candidates = sorted(c for c in LADDER if c <= cap)
    if cap not in candidates:
        candidates.append(cap)
    candidates = sorted(set(candidates))

    print(
        f"[probe] {args.model_dir} TP={args.tp} quant={args.quant} "
        f"max_position_embeddings={cap}"
    )
    print(f"[probe] candidate ladder: {candidates}")

    t_start = time.time()
    attempts = []

    # Binary search over candidate indices: find highest index that succeeds.
    lo, hi = 0, len(candidates) - 1
    best_idx = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        ml = candidates[mid]
        print(f"[probe]   trying max_model_len={ml} ...", flush=True)
        r = probe_once(model_path, args.tp, ml, args.extra)
        ok = is_success(r)
        attempts.append(
            {
                "max_model_len": ml,
                "success": ok,
                "loaded": r.get("loaded"),
                "sanity_ok": r.get("sanity_ok"),
                "error_class": r.get("error_class"),
                "load_time_s": r.get("load_time_s"),
                "kv_cache_tokens": r.get("kv_cache_tokens"),
                "max_concurrency": r.get("max_concurrency"),
                "sanity_throughput_tok_s": r.get("sanity_throughput_tok_s"),
            }
        )
        status = "OK" if ok else f"FAIL ({r.get('error_class')})"
        print(f"[probe]   max_model_len={ml} -> {status}")
        if ok:
            best_idx = mid
            lo = mid + 1
        else:
            hi = mid - 1

    elapsed = round(time.time() - t_start, 1)
    best = (
        attempts[0]
        if best_idx < 0
        else next(a for a in attempts if a["max_model_len"] == candidates[best_idx])
    )
    max_ctx = candidates[best_idx] if best_idx >= 0 else None

    record = {
        "test_type": "max_context_probe",
        "phase": "Phase 1 — hardware envelope (METHODOLOGY §5.1)",
        "date": date.today().isoformat(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": args.model_dir,
        "model_path": str(model_path),
        "quantization": args.quant,
        "tensor_parallel_size": args.tp,
        "extra_flags": args.extra.strip(),
        "enforce_eager": True,
        "gpu_memory_utilization": UTIL,
        "model_max_position_embeddings": cap,
        "candidate_ladder": candidates,
        "max_context_stable": max_ctx,
        "max_context_kv_cache_tokens": best.get("kv_cache_tokens") if max_ctx else None,
        "max_context_max_concurrency": best.get("max_concurrency") if max_ctx else None,
        "max_context_load_time_s": best.get("load_time_s") if max_ctx else None,
        "attempts": attempts,
        "probe_wall_s": elapsed,
        "stack_versions": stack_versions(),
        "env": {
            k: os.environ.get(k, "<unset>")
            for k in (
                "VLLM_ROCM_USE_AITER",
                "AMD_SERIALIZE_KERNEL",
                "HIP_LAUNCH_BLOCKING",
                "ROCR_VISIBLE_DEVICES",
                "PYTORCH_ALLOC_CONF",
            )
        },
        "embargo": "PUBLIC engineering §11.1",
        "orchestrated_by": "Claude Code probe_max_context.py (idle-GPU subagent)",
    }
    out = ENVELOPE_DIR / f"{args.model_dir}_maxctx.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    subprocess.run([str(KILL_PORT), "8100"], check=False, capture_output=True)

    print(
        f"[probe] {args.model_dir}: max_context_stable={max_ctx} "
        f"(KV {best.get('kv_cache_tokens')}, maxc {best.get('max_concurrency')}x) "
        f"wall={elapsed}s"
    )
    print(f"[probe] written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
