"""
Run a Bielik 11B v3.0 vLLM benchmark with background thermal/utilization
sampling.

Sibling of bench_with_thermals_bielik_11b.py (v2.3). Same artifact layout
(JSONL, events.json, PNG, bench.log) but points at the v3.0 runner. Adds
optional ``--rep`` for multi-replication runs at the same (TP, N) cell.

Filename conventions for the v0.3 sweep:
  - Single rep    : {quant}-tp{TP}-n{N}-{bench.log,events.json,thermals.jsonl,thermals.png}
  - With rep idx  : {quant}-tp{TP}-n{N}-r{REP}-{bench.log,events.json,thermals.jsonl,thermals.png}

We keep the same RE_RUN_NAME prefix so finalize_bielik_11b_v30_phase2.py can
detect the rep suffix via a separate regex without colliding with the
v2.3 single-run schema.

Usage:
  python bench_with_thermals_bielik_11b_v30.py 1 50 --quant bf16 \\
      --name bf16-tp1-n50-r03 \\
      --out-dir benchmarks/results/bielik-11b-v30/thermal-runs/

Embargo: EMBARGO_paper_bound (Polish model, METHODOLOGY §11.3).
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
BENCHMARK = HERE.parent / "runners" / "test_concurrent_bielik_11b_v30.py"

IDLE_BEFORE_S = 5.0
IDLE_AFTER_S = 5.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tp", type=int, help="Tensor parallel size (1 or 2)")
    ap.add_argument("n", type=int, help="Number of concurrent prompts")
    ap.add_argument(
        "--quant",
        choices=["bf16"],
        default="bf16",
        help="Quantization variant (BF16 only in v0.3 sweep)",
    )
    ap.add_argument("--max-len", type=int, default=None)
    ap.add_argument("--util", type=float, default=None)
    ap.add_argument("--kv-dtype", default=None)
    ap.add_argument("--name", help="Run name (default: {quant}-tp{TP}-n{N})")
    ap.add_argument("--out-dir", default=".", help="Output directory")
    ap.add_argument("--interval", type=float, default=1.0, help="Sampler interval s")
    ap.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Per-run timeout for inner benchmark subprocess (s)",
    )
    args = ap.parse_args()

    name = args.name or f"{args.quant}-tp{args.tp}-n{args.n}"
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    jsonl = out_dir / f"{name}-thermals.jsonl"
    events_json = out_dir / f"{name}-events.json"
    png = out_dir / f"{name}-thermals.png"
    bench_log = out_dir / f"{name}-bench.log"

    for p in (SAMPLER, BENCHMARK):
        if not p.exists():
            print(f"ERROR: missing {p}")
            sys.exit(1)

    print(f"Run name: {name}")
    print(f"Output dir: {out_dir}")
    print(f"Quantization: {args.quant.upper()}")

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
        print(f"Collecting {IDLE_BEFORE_S}s baseline...")
        time.sleep(IDLE_BEFORE_S)

        t_bench_start = time.time() - t_wall_start
        events.append(
            {
                "t": round(t_bench_start, 2),
                "label": f"bench start ({args.quant.upper()}, "
                f"TP={args.tp}, N={args.n})",
                "color": "#2ca02c",
            }
        )

        print(
            f"Running benchmark ({args.quant.upper()}, " f"TP={args.tp}, N={args.n})..."
        )

        env = os.environ.copy()
        # Inner runner needs both GPUs visible; the wrapper still uses
        # ROCR_VISIBLE_DEVICES=0,1 in the parent shell, but we pop here for
        # parity with the v2.3 wrapper which lets vLLM see both cards.
        env.pop("ROCR_VISIBLE_DEVICES", None)

        cmd = [
            sys.executable,
            "-u",
            str(BENCHMARK),
            str(args.tp),
            str(args.n),
            "--quant",
            args.quant,
        ]
        if args.max_len is not None:
            cmd += ["--max-len", str(args.max_len)]
        if args.util is not None:
            cmd += ["--util", str(args.util)]
        if args.kv_dtype is not None:
            cmd += ["--kv-dtype", args.kv_dtype]

        with open(bench_log, "w") as f:
            try:
                bench_result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    timeout=args.timeout,
                )
                bench_rc = bench_result.returncode
            except subprocess.TimeoutExpired:
                print(f"TIMEOUT after {args.timeout}s — killing inner benchmark")
                bench_rc = 124

        t_bench_end = time.time() - t_wall_start
        events.append(
            {"t": round(t_bench_end, 2), "label": "bench end", "color": "#d62728"}
        )
        print(f"Benchmark done (rc={bench_rc})")

        print(f"Collecting {IDLE_AFTER_S}s cooldown...")
        time.sleep(IDLE_AFTER_S)

    finally:
        print("Stopping sampler...")
        sampler_proc.send_signal(signal.SIGINT)
        try:
            sampler_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            sampler_proc.kill()

    with open(events_json, "w") as f:
        json.dump(events, f, indent=2)
    print(f"Events: {events_json}")

    # Plot thermals (best-effort; do not abort if matplotlib import fails)
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

    try:
        bench_text = bench_log.read_text()
        for line in bench_text.splitlines():
            if any(
                k in line
                for k in (
                    "Output throughput",
                    "Requests/second",
                    "Total time",
                    "Load time",
                )
            ):
                print(f"  {line.strip()}")
    except Exception:
        pass

    print(f"\nAll outputs in: {out_dir}")
    sys.exit(0 if bench_rc == 0 else 1)


if __name__ == "__main__":
    main()
