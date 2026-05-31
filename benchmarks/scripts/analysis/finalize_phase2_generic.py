"""
NaviMed-UMB Phase 2 finalize — PARAMETERIZED generalization.

Parameterized sibling of finalize_bielik_11b_v30_phase2.py. Same aggregation
logic, same output files, same EMBARGO=YES headers — but the model identity,
quant, ladders, max_len, util, KV dtype, reps, and (optionally) the output
directory are supplied on the command line instead of being hardcoded.

For any model whose Phase 2 thermal-runs live under
``benchmarks/results/<MODEL>/thermal-runs/`` (per-run files named
``<quant>-tp<TP>-n<N>-r<REP>-{bench.log,events.json,thermals.jsonl,thermals.png}``),
this script:
  - Reads <results-dir>/thermal-runs/<quant>-tp{TP}-n{N}-r{REP}-*
  - Aggregates the reps present per (TP, N) cell → median + p95 + p99 + min/max
    (records n_runs per cell; partial / zero-rep cells handled gracefully)
  - Emits (into <out-dir>, default == <results-dir>):
      - phase2_sweep.csv          (per-cell aggregates, METHODOLOGY §7.1 + n_runs)
      - phase2_sweep_tp{TP}.csv    (one per TP in the tp-ladder)
      - phase2_sweep_raw.csv      (per-rep, all rows)
      - scaling_curve.png         (throughput vs N, all TPs)
      - latency_p99.png           (p99 wall time / req vs N)
      - thermal_gallery.png       (per-cell temp/power traces, all TPs)
      - power_efficiency.png      (tok/s/W vs N, all TPs)
      - SUMMARY.md                (METHODOLOGY §7.3 narrative + embargo split)
      - methodology_compliance.json (Kim et al. 2026 disclosure +
                                     Lerchner 2026 humility)

Embargo: SCRIPT itself is PUBLIC, OUTPUTS are EMBARGO_paper_bound (§11.3).
Per-file EMBARGO=YES header is written into CSV/MD outputs.

Invocation contract (matches orchestrators/run_pllum_run3_sweep.sh):

    python3 finalize_phase2_generic.py \
        --results-dir <repo>/benchmarks/results/<MODEL> \
        --model-label <key> --model-name <hf> \
        --quant awq --max-len 8192 --util 0.90

Author: Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# ============================================================
# Repo root — robust (git rev-parse, not fragile parent counting;
# PLAN-NEXT anti-pattern 1.1). Falls back to a path walk only if git
# is unavailable (e.g. exported tarball).
# ============================================================


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=here.parent,
            capture_output=True,
            text=True,
            check=True,
        )
        root = Path(out.stdout.strip())
        if root.exists():
            return root
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass
    # Fallback: benchmarks/scripts/analysis/<file> → repo is 3 parents up.
    return here.parent.parent.parent.parent


REPO_ROOT = find_repo_root()

EMBARGO_HEADER = (
    "# EMBARGO=YES — paper-bound (Polish model, METHODOLOGY §11.3)\n"
    "# DO NOT COMMIT until paper acceptance.\n"
)

# Quant-agnostic: matches "<quant>-tp<tp>-n<n>-r<rep>-bench.log" only (the
# non-rep "<quant>-tp<tp>-n<n>-bench.log" envelope files lack -rNN- and are
# intentionally NOT matched). Capturing the quant group lets the thermal
# gallery reconstruct per-rep filenames regardless of the --quant label.
RE_RUN = re.compile(
    r"^(?P<quant>[a-z0-9.]+)-tp(?P<tp>\d+)-n(?P<n>\d+)-r(?P<rep>\d+)-bench\.log$"
)


def _rel(path: Path) -> str:
    """Display path relative to repo root when possible, else absolute."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


# ============================================================
# Config (populated from argparse, threaded through as a dataclass)
# ============================================================


@dataclass
class Config:
    results_dir: Path
    out_dir: Path
    thermal_dir: Path
    model_label: str
    model_name: str
    quant: str
    backend: str
    max_len: int
    util: float
    kv_dtype: str
    tuning: str
    n_ladder: list[int]
    tp_ladder: list[int]
    reps: int


# ============================================================
# Per-rep record (raw)
# ============================================================


@dataclass
class RepRecord:
    tp: int
    n: int
    rep: int
    fname_quant: str = ""  # filename quant prefix (e.g. "bf16" / "awq")
    load_time_s: Optional[float] = None
    total_s: Optional[float] = None
    tok_s_out: Optional[float] = None
    tok_s_tot: Optional[float] = None
    req_s: Optional[float] = None
    total_out_tokens: Optional[int] = None
    total_in_tokens: Optional[int] = None
    mean_output_len: Optional[float] = None
    vram_peak_gib: Optional[float] = None
    t_peak_c: Optional[float] = None
    w_mean: Optional[float] = None
    w_peak: Optional[float] = None
    w_per_tok_wh: Optional[float] = None
    ok: bool = False


# ============================================================
# Per-cell aggregate (median + p95 + p99)
# ============================================================


@dataclass
class CellAggregate:
    tp: int
    n: int
    n_runs_ok: int = 0
    n_runs_fail: int = 0
    # Throughput aggregates
    tok_s_out_median: Optional[float] = None
    tok_s_out_min: Optional[float] = None
    tok_s_out_max: Optional[float] = None
    tok_s_tot_median: Optional[float] = None
    # Latency aggregates (total wall time per request as proxy)
    total_s_median: Optional[float] = None
    total_s_p95: Optional[float] = None
    total_s_p99: Optional[float] = None
    req_s_median: Optional[float] = None
    # Per-request latency proxy: total_s / n
    per_req_latency_median: Optional[float] = None
    per_req_latency_p95: Optional[float] = None
    per_req_latency_p99: Optional[float] = None
    # Thermal aggregates
    vram_peak_gib_median: Optional[float] = None
    t_peak_c_median: Optional[float] = None
    t_peak_c_max: Optional[float] = None
    w_mean_median: Optional[float] = None
    w_peak_max: Optional[float] = None
    # Energy
    w_per_tok_wh_median: Optional[float] = None
    # Tokens
    output_tok_total_median: Optional[float] = None
    load_time_s_median: Optional[float] = None
    # Raw reps for downstream stats
    reps: list[RepRecord] = field(default_factory=list)


# ============================================================
# Parsing
# ============================================================


BENCH_PATTERNS = {
    "load_time_s": r"Load time:\s+([\d.]+)s",
    "total_s": r"Total time:\s+([\d.]+)s",
    "total_out_tokens": r"Total output tokens:\s+(\d+)",
    "total_in_tokens": r"Total input tokens:\s+(\d+)",
    "tok_s_out": r"Output throughput:\s+([\d.]+)\s+tok/s",
    "tok_s_tot": r"Total throughput:\s+([\d.]+)\s+tok/s",
    "req_s": r"Requests/second:\s+([\d.]+)",
    "mean_output_len": r"Mean output len:\s+([\d.]+)",
}


def parse_bench_log(path: Path) -> dict:
    data: dict = {}
    if not path.exists():
        return data
    text = path.read_text(errors="ignore")
    for key, pat in BENCH_PATTERNS.items():
        m = re.search(pat, text)
        if m:
            val_str = m.group(1)
            data[key] = int(val_str) if "tokens" in key else float(val_str)
    return data


def parse_thermals_window(jsonl_path: Path, events_path: Path) -> dict:
    if not jsonl_path.exists() or not events_path.exists():
        return {}

    try:
        events = json.loads(events_path.read_text())
    except json.JSONDecodeError:
        return {}

    t_start = next((e["t"] for e in events if "bench start" in e["label"]), None)
    t_end = next((e["t"] for e in events if "bench end" in e["label"]), None)
    if t_start is None or t_end is None:
        return {}

    samples = []
    for line in jsonl_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            samples.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    win = [s for s in samples if t_start <= s.get("t", -1) <= t_end]
    if not win:
        return {}

    vram_max = 0.0
    t_max = 0.0
    w_samples_total = []

    for s in win:
        gpus = s.get("gpus", []) or []
        if not gpus:
            continue
        sum_w = 0.0
        for g in gpus:
            if g.get("is_igpu"):
                continue
            vram_b = g.get("vram_used_b") or 0
            vram_gib = vram_b / (1024**3)
            if vram_gib > vram_max:
                vram_max = vram_gib
            tc = g.get("temp") or 0.0
            if tc > t_max:
                t_max = tc
            pw = g.get("power_w") or 0.0
            sum_w += pw
        if sum_w > 0:
            w_samples_total.append(sum_w)

    return {
        "vram_peak_gib": round(vram_max, 3) if vram_max > 0 else None,
        "t_peak_c": round(t_max, 1) if t_max > 0 else None,
        "w_mean": round(statistics.mean(w_samples_total), 1)
        if w_samples_total
        else None,
        "w_peak": round(max(w_samples_total), 1) if w_samples_total else None,
    }


def build_reps(cfg: Config) -> list[RepRecord]:
    reps: list[RepRecord] = []
    if not cfg.thermal_dir.exists():
        return reps

    for log_path in sorted(cfg.thermal_dir.glob("*-bench.log")):
        m = RE_RUN.match(log_path.name)
        if not m:
            continue
        tp = int(m.group("tp"))
        n = int(m.group("n"))
        rep_idx = int(m.group("rep"))
        fname_quant = m.group("quant")

        rec = RepRecord(tp=tp, n=n, rep=rep_idx, fname_quant=fname_quant)
        bench_data = parse_bench_log(log_path)
        for k, v in bench_data.items():
            setattr(rec, k, v)

        base = log_path.name.removesuffix("-bench.log")
        events_p = cfg.thermal_dir / f"{base}-events.json"
        thermals_p = cfg.thermal_dir / f"{base}-thermals.jsonl"
        therm = parse_thermals_window(thermals_p, events_p)
        for k, v in therm.items():
            setattr(rec, k, v)

        # Energy per token (Wh)
        if rec.w_mean and rec.total_s and rec.total_out_tokens:
            energy_wh = rec.w_mean * rec.total_s / 3600.0
            rec.w_per_tok_wh = round(energy_wh / rec.total_out_tokens, 6)

        rec.ok = rec.tok_s_out is not None and rec.total_s is not None
        reps.append(rec)

    return reps


# ============================================================
# Aggregation
# ============================================================


def _pct(xs: list[float], p: float) -> Optional[float]:
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    s = sorted(xs)
    # Nearest-rank percentile (suitable for small n=10 samples; documented in SUMMARY)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


def aggregate_cells(reps: list[RepRecord]) -> list[CellAggregate]:
    cells: dict[tuple[int, int], CellAggregate] = {}
    for r in reps:
        key = (r.tp, r.n)
        c = cells.setdefault(key, CellAggregate(tp=r.tp, n=r.n))
        c.reps.append(r)
        if r.ok:
            c.n_runs_ok += 1
        else:
            c.n_runs_fail += 1

    for c in cells.values():
        ok_reps = [r for r in c.reps if r.ok]
        if not ok_reps:
            # Zero successful reps in this cell — leave aggregates None,
            # n_runs_ok/n_runs_fail already recorded. Do not crash.
            continue

        tok_s_out = [r.tok_s_out for r in ok_reps if r.tok_s_out is not None]
        tok_s_tot = [r.tok_s_tot for r in ok_reps if r.tok_s_tot is not None]
        total_s = [r.total_s for r in ok_reps if r.total_s is not None]
        req_s = [r.req_s for r in ok_reps if r.req_s is not None]
        per_req_lat = [r.total_s / r.n for r in ok_reps if r.total_s]
        vram = [r.vram_peak_gib for r in ok_reps if r.vram_peak_gib is not None]
        temps = [r.t_peak_c for r in ok_reps if r.t_peak_c is not None]
        w_mean = [r.w_mean for r in ok_reps if r.w_mean is not None]
        w_peak = [r.w_peak for r in ok_reps if r.w_peak is not None]
        w_per_tok = [r.w_per_tok_wh for r in ok_reps if r.w_per_tok_wh is not None]
        out_toks = [
            r.total_out_tokens for r in ok_reps if r.total_out_tokens is not None
        ]
        load_t = [r.load_time_s for r in ok_reps if r.load_time_s is not None]

        c.tok_s_out_median = statistics.median(tok_s_out) if tok_s_out else None
        c.tok_s_out_min = min(tok_s_out) if tok_s_out else None
        c.tok_s_out_max = max(tok_s_out) if tok_s_out else None
        c.tok_s_tot_median = statistics.median(tok_s_tot) if tok_s_tot else None
        c.total_s_median = statistics.median(total_s) if total_s else None
        c.total_s_p95 = _pct(total_s, 95.0)
        c.total_s_p99 = _pct(total_s, 99.0)
        c.req_s_median = statistics.median(req_s) if req_s else None
        c.per_req_latency_median = (
            statistics.median(per_req_lat) if per_req_lat else None
        )
        c.per_req_latency_p95 = _pct(per_req_lat, 95.0)
        c.per_req_latency_p99 = _pct(per_req_lat, 99.0)
        c.vram_peak_gib_median = statistics.median(vram) if vram else None
        c.t_peak_c_median = statistics.median(temps) if temps else None
        c.t_peak_c_max = max(temps) if temps else None
        c.w_mean_median = statistics.median(w_mean) if w_mean else None
        c.w_peak_max = max(w_peak) if w_peak else None
        c.w_per_tok_wh_median = statistics.median(w_per_tok) if w_per_tok else None
        c.output_tok_total_median = statistics.median(out_toks) if out_toks else None
        c.load_time_s_median = statistics.median(load_t) if load_t else None

    return sorted(cells.values(), key=lambda c: (c.tp, c.n))


# ============================================================
# CSV emission
# ============================================================


CELL_CSV_COLUMNS = [
    "model",
    "quant",
    "backend",
    "TP",
    "max_len",
    "util",
    "KV_dtype",
    "N",
    "n_runs_ok",
    "n_runs_fail",
    "tok_s_out_median",
    "tok_s_out_min",
    "tok_s_out_max",
    "tok_s_tot_median",
    "total_s_median",
    "total_s_p95",
    "total_s_p99",
    "req_s_median",
    "per_req_latency_median",
    "per_req_latency_p95",
    "per_req_latency_p99",
    "VRAM_peak_GB_median",
    "T_peak_C_median",
    "T_peak_C_max",
    "W_mean_median",
    "W_peak_max",
    "W_per_tok_Wh_median",
    "output_tok_total_median",
    "load_time_s_median",
    "tuning",
]


def _fmt(v, d=2) -> str:
    if v is None:
        return ""
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return f"{v:.{d}f}"
    return str(v)


def _emit_cell_csv(cells: list[CellAggregate], path: Path, cfg: Config) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        f.write(EMBARGO_HEADER)
        w = csv.writer(f)
        w.writerow(CELL_CSV_COLUMNS)
        for c in cells:
            w.writerow(
                [
                    cfg.model_label,
                    cfg.quant,
                    cfg.backend,
                    c.tp,
                    cfg.max_len,
                    cfg.util,
                    cfg.kv_dtype,
                    c.n,
                    c.n_runs_ok,
                    c.n_runs_fail,
                    _fmt(c.tok_s_out_median, 2),
                    _fmt(c.tok_s_out_min, 2),
                    _fmt(c.tok_s_out_max, 2),
                    _fmt(c.tok_s_tot_median, 2),
                    _fmt(c.total_s_median, 3),
                    _fmt(c.total_s_p95, 3),
                    _fmt(c.total_s_p99, 3),
                    _fmt(c.req_s_median, 3),
                    _fmt(c.per_req_latency_median, 4),
                    _fmt(c.per_req_latency_p95, 4),
                    _fmt(c.per_req_latency_p99, 4),
                    _fmt(c.vram_peak_gib_median, 2),
                    _fmt(c.t_peak_c_median, 1),
                    _fmt(c.t_peak_c_max, 1),
                    _fmt(c.w_mean_median, 1),
                    _fmt(c.w_peak_max, 1),
                    _fmt(c.w_per_tok_wh_median, 6),
                    _fmt(c.output_tok_total_median, 0),
                    _fmt(c.load_time_s_median, 1),
                    cfg.tuning,
                ]
            )
    print(f"  CSV → {_rel(path)}")


def emit_csvs(cells: list[CellAggregate], reps: list[RepRecord], cfg: Config) -> None:
    _emit_cell_csv(cells, cfg.out_dir / "phase2_sweep.csv", cfg)
    # One per-TP CSV for each TP in the ladder. A single-element tp-ladder
    # therefore yields exactly one per-TP CSV (the other is not written), and
    # an empty/partial TP yields a header-only CSV — neither crashes.
    for tp in cfg.tp_ladder:
        _emit_cell_csv(
            [c for c in cells if c.tp == tp],
            cfg.out_dir / f"phase2_sweep_tp{tp}.csv",
            cfg,
        )

    # Raw per-rep CSV
    raw_path = cfg.out_dir / "phase2_sweep_raw.csv"
    with raw_path.open("w", newline="") as f:
        f.write(EMBARGO_HEADER)
        w = csv.writer(f)
        w.writerow(
            [
                "TP",
                "N",
                "rep",
                "ok",
                "load_time_s",
                "total_s",
                "tok_s_out",
                "tok_s_tot",
                "req_s",
                "total_out_tokens",
                "total_in_tokens",
                "mean_output_len",
                "VRAM_peak_GB",
                "T_peak_C",
                "W_mean",
                "W_peak",
                "W_per_tok_Wh",
            ]
        )
        for r in sorted(reps, key=lambda x: (x.tp, x.n, x.rep)):
            w.writerow(
                [
                    r.tp,
                    r.n,
                    r.rep,
                    int(r.ok),
                    _fmt(r.load_time_s, 2),
                    _fmt(r.total_s, 3),
                    _fmt(r.tok_s_out, 2),
                    _fmt(r.tok_s_tot, 2),
                    _fmt(r.req_s, 3),
                    _fmt(r.total_out_tokens, 0),
                    _fmt(r.total_in_tokens, 0),
                    _fmt(r.mean_output_len, 1),
                    _fmt(r.vram_peak_gib, 2),
                    _fmt(r.t_peak_c, 1),
                    _fmt(r.w_mean, 1),
                    _fmt(r.w_peak, 1),
                    _fmt(r.w_per_tok_wh, 6),
                ]
            )
    print(f"  CSV → {_rel(raw_path)}")


# ============================================================
# Plots
# ============================================================


def _by_tp(cells: list[CellAggregate]) -> dict[int, list[CellAggregate]]:
    out: dict[int, list[CellAggregate]] = {}
    for c in cells:
        out.setdefault(c.tp, []).append(c)
    for tp in out:
        out[tp].sort(key=lambda c: c.n)
    return out


def plot_scaling(cells: list[CellAggregate], path: Path, cfg: Config) -> None:
    by_tp = _by_tp(cells)
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = {1: "#1f77b4", 2: "#d62728"}
    markers = {1: "o", 2: "s"}
    for tp, tp_cells in sorted(by_tp.items()):
        xs = [c.n for c in tp_cells if c.tok_s_out_median is not None]
        ys = [c.tok_s_out_median for c in tp_cells if c.tok_s_out_median is not None]
        ymin = [c.tok_s_out_min for c in tp_cells if c.tok_s_out_min is not None]
        ymax = [c.tok_s_out_max for c in tp_cells if c.tok_s_out_max is not None]
        if not xs:
            continue
        ax.plot(
            xs,
            ys,
            marker=markers.get(tp, "x"),
            linewidth=2,
            color=colors.get(tp, "black"),
            label=f"TP={tp} (median, n_reps={cfg.reps})",
        )
        if len(ymin) == len(xs):
            ax.fill_between(xs, ymin, ymax, color=colors.get(tp, "black"), alpha=0.15)

    ax.set_xscale("log")
    ax.set_xlabel("Concurrent prompts (N)")
    ax.set_ylabel("Output throughput (tok/s, median across reps)")
    ax.set_title(
        f"{cfg.model_label} {cfg.quant} — Phase 2 scaling "
        f"(TP ladder {cfg.tp_ladder}, 2× R9700 gfx1201)"
    )
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"  PNG → {_rel(path)}")


def plot_latency_p99(cells: list[CellAggregate], path: Path, cfg: Config) -> None:
    by_tp = _by_tp(cells)
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = {1: "#1f77b4", 2: "#d62728"}
    for tp, tp_cells in sorted(by_tp.items()):
        xs = [c.n for c in tp_cells if c.per_req_latency_p99 is not None]
        ys99 = [
            c.per_req_latency_p99 for c in tp_cells if c.per_req_latency_p99 is not None
        ]
        ys50 = [
            c.per_req_latency_median
            for c in tp_cells
            if c.per_req_latency_p99 is not None
        ]
        if not xs:
            continue
        ax.plot(
            xs,
            ys99,
            marker="o",
            linewidth=2,
            color=colors.get(tp, "black"),
            label=f"TP={tp} p99",
        )
        ax.plot(
            xs,
            ys50,
            marker="o",
            linewidth=1,
            linestyle="--",
            color=colors.get(tp, "black"),
            alpha=0.6,
            label=f"TP={tp} median",
        )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Concurrent prompts (N)")
    ax.set_ylabel("Per-request wall time proxy (s) — total_s / N")
    ax.set_title(
        f"{cfg.model_label} {cfg.quant} — Tail latency (median + p99 across reps)"
    )
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"  PNG → {_rel(path)}")


def plot_power_efficiency(cells: list[CellAggregate], path: Path, cfg: Config) -> None:
    by_tp = _by_tp(cells)
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = {1: "#1f77b4", 2: "#d62728"}
    for tp, tp_cells in sorted(by_tp.items()):
        xs, ys = [], []
        for c in tp_cells:
            if c.tok_s_out_median and c.w_mean_median:
                xs.append(c.n)
                ys.append(c.tok_s_out_median / c.w_mean_median)
        if not xs:
            continue
        ax.plot(
            xs,
            ys,
            marker="^",
            linewidth=2,
            color=colors.get(tp, "black"),
            label=f"TP={tp}",
        )
    ax.set_xscale("log")
    ax.set_xlabel("Concurrent prompts (N)")
    ax.set_ylabel("Aggregate efficiency (tok/s per W)")
    ax.set_title(f"{cfg.model_label} {cfg.quant} — Power efficiency (tok/s/W, median)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"  PNG → {_rel(path)}")


def plot_thermal_gallery(cells: list[CellAggregate], path: Path, cfg: Config) -> None:
    by_tp = _by_tp(cells)
    # Columns = the TPs that actually have cells, in ladder order (then any
    # extra observed TPs). Avoids empty columns crashing on partial sweeps.
    tp_cols = [tp for tp in cfg.tp_ladder if by_tp.get(tp)]
    for tp in sorted(by_tp):
        if tp not in tp_cols:
            tp_cols.append(tp)
    if not tp_cols:
        return
    n_rows = max(len(by_tp.get(tp, [])) for tp in tp_cols)
    n_cols = len(tp_cols)
    if n_rows == 0:
        return

    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(6 * n_cols, 1.8 * n_rows), sharex=False, squeeze=False
    )

    for col, tp in enumerate(tp_cols):
        tp_cells = by_tp.get(tp, [])
        for row, c in enumerate(tp_cells):
            ax = axes[row][col]
            # Use first OK rep for the trace (the median run is harder to ID
            # without re-scanning; the gallery shows representative shape).
            ok_reps = [r for r in c.reps if r.ok]
            if not ok_reps:
                ax.set_title(f"TP={tp} N={c.n} (no data)")
                continue
            r0 = ok_reps[0]
            # Reconstruct the per-rep filename from the rep's own filename
            # quant prefix (e.g. "bf16" / "awq"), NOT the --quant label.
            base = f"{r0.fname_quant}-tp{tp}-n{c.n}-r{r0.rep:02d}"
            jp = cfg.thermal_dir / f"{base}-thermals.jsonl"
            if not jp.exists():
                ax.set_title(f"TP={tp} N={c.n} (no thermals file)")
                continue
            rows_t = []
            for line in jp.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows_t.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            if not rows_t:
                ax.set_title(f"TP={tp} N={c.n} (empty thermals)")
                continue
            ts = [r["t"] for r in rows_t]
            non_igpu_idx = [
                i
                for i, g in enumerate(rows_t[0].get("gpus", []) or [])
                if not g.get("is_igpu")
            ]
            colors_g = ["#1f77b4", "#ff7f0e"]
            for k, list_idx in enumerate(non_igpu_idx[:2]):
                temps = [
                    (
                        r["gpus"][list_idx]["temp"]
                        if len(r.get("gpus", [])) > list_idx
                        else None
                    )
                    for r in rows_t
                ]
                ax.plot(
                    ts,
                    temps,
                    color=colors_g[k % len(colors_g)],
                    linewidth=1.2,
                    label=f"GPU{k} T",
                )
            ax.set_ylabel("Temp °C", fontsize=8)
            ax.grid(True, alpha=0.3)

            ax2 = ax.twinx()
            for k, list_idx in enumerate(non_igpu_idx[:2]):
                powers = [
                    (
                        r["gpus"][list_idx]["power_w"]
                        if len(r.get("gpus", [])) > list_idx
                        else None
                    )
                    for r in rows_t
                ]
                ax2.plot(
                    ts,
                    powers,
                    color=colors_g[k % len(colors_g)],
                    linewidth=1.0,
                    linestyle="--",
                    alpha=0.7,
                )
            ax2.set_ylabel("W", fontsize=8)
            ax.set_title(f"TP={tp} N={c.n}", loc="left", fontsize=9)

        # Hide unused subplots
        for row in range(len(tp_cells), n_rows):
            axes[row][col].set_visible(False)

    fig.suptitle(
        f"{cfg.model_label} {cfg.quant} — Thermal gallery (first OK rep per cell)",
        fontsize=11,
        y=1.0,
    )
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"  PNG → {_rel(path)}")


# ============================================================
# SUMMARY.md
# ============================================================


def _detect_knee(tp_cells: list[CellAggregate]) -> Optional[int]:
    """Return N at which efficiency drops below 50% of N-doubled extrapolation."""
    ok = [c for c in tp_cells if c.tok_s_out_median is not None]
    if len(ok) < 2:
        return None
    for i in range(1, len(ok)):
        n_ratio = ok[i].n / ok[i - 1].n
        tp_ratio = ok[i].tok_s_out_median / ok[i - 1].tok_s_out_median
        if (tp_ratio / n_ratio) < 0.5:
            return ok[i - 1].n
    return None


def _detect_crossover(cells: list[CellAggregate]) -> Optional[int]:
    by_tp = _by_tp(cells)
    if 1 not in by_tp or 2 not in by_tp:
        return None
    by_n_tp1 = {c.n: c.tok_s_out_median for c in by_tp[1] if c.tok_s_out_median}
    by_n_tp2 = {c.n: c.tok_s_out_median for c in by_tp[2] if c.tok_s_out_median}
    common = sorted(set(by_n_tp1) & set(by_n_tp2))
    for n in common:
        if by_n_tp2[n] > by_n_tp1[n]:
            return n
    return None


def emit_summary(
    cells: list[CellAggregate], reps: list[RepRecord], cfg: Config
) -> None:
    by_tp = _by_tp(cells)
    knees = {tp: _detect_knee(by_tp.get(tp, [])) for tp in cfg.tp_ladder}
    crossover = _detect_crossover(cells)

    # Max thermal observation across all reps
    all_temps = [r.t_peak_c for r in reps if r.t_peak_c is not None]
    max_temp = max(all_temps) if all_temps else None
    throttle_events = sum(1 for t in all_temps if t > 95.0)

    # Power envelope
    all_w_peak = [r.w_peak for r in reps if r.w_peak is not None]
    all_w_mean = [r.w_mean for r in reps if r.w_mean is not None]
    avg_w = statistics.mean(all_w_mean) if all_w_mean else None
    peak_w = max(all_w_peak) if all_w_peak else None

    # Best tok/s/W per TP
    best_eff = {}
    for tp, tp_cells in by_tp.items():
        eff_pairs = [
            (c.n, c.tok_s_out_median / c.w_mean_median)
            for c in tp_cells
            if c.tok_s_out_median and c.w_mean_median
        ]
        if eff_pairs:
            best = max(eff_pairs, key=lambda x: x[1])
            best_eff[tp] = best

    # Build per-TP markdown tables
    def _fmt_table(tp_cells: list[CellAggregate]) -> str:
        if not tp_cells:
            return "_no data_"
        header = (
            "| N | n_ok | tok/s out (median) | min | max | "
            "total_s (median) | p95 | p99 | "
            "req/s | per_req_s p99 | "
            "VRAM_GB | T_peak | W_mean | W_peak | mWh/tok |"
        )
        sep = "|" + "|".join(["---"] * 15) + "|"
        rows = []
        for c in tp_cells:
            mwh = (
                f"{c.w_per_tok_wh_median * 1000:.3f}"
                if c.w_per_tok_wh_median is not None
                else "n/a"
            )
            rows.append(
                f"| {c.n} | {c.n_runs_ok} | "
                f"{_fmt(c.tok_s_out_median, 1)} | "
                f"{_fmt(c.tok_s_out_min, 1)} | "
                f"{_fmt(c.tok_s_out_max, 1)} | "
                f"{_fmt(c.total_s_median, 2)} | "
                f"{_fmt(c.total_s_p95, 2)} | "
                f"{_fmt(c.total_s_p99, 2)} | "
                f"{_fmt(c.req_s_median, 3)} | "
                f"{_fmt(c.per_req_latency_p99, 3)} | "
                f"{_fmt(c.vram_peak_gib_median, 1)} | "
                f"{_fmt(c.t_peak_c_max, 1)} | "
                f"{_fmt(c.w_mean_median, 0)} | "
                f"{_fmt(c.w_peak_max, 0)} | "
                f"{mwh} |"
            )
        return "\n".join([header, sep, *rows])

    knee_text = {}
    for tp in cfg.tp_ladder:
        knee_text[tp] = (
            f"Knee at N={knees[tp]}"
            if knees.get(tp)
            else "No clear knee within tested range — scales sub-linearly throughout"
        )
    crossover_text = (
        f"TP=2 first exceeds TP=1 throughput at N={crossover}"
        if crossover
        else "TP=2 did not exceed TP=1 throughput at any tested N "
        "(possible: crossover occurs outside the tested range, "
        "or TP=2 AllReduce overhead dominates throughout)"
    )

    best_eff_text = "\n".join(
        f"  - TP={tp}: best at N={n}, {eff:.3f} tok/s per W"
        for tp, (n, eff) in sorted(best_eff.items())
    )

    # Per-TP results sections (one per TP in the ladder).
    results_sections = "\n".join(
        f"## Results — TP={tp} (EMBARGO_paper_bound — Polish model, §11.3)\n\n"
        f"{_fmt_table(by_tp.get(tp, []))}\n"
        for tp in cfg.tp_ladder
    )

    # Per-TP engineering scaling lines.
    scaling_lines = "\n".join(
        f"- **TP={tp} scaling regime:** {knee_text[tp]}." for tp in cfg.tp_ladder
    )

    orch_log = cfg.results_dir / "logs/orchestrator.log"
    sweep_date = orch_log.stat().st_mtime if orch_log.exists() else "(in-progress)"
    n_set = "{" + ",".join(str(n) for n in cfg.n_ladder) + "}"
    tp_set = "{" + ",".join(str(t) for t in cfg.tp_ladder) + "}"

    md = f"""{EMBARGO_HEADER.rstrip()}

# {cfg.model_label} {cfg.quant} — Phase 2 sweep summary

**Sweep ID:** `{cfg.model_label}-{cfg.quant.lower()}-tp{tp_set}-max{cfg.max_len}-n{n_set}-r{cfg.reps}`
**Date:** {sweep_date}
**Operator:** Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>
**Methodology:** METHODOLOGY.md v1.0 §5.2 (Phase 2 scaling sweep)
**Embargo:** Mixed per §11.1/§11.2/§11.3 — see classification below.

## ⚠ Embargo classification (METHODOLOGY §11.4)

**EMBARGO_paper_bound** for all concrete throughput, latency, thermal, and
power numbers (Polish model, stricter embargo per §11.3). Engineering
observations (knee shape, vLLM scheduler robustness, preemption regime onset,
TP=1 vs TP=2 trade-off, thermal headroom) are PUBLIC.

## N-ladder note (transparency, METHODOLOGY §5.2)

The canonical Phase 2 ladder is N ∈ {{10, 25, 50, 100, 200, 500, 1000}}.
This sweep used N ∈ {n_set} at n_reps={cfg.reps} per cell (median + p95/p99
stats) to fit the overnight wall-time budget. Cross-suite comparability with
other model sweeps may require re-running at the canonical ladder before paper
synthesis — flagged as paper TODO.

## Methodological humility (METHODOLOGY §8, Lerchner 2026)

We measure inference *throughput*, *latency*, *thermal envelope*, and *power
efficiency* under varying concurrent load. We do not measure model quality,
reasoning capability, factual accuracy, or downstream clinical utility.
Following Lerchner (2026), these are extrinsic computational properties of
the inference vehicle, not constitutive properties of cognition. Our claims
terminate at the hardware-software interface.

## Configuration

- Model: `{cfg.model_name}`
- Model label: `{cfg.model_label}`
- Quantization: {cfg.quant}
- Backend: {cfg.backend}
- Tensor parallel sizes: {cfg.tp_ladder}
- max_model_len: {cfg.max_len}
- gpu_memory_utilization: {cfg.util}
- KV cache dtype: {cfg.kv_dtype}
- enforce_eager: True (graphs path segfaults on gfx1201; per METHODOLOGY §3.2)
- N ladder: {cfg.n_ladder}
- Reps per cell: {cfg.reps} (median + p95/p99 statistics)
- Cooldown between runs: 30s

{results_sections}
## Engineering observations (PUBLIC)

{scaling_lines}
- **TP=1 vs TP=2 crossover:** {crossover_text}.
- **Thermal envelope:** peak GPU temperature across all {len(reps)} runs was
  {f'{max_temp:.1f}°C' if max_temp else 'n/a'}. Throttle events
  (>95°C): {throttle_events}.
- **Power envelope:** mean {f'{avg_w:.0f} W' if avg_w else 'n/a'} across run windows,
  peak {f'{peak_w:.0f} W' if peak_w else 'n/a'}. 1650 W PSU headroom comfortable for 2× R9700.
- **Best efficiency (tok/s per W) operating points:**
{best_eff_text or "  - (no efficiency data)"}

## Statistical methodology

- Per-cell aggregates use **median** across {cfg.reps} reps (robust to
  outliers from one-shot vLLM cold-start variance).
- p95 / p99 computed by **nearest-rank percentile** on n={cfg.reps}
  samples (suitable for small n; p99 ≈ max). For paper-grade tail latency
  characterization, per-request timestamps from vLLM AsyncEngine logging
  will be required (future enhancement, flagged in §10).
- No formal statistical test (Holm-Bonferroni) is applied at this stage —
  the small n_reps={cfg.reps} per cell is intended for **point estimate
  stability**, not for inferential tests across N. Cross-N or cross-TP
  significance testing belongs to the paper-grade analysis with larger
  n_reps or bootstrap CIs.
- `per_req_latency` is computed as `total_s / N` (i.e. aggregate wall time
  divided by request count) as a **proxy** for per-request latency. True
  per-request P50/P95/P99 requires AsyncEngine timestamp extraction.

## Plots

- `scaling_curve.png` — `tok/s_out_median` vs `N` (log-x), all TPs with
  min/max ribbon
- `latency_p99.png` — per-request wall time proxy, median + p99, all TPs
- `power_efficiency.png` — `tok/s_median / W_mean_median` vs `N`, all TPs
- `thermal_gallery.png` — per-cell temperature + power traces (first OK rep
  per cell), one column per TP

## Files

- `phase2_sweep.csv` — per-cell aggregates, all TPs
- `phase2_sweep_tp{{TP}}.csv` — per-TP cells (one file per TP in the ladder)
- `phase2_sweep_raw.csv` — per-rep raw data (n={cfg.reps} × N × TP)
- `logs/orchestrator.log` — orchestrator wall log
- `thermal-runs/` — per-run bench.log, events.json, thermals.jsonl, thermals.png
- `methodology_compliance.json` — Kim et al. 2026 AI disclosure + Lerchner 2026 humility

## Limitations (METHODOLOGY §10)

All ten standing limitations from METHODOLOGY §10 apply. Specific emphases:
- §10.1 synthetic prompts (apples-to-apples cross-model, not clinical)
- §10.5 single-batch concurrency (not Poisson arrival)
- §10.6 1 Hz power sampling (sub-second transients lost)
- §10.10 Polish-language model lacks public R9700 baseline — comparisons
  are within-model only

## AI usage disclosure (METHODOLOGY §9, Kim et al. 2026)

| Layer | Disclosure |
|---|---|
| 1 — Dataset / data generation | N/A. Synthetic prompts per §6, deterministic from human-curated templates × topics, byte-for-byte identical to other model sweeps. |
| 2 — Experimental pipeline | Claude (Anthropic, via Claude Code) used as Phase 2 sweep sub-orchestrator. Specific role: orchestrator + finalize script generation following METHODOLOGY.md §5.2/§7. All decision criteria (N ladder, n_reps, statistical aggregation method) pre-specified in task brief before sweep launch. No autonomous decisions on experimental design. |
| 3 — Manuscript editing | TBD per paper submission. |

## Reproducibility (METHODOLOGY §3.3)

- vLLM {cfg.backend} (pinned)
- Env (per `scripts/_env.sh`): `AMD_SERIALIZE_KERNEL=1`,
  `ROCR_VISIBLE_DEVICES=0,1`, `VLLM_ROCM_USE_AITER=0`,
  `HIP_LAUNCH_BLOCKING=1`, `PYTORCH_ALLOC_CONF=unset`
- Hardware: 2× AMD Radeon AI PRO R9700 (gfx1201, 32 GiB each), 1650 W PSU
- iGPU (RAPHAEL) excluded from sampling per METHODOLOGY §2

## Next steps (paper-bound, EMBARGOED)

1. Re-run at canonical METHODOLOGY ladder N ∈ {{10, 25, 50, 100, 200, 500, 1000}}
   for cross-model paper figures
2. Extract per-request P50/P95/P99 latency from vLLM AsyncEngine logs
   (currently using aggregate total_s/N proxy)
3. Cross-quantization comparison on identical N ladder
4. Energy-optimal operating point identification across full N grid
   (currently best within tested points only)
"""
    path = cfg.out_dir / "SUMMARY.md"
    path.write_text(md)
    print(f"  MD  → {_rel(path)}")


# ============================================================
# Methodology compliance JSON
# ============================================================


def emit_methodology_compliance(reps: list[RepRecord], cfg: Config) -> None:
    n_total = len(reps)
    n_ok = sum(1 for r in reps if r.ok)
    out = {
        "embargo": "EMBARGO_paper_bound",
        "embargo_rationale": "Polish-language model per METHODOLOGY §11.3 (Bielik scoop risk).",
        "methodology_version": "v1.0",
        "phase": "2_scaling_sweep",
        "model_label": cfg.model_label,
        "model_name": cfg.model_name,
        "quant": cfg.quant,
        "n_reps_per_cell_target": cfg.reps,
        "n_runs_total_planned": cfg.reps * len(cfg.n_ladder) * len(cfg.tp_ladder),
        "n_runs_completed": n_ok,
        "n_runs_failed": n_total - n_ok,
        "n_ladder": cfg.n_ladder,
        "tp_ladder": cfg.tp_ladder,
        "kim_2026_disclosure": {
            "layer_1_data": "N/A — synthetic prompts per METHODOLOGY §6",
            "layer_2_pipeline": (
                "Claude (Anthropic, via Claude Code) generated "
                "orchestrator + finalize scripts following METHODOLOGY.md "
                "§5.2/§7. All design parameters (N ladder, n_reps, stats) "
                "pre-specified in human task brief before sweep launch."
            ),
            "layer_3_manuscript": "TBD per paper submission",
        },
        "lerchner_2026_humility": (
            "Measurements are extrinsic computational properties of the "
            "inference vehicle (throughput, latency, power, thermal). They "
            "do not constitute claims about model quality, reasoning, "
            "factual accuracy, or downstream clinical utility. All claims "
            "terminate at the hardware-software interface."
        ),
    }
    path = cfg.out_dir / "methodology_compliance.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"  JSON → {_rel(path)}")


# ============================================================
# Argument parsing / config
# ============================================================


def _parse_int_list(s: str) -> list[int]:
    return [int(x) for x in s.split(",") if x.strip() != ""]


def parse_args(argv: Optional[list[str]] = None) -> Config:
    p = argparse.ArgumentParser(
        description="Parameterized Phase 2 finalize (generalization of "
        "finalize_bielik_11b_v30_phase2.py).",
    )
    p.add_argument(
        "--results-dir",
        required=True,
        help="Path to benchmarks/results/<MODEL> (thermal-runs/ lives underneath).",
    )
    p.add_argument("--model-label", required=True, help="Short model key/label.")
    p.add_argument("--model-name", required=True, help="HF model name / id.")
    p.add_argument(
        "--quant", default="awq", help="Quant label for CSV/MD (default awq)."
    )
    p.add_argument(
        "--backend",
        default="vllm-0.19.0+rocm721",
        help="Backend string for CSV/MD (default vllm-0.19.0+rocm721).",
    )
    p.add_argument("--max-len", type=int, required=True, help="max_model_len.")
    p.add_argument("--util", type=float, required=True, help="gpu_memory_utilization.")
    p.add_argument(
        "--kv-dtype", default="auto", help="KV cache dtype label (default auto)."
    )
    p.add_argument(
        "--tuning", default="stock", help="Tuning label for CSV (default stock)."
    )
    p.add_argument(
        "--n-ladder",
        default="5,10,25,50,100,250",
        help="Comma-separated N ladder (default 5,10,25,50,100,250).",
    )
    p.add_argument(
        "--tp-ladder",
        default="1,2",
        help="Comma-separated TP ladder (default 1,2).",
    )
    p.add_argument(
        "--reps", type=int, default=10, help="Reps expected per cell (default 10)."
    )
    p.add_argument(
        "--out-dir",
        default=None,
        help="Output directory (default = --results-dir, beside thermal-runs/).",
    )
    args = p.parse_args(argv)

    results_dir = Path(args.results_dir).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else results_dir
    return Config(
        results_dir=results_dir,
        out_dir=out_dir,
        thermal_dir=results_dir / "thermal-runs",
        model_label=args.model_label,
        model_name=args.model_name,
        quant=args.quant,
        backend=args.backend,
        max_len=args.max_len,
        util=args.util,
        kv_dtype=args.kv_dtype,
        tuning=args.tuning,
        n_ladder=_parse_int_list(args.n_ladder),
        tp_ladder=_parse_int_list(args.tp_ladder),
        reps=args.reps,
    )


# ============================================================
# Main
# ============================================================


def main(argv: Optional[list[str]] = None) -> int:
    cfg = parse_args(argv)

    if not cfg.thermal_dir.exists():
        print(f"ERROR: missing {cfg.thermal_dir}", file=sys.stderr)
        return 2

    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"{cfg.model_label} {cfg.quant} Phase 2 finalize (generic)")
    print(f"Reading from: {_rel(cfg.thermal_dir)}")
    print(f"Writing to:   {_rel(cfg.out_dir)}")
    print("=" * 60)

    reps = build_reps(cfg)
    if not reps:
        print("ERROR: no rep records parsed", file=sys.stderr)
        return 3

    cells = aggregate_cells(reps)

    print(f"\nParsed {len(reps)} rep runs into {len(cells)} cells:")
    for c in cells:
        print(
            f"  TP={c.tp} N={c.n:4d}  n_ok={c.n_runs_ok:2d} "
            f"tok/s median={c.tok_s_out_median} "
            f"(min={c.tok_s_out_min}, max={c.tok_s_out_max}) "
            f"T_peak_max={c.t_peak_c_max}"
        )

    print("\nEmitting outputs:")
    emit_csvs(cells, reps, cfg)
    plot_scaling(cells, cfg.out_dir / "scaling_curve.png", cfg)
    plot_latency_p99(cells, cfg.out_dir / "latency_p99.png", cfg)
    plot_power_efficiency(cells, cfg.out_dir / "power_efficiency.png", cfg)
    plot_thermal_gallery(cells, cfg.out_dir / "thermal_gallery.png", cfg)
    emit_summary(cells, reps, cfg)
    emit_methodology_compliance(reps, cfg)

    print("\n" + "=" * 60)
    print("Phase 2 finalize complete.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
