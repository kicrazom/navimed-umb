#!/usr/bin/env python3
"""Wykres porównawczy A/B chłodzenia 9950X3D. Użycie:
   plot_cooling_ab.py <csv_A> <csv_B> <outdir>   -> generuje PNG w pl i en
Metryka główna: ΔT nad otoczeniem (przebiegi mają różny ambient, więc surowe Tctl
nie jest porównywalne). ponytail: dwa panele zamiast dual-axis."""

import csv
import glob
import re
import sys
import pathlib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

S1, S2 = "#2a78d6", "#eb6834"  # slot 1/2 palety kategorycznej (adjacent CVD ΔE 9.1)
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#b8b7b0"
SURFACE = "#fcfcfb"

STR = {
    "pl": dict(
        title="Chłodzenie 9950X3D: NH-D15 G2 vs LC1-42",
        sub="ΔT nad otoczeniem — przebiegi mają różny ambient, więc surowe Tctl nie jest porównywalne",
        x="czas [min]",
        y1="ΔT nad otoczeniem [K]",
        y2="zegar [MHz]",
        ph=["bezczynność", "obciążenie (stress-ng)", "stygnięcie"],
        amb="otoczenie",
        note="Niżej = lepiej",
        dec=",",
    ),
    "en": dict(
        title="9950X3D cooling: NH-D15 G2 vs LC1-42",
        sub="ΔT above ambient — runs differ in ambient, so raw Tctl is not comparable",
        x="time [min]",
        y1="ΔT above ambient [K]",
        y2="clock [MHz]",
        ph=["idle", "load (stress-ng)", "cooldown"],
        amb="ambient",
        note="Lower is better",
        dec=".",
    ),
}


def load(path):
    amb, rows = None, []
    with open(path) as f:
        for line in f:
            if line.startswith("#"):
                m = re.search(r"ambient=([\d.]+)C", line)
                if m:
                    amb = float(m.group(1))
                continue
            rows.append(line)
    r = list(csv.DictReader(rows))
    t0 = int(r[0]["epoch"])
    out = []
    for x in r:
        try:
            tctl = float(x["tctl"])
            mhz = float(x["mhz_avg"])
        except (ValueError, TypeError):
            continue
        out.append(((int(x["epoch"]) - t0) / 60.0, x["phase"], tctl, tctl - amb, mhz))
    return amb, out


def stats(rows, amb):
    idle = [r[3] for r in rows if r[1] == "idle"][-60:]
    load = [r for r in rows if r[1] == "load"][-120:]
    return dict(
        ambient=amb,
        idle_dt=sum(idle) / len(idle),
        load_dt=sum(r[3] for r in load) / len(load),
        load_max=max(r[2] for r in rows if r[1] == "load"),
        mhz=sum(r[4] for r in load) / len(load),
    )


def plot(a, b, sa, sb, lang, out):
    s = STR[lang]
    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(10, 7.2),
        sharex=True,
        gridspec_kw=dict(height_ratios=[2.4, 1], hspace=0.13),
    )
    fig.patch.set_facecolor(SURFACE)
    for ax in (ax1, ax2):
        ax.set_facecolor(SURFACE)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(MUTED)
        ax.grid(axis="y", color=MUTED, lw=0.6, alpha=0.45)
        ax.tick_params(colors=INK2, labelsize=9, length=0)

    ax1.axvspan(10, 50, color=MUTED, alpha=0.15, lw=0)  # tylko faza obciążenia
    for x, lab in ((5, s["ph"][0]), (30, s["ph"][1]), (55, s["ph"][2])):
        ax1.text(
            x,
            0.975,
            lab,
            transform=ax1.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=8.5,
            color=INK2,
        )

    ends = []
    for rows, col, name in ((a, S1, "NH-D15 G2"), (b, S2, "LC1-42")):
        ax1.plot(
            [r[0] for r in rows],
            [r[3] for r in rows],
            color=col,
            lw=2,
            solid_capstyle="round",
        )
        ax2.plot(
            [r[0] for r in rows],
            [r[4] for r in rows],
            color=col,
            lw=2,
            solid_capstyle="round",
        )
        ends.append([rows[-1][0], rows[-1][3], col, name])
    if abs(ends[0][1] - ends[1][1]) < 1.4:  # rozsuń kolidujące etykiety
        hi = 0 if ends[0][1] >= ends[1][1] else 1
        ends[hi][1] += 0.8
        ends[1 - hi][1] -= 0.8
    for x, y, col, name in ends:
        ax1.text(
            x + 0.8, y, name, color=col, fontsize=9.5, va="center", fontweight="bold"
        )

    ax1.set_ylabel(s["y1"], color=INK2, fontsize=10)
    ax2.set_ylabel(s["y2"], color=INK2, fontsize=10)
    ax2.set_xlabel(s["x"], color=INK2, fontsize=10)
    ax1.set_xlim(0, 66)

    fig.text(
        0.075, 0.965, s["title"], fontsize=15, fontweight="bold", color=INK, va="top"
    )
    fig.text(0.075, 0.925, s["sub"], fontsize=9.5, color=INK2, va="top")
    fig.legend(
        handles=[
            Patch(facecolor=S1, label=f"NH-D15 G2 ({s['amb']} {sa['ambient']:g} °C)"),
            Patch(facecolor=S2, label=f"LC1-42 ({s['amb']} {sb['ambient']:g} °C)"),
        ],
        loc="upper left",
        bbox_to_anchor=(0.073, 0.905),
        ncol=2,
        frameon=False,
        fontsize=9.5,
        labelcolor=INK2,
    )
    ax1.text(
        0.995,
        0.905,
        s["note"],
        transform=ax1.transAxes,
        ha="right",
        fontsize=8.5,
        color=MUTED,
        style="italic",
    )
    fig.subplots_adjust(top=0.83, bottom=0.09, left=0.09, right=0.9)
    fig.savefig(out, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return out


MD = {
    "pl": dict(
        f="podsumowanie-pl.md",
        h="# Chłodzenie 9950X3D — A/B: NH-D15 G2 vs LC1-42",
        cols=["Metryka", "NH-D15 G2 (A)", "LC1-42 (B)", "Δ (B−A)"],
        rows=[
            "otoczenie [°C]",
            "ΔT bezczynność [K]",
            "ΔT obciążenie [K]",
            "Tctl max [°C]",
            "zegar pod obciążeniem [MHz]",
            "bogo-ops/s",
        ],
        note=(
            "Metryką porównawczą jest **ΔT nad otoczeniem** — przebiegi wykonano przy różnym ambiencie, "
            "więc surowe Tctl nie jest porównywalne. Warunki stałe: 9950X3D, stress-ng matrixprod na wszystkich "
            "wątkach, 40 min obciążenia, BIOS i krzywe wentylatorów bez zmian, GPU bezczynne (vLLM zatrzymany).\n\n"
            "**Obroty pompy niedostępne w przebiegu B** — `asus-ec-sensors` eksponuje na tej płycie wyłącznie "
            "kanał `CPU_Opt`, a pompa AIO siedzi na headerze `AIO_PUMP`, którego sterownik nie wystawia. "
            "Kolumna RPM to `NA`, nie zero."
        ),
    ),
    "en": dict(
        f="summary-en.md",
        h="# 9950X3D cooling — A/B: NH-D15 G2 vs LC1-42",
        cols=["Metric", "NH-D15 G2 (A)", "LC1-42 (B)", "Δ (B−A)"],
        rows=[
            "ambient [°C]",
            "ΔT idle [K]",
            "ΔT load [K]",
            "Tctl max [°C]",
            "clock under load [MHz]",
            "bogo-ops/s",
        ],
        note=(
            "The comparison metric is **ΔT above ambient** — the runs were made at different ambient "
            "temperatures, so raw Tctl is not comparable. Held constant: 9950X3D, stress-ng matrixprod on all "
            "threads, 40 min load, BIOS and fan curves unchanged, GPUs idle (vLLM stopped).\n\n"
            "**Pump RPM is unavailable for run B** — `asus-ec-sensors` exposes only the `CPU_Opt` channel on this "
            "board, while the AIO pump sits on the `AIO_PUMP` header the driver does not expose. "
            "The RPM column is `NA`, not zero."
        ),
    ),
}


def bogo(tag):
    f = sorted(glob.glob(f"stressng_{tag}_*.log"))
    if not f:
        return None
    m = re.findall(
        r"metrc:.*?\]\s+cpu\s+\d+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)",
        pathlib.Path(f[-1]).read_text(),
    )
    return float(m[-1]) if m else None


def write_md(sa, sb, ba, bb, lang, outdir):
    d = MD[lang]
    vals = [
        (sa["ambient"], sb["ambient"], 1),
        (sa["idle_dt"], sb["idle_dt"], 1),
        (sa["load_dt"], sb["load_dt"], 1),
        (sa["load_max"], sb["load_max"], 1),
        (sa["mhz"], sb["mhz"], 0),
        (ba, bb, 0),
    ]
    lines = [d["h"], "", "| " + " | ".join(d["cols"]) + " |", "|---|---:|---:|---:|"]
    for name, (va, vb, prec) in zip(d["rows"], vals):
        if va is None or vb is None:
            lines.append(f"| {name} | — | — | — |")
            continue
        delta = vb - va
        lines.append(f"| {name} | {va:.{prec}f} | {vb:.{prec}f} | {delta:+.{prec}f} |")
    lines += ["", d["note"], ""]
    (outdir / d["f"]).write_text("\n".join(lines))
    return outdir / d["f"]


if __name__ == "__main__":
    ca, cb, outdir = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
    outdir.mkdir(parents=True, exist_ok=True)
    amb_a, ra = load(ca)
    amb_b, rb = load(cb)
    sa, sb = stats(ra, amb_a), stats(rb, amb_b)
    ba, bb = (
        bogo(pathlib.Path(ca).name.split("_")[0]),
        bogo(pathlib.Path(cb).name.split("_")[0]),
    )
    for lang in ("pl", "en"):
        print(plot(ra, rb, sa, sb, lang, outdir / f"chlodzenie-AB-{lang}.png"))
        print(write_md(sa, sb, ba, bb, lang, outdir))
    print("A:", {k: round(v, 1) for k, v in sa.items()})
    print("B:", {k: round(v, 1) for k, v in sb.items()})
