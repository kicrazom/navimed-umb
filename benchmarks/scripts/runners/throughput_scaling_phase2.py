#!/usr/bin/env python3
"""
throughput_scaling_phase2.py — Faza 6: Phase 2 scaling sweep (knee/plateau).

Thin wrapper around `throughput_sweep_v0.3.py`. Sweep #3 (N∈{10..200}) found
all 12 PASS models scale linearly to N=200 — knee throughput NOT located for
the bf16/fp16 models. This wrapper re-runs the harness with an EXTENDED N
ladder (N>200) to locate the throughput knee and plateau.

Key difference vs the v0.3 harness: output goes to
  benchmarks/results/<model>/scaling/
instead of overwriting the sweep #3 artifacts in
  benchmarks/results/<model>/{results_table.csv,SUMMARY.md,thermal-runs/}.

Sweep #3 results are preserved untouched (linear-region reference, N≤200).

Reuses METHODOLOGY §5.2/§6/§7: same workload, same reporting schema, same
KILL_PORT cleanup, same per-N process isolation, same 1 Hz thermal sampling.

Embargo §11.2/§11.3 — all output under gitignored benchmarks/results/.

Usage:
    python throughput_scaling_phase2.py <model_dir> <tp> --quant Q \
        --ns 350,500,750,1000 [--extra "..."]

Author: Claude Code (navimed-umb Faza 6 subagent), 2026-05-21.
"""

import argparse
import importlib.util
import sys
import time
from pathlib import Path

# Import the v0.3 harness as a module (filename has dots → importlib by path).
# Reuse run_n / write_summary / module globals; child mode is its own __main__.
_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "throughput_sweep_v0_3", _HERE / "throughput_sweep_v0.3.py"
)
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model_dir")
    ap.add_argument("tp", type=int)
    ap.add_argument("--quant", default="auto")
    ap.add_argument("--extra", default="")
    ap.add_argument("--ns", required=True, help="comma list, extended N>200")
    args = ap.parse_args()

    model_path = H.MODELS_DIR / args.model_dir
    if not (model_path / "config.json").exists():
        print(f"ERROR: {model_path}/config.json missing", file=sys.stderr)
        return 1

    ns = [int(x) for x in args.ns.split(",")]
    # Output isolated under <model>/scaling/ — sweep #3 artifacts untouched.
    results_dir = H.RESULTS_DIR / args.model_dir / "scaling"
    out_dir = results_dir / "thermal-runs"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[scaling] {args.model_dir} TP={args.tp} quant={args.quant} N={ns}")
    t_start = time.time()
    rows = []
    for n in ns:
        print(f"[scaling]   N={n} ...", flush=True)
        tr0 = time.time()
        row = H.run_n(
            args.model_dir, model_path, args.tp, n, args.quant, args.extra, out_dir
        )
        rows.append(row)
        dt = time.time() - tr0
        if row["ok"]:
            print(
                f"[scaling]   N={n} -> {row['tok_s_out']} tok/s_out, "
                f"{row['req_s']} req/s, VRAM {row['vram_peak_gb']}GB, "
                f"T {row['temp_peak_c']}C ({dt:.0f}s)"
            )
        else:
            print(f"[scaling]   N={n} -> FAIL: {row['error']} ({dt:.0f}s)")
        if n != ns[-1]:
            time.sleep(H.COOLDOWN_S)

    wall = time.time() - t_start
    csv_path, md = H.write_summary(
        args.model_dir, args.tp, args.quant, rows, results_dir, wall
    )
    print(f"[scaling] {args.model_dir} done — wall {wall/60:.1f} min")
    print(f"[scaling] CSV: {csv_path}")
    print(f"[scaling] SUMMARY: {md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
