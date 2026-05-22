#!/usr/bin/env python3
"""
Run a vLLM benchmark with background thermal/utilization sampling.

Consolidates five near-identical per-model wrappers into one. The model is
selected by name on the CLI; everything that differed between the old
wrappers (which runner to invoke, quantization set, ROCR masking policy,
default timeout, grep keys, plotter handling, exit-code policy) is data in
the MODELS table below — not code.

Replaces (behaviour-preserving 1:1):
  - bench_with_thermals.py               → bench_with_thermals.py qwen7b
  - bench_with_thermals_qwen72b.py       → bench_with_thermals.py qwen72b-awq
  - bench_with_thermals_qwen36_27b.py    → bench_with_thermals.py qwen36-27b
  - bench_with_thermals_bielik_11b.py    → bench_with_thermals.py bielik-11b
  - bench_with_thermals_bielik_11b_v30.py→ bench_with_thermals.py bielik-11b-v30

The inner benchmark is the parameterized runners/run_concurrent.py.

What it does:
  1. Starts sample_system.py in background
  2. Waits 5s (baseline idle)
  3. Runs run_concurrent.py <model> with given TP and N
  4. Waits 5s (cooldown capture)
  5. Kills sampler
  6. Writes events.json with benchmark start/end markers
  7. Calls plot_thermals.py

Usage:
    python bench_with_thermals.py qwen7b 1 100 --name tp1-n100 --out-dir runs/
    python bench_with_thermals.py qwen36-27b 2 100 --quant fp8 --name fp8-tp2-n100
    python bench_with_thermals.py bielik-11b-v30 1 50 --quant bf16 --name bf16-tp1-n50-r03

Embargo: SCRIPT is PUBLIC (engineering). Polish-model runs (Bielik) produce
EMBARGO_paper_bound numbers per METHODOLOGY §11.3.

Author: Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
SAMPLER = HERE / "sample_system.py"
PLOTTER = HERE.parent / "plotting" / "plot_thermals.py"
RUN_CONCURRENT = HERE.parent / "runners" / "run_concurrent.py"

IDLE_BEFORE_S = 5.0
IDLE_AFTER_S = 5.0

# Throughput lines surfaced from the bench log after the run. The 7B wrapper
# historically omitted "Load time"; every other wrapper included it.
GREP_KEYS_NO_LOAD = ("Output throughput", "Requests/second", "Total time")
GREP_KEYS_WITH_LOAD = (
    "Output throughput",
    "Requests/second",
    "Total time",
    "Load time",
)

# ---------------------------------------------------------------------------
# Per-model configuration. Every field below is what differed between the five
# old wrappers; the executable logic in main() is shared.
#
#   quants        : allowed --quant values, or None if the model takes no
#                   --quant flag (qwen7b, qwen72b-awq)
#   default_quant : --quant default when quants is not None
#   default_name  : run-name template — "tp{tp}-n{n}" or "{quant}-tp{tp}-n{n}"
#   rocr_policy   : "tp1_zero"  → ROCR_VISIBLE_DEVICES=0 for TP=1, pop for TP=2
#                   "always_pop"→ always pop ROCR_VISIBLE_DEVICES
#   default_timeout : inner-benchmark subprocess timeout (s)
#   timeout_flag  : True → expose a --timeout CLI override (v3.0 only)
#   catch_timeout : True → a subprocess timeout is caught, recorded as rc=124,
#                   and the run finalizes normally (v3.0 only); False → a
#                   timeout propagates as an exception, exactly as the legacy
#                   non-v3.0 wrappers behaved
#   grep_keys     : log lines echoed after the run
#   require_plotter : True → fail fast if plot_thermals.py is missing
#   plot_guard    : True → plot best-effort (exists-guarded, 120s cap,
#                   check=False); False → plot unconditionally with check=True
#   print_quant   : True → print "Quantization: <Q>" in the banner
#   exit_on_rc    : True → sys.exit(0/1) mirroring the inner rc; False → no
#                   explicit exit (legacy wrappers returned 0)
# ---------------------------------------------------------------------------
MODELS = {
    # bench_with_thermals.py — Qwen 2.5 7B.
    "qwen7b": {
        "quants": None,
        "default_quant": None,
        "default_name": "tp{tp}-n{n}",
        "rocr_policy": "tp1_zero",
        "default_timeout": 900,
        "timeout_flag": False,
        "catch_timeout": False,
        "grep_keys": GREP_KEYS_NO_LOAD,
        "require_plotter": True,
        "plot_guard": False,
        "print_quant": False,
        "exit_on_rc": False,
    },
    # bench_with_thermals_qwen72b.py — Qwen 2.5 72B AWQ, TP=2.
    "qwen72b-awq": {
        "quants": None,
        "default_quant": None,
        "default_name": "tp{tp}-n{n}",
        "rocr_policy": "always_pop",
        "default_timeout": 1800,
        "timeout_flag": False,
        "catch_timeout": False,
        "grep_keys": GREP_KEYS_WITH_LOAD,
        "require_plotter": True,
        "plot_guard": False,
        "print_quant": False,
        "exit_on_rc": False,
    },
    # bench_with_thermals_qwen36_27b.py — Qwen 3.6 27B, FP8/BF16, TP=2.
    "qwen36-27b": {
        "quants": ["fp8", "bf16"],
        "default_quant": "bf16",
        "default_name": "{quant}-tp{tp}-n{n}",
        "rocr_policy": "always_pop",
        "default_timeout": 1800,
        "timeout_flag": False,
        "catch_timeout": False,
        "grep_keys": GREP_KEYS_WITH_LOAD,
        "require_plotter": True,
        "plot_guard": False,
        "print_quant": True,
        "exit_on_rc": False,
    },
    # bench_with_thermals_bielik_11b.py — Bielik 11B v2.3, FP16/AWQ.
    "bielik-11b": {
        "quants": ["fp16", "awq"],
        "default_quant": "fp16",
        "default_name": "{quant}-tp{tp}-n{n}",
        "rocr_policy": "always_pop",
        "default_timeout": 1800,
        "timeout_flag": False,
        "catch_timeout": False,
        "grep_keys": GREP_KEYS_WITH_LOAD,
        "require_plotter": True,
        "plot_guard": False,
        "print_quant": True,
        "exit_on_rc": False,
    },
    # bench_with_thermals_bielik_11b_v30.py — Bielik 11B v3.0, BF16.
    "bielik-11b-v30": {
        "quants": ["bf16"],
        "default_quant": "bf16",
        "default_name": "{quant}-tp{tp}-n{n}",
        "rocr_policy": "always_pop",
        "default_timeout": 1800,
        "timeout_flag": True,
        "catch_timeout": True,
        "grep_keys": GREP_KEYS_WITH_LOAD,
        "require_plotter": False,
        "plot_guard": True,
        "print_quant": True,
        "exit_on_rc": True,
    },
}


def main():
    """Argument parsing and instrumented benchmark execution."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("model", choices=sorted(MODELS), help="Model key (see MODELS)")
    ap.add_argument("tp", type=int, help="Tensor parallel size")
    ap.add_argument("n", type=int, help="Number of concurrent prompts")
    ap.add_argument(
        "--quant",
        default=None,
        help="Quantization variant (only for models that take one)",
    )
    ap.add_argument(
        "--max-len",
        type=int,
        default=None,
        help="Override max_model_len for inner benchmark",
    )
    ap.add_argument(
        "--util",
        type=float,
        default=None,
        help="Override gpu_memory_utilization for inner benchmark",
    )
    ap.add_argument(
        "--kv-dtype", default=None, help="Override kv_cache_dtype for inner benchmark"
    )
    ap.add_argument("--name", help="Run name (default: per-model template)")
    ap.add_argument("--out-dir", default=".", help="Output directory")
    ap.add_argument("--interval", type=float, default=1.0, help="Sampler interval")
    ap.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Per-run timeout for inner benchmark subprocess (s)",
    )
    args = ap.parse_args()

    spec = MODELS[args.model]

    # Resolve quantization. Models with quants=None take no --quant.
    quant = None
    if spec["quants"] is not None:
        quant = args.quant or spec["default_quant"]
        if quant not in spec["quants"]:
            ap.error(
                f"model '{args.model}' supports --quant "
                f"{spec['quants']}, got '{quant}'"
            )
    elif args.quant is not None:
        ap.error(f"model '{args.model}' does not take --quant")

    # Run name from the per-model template.
    name = args.name or spec["default_name"].format(tp=args.tp, n=args.n, quant=quant)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    jsonl = out_dir / f"{name}-thermals.jsonl"
    events_json = out_dir / f"{name}-events.json"
    png = out_dir / f"{name}-thermals.png"
    bench_log = out_dir / f"{name}-bench.log"

    # Sanity checks. The v3.0 wrapper deliberately did not require the plotter
    # (plotting is best-effort there); every other wrapper required it.
    required = [SAMPLER, RUN_CONCURRENT]
    if spec["require_plotter"]:
        required.append(PLOTTER)
    for p in required:
        if not p.exists():
            print(f"ERROR: missing {p}")
            sys.exit(1)

    # Per-run timeout: --timeout overrides only when the model exposes it.
    # Legacy non-v3.0 wrappers had no --timeout flag at all; reject it here so
    # the CLI surface stays 1:1 with the old per-model scripts.
    if args.timeout is not None and not spec["timeout_flag"]:
        ap.error(f"model '{args.model}' does not take --timeout")
    timeout_s = spec["default_timeout"]
    if spec["timeout_flag"] and args.timeout is not None:
        timeout_s = args.timeout

    print(f"Run name: {name}")
    print(f"Output dir: {out_dir}")
    if spec["print_quant"]:
        print(f"Quantization: {quant.upper()}")

    # 1. Start sampler.
    print("Starting sampler...")
    sampler_proc = subprocess.Popen(
        [sys.executable, str(SAMPLER), str(jsonl), "--interval", str(args.interval)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    t_wall_start = time.time()
    events = []
    bench_rc = -1

    try:
        # 2. Baseline idle.
        print(f"Collecting {IDLE_BEFORE_S}s baseline...")
        time.sleep(IDLE_BEFORE_S)

        # 3. Benchmark.
        t_bench_start = time.time() - t_wall_start
        if spec["print_quant"]:
            start_label = f"bench start ({quant.upper()}, TP={args.tp}, N={args.n})"
        else:
            start_label = f"bench start (TP={args.tp}, N={args.n})"
        events.append(
            {
                "t": round(t_bench_start, 2),
                "label": start_label,
                "color": "#2ca02c",
            }
        )
        if spec["print_quant"]:
            print(f"Running benchmark ({quant.upper()}, TP={args.tp}, N={args.n})...")
        else:
            print(f"Running benchmark (TP={args.tp}, N={args.n})...")

        env = os.environ.copy()
        if spec["rocr_policy"] == "tp1_zero":
            if args.tp == 1:
                env["ROCR_VISIBLE_DEVICES"] = "0"
            else:
                env.pop("ROCR_VISIBLE_DEVICES", None)
        else:  # always_pop
            env.pop("ROCR_VISIBLE_DEVICES", None)

        # Build inner benchmark command for run_concurrent.py <model> <tp> <n>.
        cmd = [
            sys.executable,
            "-u",
            str(RUN_CONCURRENT),
            args.model,
            str(args.tp),
            str(args.n),
        ]
        if quant is not None:
            cmd += ["--quant", quant]
        if args.max_len is not None:
            cmd += ["--max-len", str(args.max_len)]
        if args.util is not None:
            cmd += ["--util", str(args.util)]
        if args.kv_dtype is not None:
            cmd += ["--kv-dtype", args.kv_dtype]

        with open(bench_log, "w") as f:
            if spec["catch_timeout"]:
                # v3.0 wrapper: a timeout is caught and the run finalizes.
                try:
                    bench_result = subprocess.run(
                        cmd,
                        stdout=f,
                        stderr=subprocess.STDOUT,
                        env=env,
                        timeout=timeout_s,
                    )
                    bench_rc = bench_result.returncode
                except subprocess.TimeoutExpired:
                    print(f"TIMEOUT after {timeout_s}s — killing inner benchmark")
                    bench_rc = 124
            else:
                # Legacy non-v3.0 wrappers: a timeout propagates as an
                # exception (the finally block still stops the sampler).
                bench_result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    timeout=timeout_s,
                )
                bench_rc = bench_result.returncode

        t_bench_end = time.time() - t_wall_start
        events.append(
            {"t": round(t_bench_end, 2), "label": "bench end", "color": "#d62728"}
        )
        print(f"Benchmark done (rc={bench_rc})")

        # 4. Cooldown capture.
        print(f"Collecting {IDLE_AFTER_S}s cooldown...")
        time.sleep(IDLE_AFTER_S)

    finally:
        # 5. Stop sampler.
        print("Stopping sampler...")
        sampler_proc.send_signal(signal.SIGINT)
        try:
            sampler_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            sampler_proc.kill()

    # 6. Write events.
    with open(events_json, "w") as f:
        json.dump(events, f, indent=2)
    print(f"Events: {events_json}")

    # 7. Plot. Best-effort (exists-guarded) or unconditional, per model.
    if spec["plot_guard"]:
        if PLOTTER.exists():
            print("Generating thermal plot...")
            try:
                subprocess.run(
                    [
                        sys.executable,
                        str(PLOTTER),
                        str(jsonl),
                        str(png),
                        "--events",
                        str(events_json),
                    ],
                    check=False,
                    timeout=120,
                )
            except subprocess.TimeoutExpired:
                print("WARN: thermal plot timed out (non-fatal)")
    else:
        print("Generating thermal plot...")
        subprocess.run(
            [
                sys.executable,
                str(PLOTTER),
                str(jsonl),
                str(png),
                "--events",
                str(events_json),
            ],
            check=True,
        )

    # Also print throughput from bench log if available.
    try:
        bench_text = bench_log.read_text()
        for line in bench_text.splitlines():
            if any(k in line for k in spec["grep_keys"]):
                print(f"  {line.strip()}")
    except Exception:
        pass

    print(f"\nAll outputs in: {out_dir}")

    if spec["exit_on_rc"]:
        sys.exit(0 if bench_rc == 0 else 1)


if __name__ == "__main__":
    main()
