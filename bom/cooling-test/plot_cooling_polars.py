#!/usr/bin/env python3
"""Wykres NH-D15 G2 vs NL-LC1-42 — obróbka w Polars, rendering w matplotlib.

Użycie: plot_cooling_polars.py [outdir]      (domyślnie ~/Pulpit/chlodzenie-cpu-AB)

Metryka główna: ΔT nad otoczeniem — przebiegi mają różny ambient, więc surowe Tctl
nie jest porównywalne. Przebieg B (wentylatory chłodnicy 0 RPM) jest NIEWAŻNY i rysowany
przerywaną linią wyłącznie jako kontrola negatywna.
"""

import re
import sys
import pathlib
import polars as pl
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = pathlib.Path(__file__).parent
OUT = pathlib.Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else pathlib.Path.home() / "Pulpit" / "chlodzenie-cpu-AB"
)

D15, LC, BAD, INK, GRID = "#c2703d", "#3d84c2", "#8a8a86", "#12100f", "#d8d5cf"

RUNS = [  # plik, klucz, ważny
    ("noctua_20260731-2232.csv", "d15", True),
    ("lc142-fanC_20260823-0833.csv", "lc", True),
    ("lc142_20260823-0035.csv", "bad", False),
]

STR = {
    "pl": dict(
        t="Chłodzenie 9950X3D: NH-D15 G2 vs NL-LC1-42",
        sub="ΔT nad otoczeniem — przebiegi miały różny ambient, więc surowe Tctl nie jest porównywalne",
        x="czas [min]",
        y1="ΔT nad otoczeniem [K]",
        y2="zegar [MHz]",
        d15="NH-D15 G2 — powietrze",
        lc="NL-LC1-42 — ciecz",
        bad="NL-LC1-42 z zatrzymanymi wentylatorami (przebieg nieważny)",
        load="obciążenie stress-ng",
        note="Niżej = lepiej",
    ),
    "en": dict(
        t="9950X3D cooling: NH-D15 G2 vs NL-LC1-42",
        sub="ΔT above ambient — runs differ in ambient, so raw Tctl is not comparable",
        x="time [min]",
        y1="ΔT above ambient [K]",
        y2="clock [MHz]",
        d15="NH-D15 G2 — air",
        lc="NL-LC1-42 — liquid",
        bad="NL-LC1-42 with stopped fans (invalid run)",
        load="stress-ng load",
        note="Lower is better",
    ),
}


def ambient(path: pathlib.Path) -> float:
    for line in path.open():
        if line.startswith("#"):
            m = re.search(r"ambient=([\d.]+)C", line)
            if m:
                return float(m.group(1))
    raise ValueError(f"brak ambient w nagłówku {path.name}")


def load(path: pathlib.Path, key: str) -> pl.DataFrame:
    amb = ambient(path)
    return (
        pl.read_csv(path, comment_prefix="#")
        .with_columns(
            ((pl.col("epoch") - pl.col("epoch").min()) / 60).alias("min"),
            (pl.col("tctl") - amb).alias("dt"),
            pl.lit(amb).alias("ambient"),
            pl.lit(key).alias("run"),
            # ponytail: w nieważnym przebiegu kolumna to łańcuch "NA" -> schematy się nie sklejają
            pl.col("cpu_fan_rpm").cast(pl.Float64, strict=False).alias("cpu_fan_rpm"),
        )
        # ponytail: zegar próbkowany co 5 s szumi; okno 12 próbek = 1 min
        .with_columns(pl.col("mhz_avg").rolling_mean(12, min_samples=1).alias("mhz_s"))
    )


frames = {k: load(HERE / f, k) for f, k, _ in RUNS}
df = pl.concat(frames.values())

# statystyki tymi samymi oknami co cooling_ab_test.sh: idle ost. 5 min, load ost. 10 min
stats = (
    df.filter(pl.col("phase") == "load")
    .group_by("run")
    .agg(
        pl.col("dt").tail(120).mean().round(1).alias("dT_load_K"),
        pl.col("tctl").max().alias("Tctl_max_C"),
        pl.col("mhz_avg").tail(120).mean().round(0).alias("MHz"),
        pl.col("cpu_fan_rpm").tail(120).mean().round(0).alias("RPM"),
        pl.col("ambient").first().alias("ambient_C"),
    )
    .sort("run")
)
print(stats)


def draw(lang: str) -> pathlib.Path:
    s = STR[lang]
    fig, (a1, a2) = plt.subplots(
        2, 1, figsize=(10, 7.6), sharex=True, gridspec_kw=dict(height_ratios=[2.1, 1])
    )
    fig.suptitle(
        s["t"], fontsize=17, fontweight="bold", color=INK, x=0.055, ha="left", y=0.975
    )
    fig.text(0.055, 0.932, s["sub"], fontsize=10.5, color="#52514e", ha="left")

    series = [
        ("bad", BAD, s["bad"], "--", 1.6, 0.85),
        ("d15", D15, s["d15"], "-", 2.4, 1.0),
        ("lc", LC, s["lc"], "-", 2.4, 1.0),
    ]

    for ax, col in ((a1, "dt"), (a2, "mhz_s")):
        ax.axvspan(10, 50, color="#000000", alpha=0.045, lw=0)
        for key, c, lab, ls, lw, al in series:
            d = frames[key]
            ax.plot(
                d["min"],
                d[col],
                color=c,
                ls=ls,
                lw=lw,
                alpha=al,
                label=lab if ax is a1 else None,
            )
        ax.grid(color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)

    a1.set_ylabel(s["y1"], fontsize=11)
    a2.set_ylabel(s["y2"], fontsize=11)
    a2.set_xlabel(s["x"], fontsize=11)
    a1.annotate(
        s["load"],
        xy=(30, 0.965),
        xycoords=("data", "axes fraction"),
        ha="center",
        va="top",
        fontsize=10,
        color="#52514e",
    )
    # ponytail: lewy górny róg jest pusty dla x<10, dolny kolidował z krzywą LC
    a1.annotate(
        s["note"],
        xy=(0.012, 0.96),
        xycoords="axes fraction",
        va="top",
        fontsize=10,
        color="#52514e",
        style="italic",
    )
    a1.legend(fontsize=10, frameon=False, loc="center right")
    fig.tight_layout(rect=[0, 0.01, 1, 0.915])

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"chlodzenie-D15-vs-LC-{lang}.png"
    fig.savefig(p, dpi=140, facecolor="white")
    plt.close(fig)
    return p


for lang in ("pl", "en"):
    print(" ->", draw(lang))

# ponytail: jedna bramka — werdykt musi zostać remisem, inaczej dane albo kod się rozjechały
row = {r["run"]: r for r in stats.to_dicts()}
delta = abs(row["lc"]["dT_load_K"] - row["d15"]["dT_load_K"])
assert delta < 2.0, f"ΔT load D15 vs LC rozjechane o {delta} K — sprawdź dane"
assert (
    row["bad"]["dT_load_K"] > row["d15"]["dT_load_K"] + 2
), "przebieg B przestał być odstający"
print(f"OK: |ΔT_LC - ΔT_D15| = {delta:.1f} K (remis), B odstaje zgodnie z oczekiwaniem")
