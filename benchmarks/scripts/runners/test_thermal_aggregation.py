#!/usr/bin/env python3
"""Test agregacji termicznej runnera — najmniejszy, ktory lapie regresje P1/P6/P7.

Nie dotyka GPU, nie importuje vLLM (`run_child` robi to dopiero w ciele funkcji)
i nie czyta zadnego przebiegu kampanii. Buduje syntetyczna pare
`*-thermals.jsonl` / `*-events.json` w katalogu tymczasowym i sprawdza cztery
reguly, kazda wprowadzona 2026-10-08:

  P1/D3  moc = suma kart w probce, potem srednia po probkach (nie usrednienie
         po kartach, ktore przy TP=2 zanizalo sumaryczny pobor dwukrotnie);
  P1/D3  okno mocy = okno GENERACJI, gdy `gen start`/`gen end` sa zapisane;
         okno przebiegu to tylko awaryjny powrot dla starych sladow;
  P6     VRAM w GiB (2^30), pod nazwa `vram_peak_gib`;
  P7     `W_peak` = maksimum SUMY kart, nie maksimum pojedynczej karty.

Uzycie:
    python benchmarks/scripts/runners/test_thermal_aggregation.py
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "throughput_sweep_v0_3", HERE / "throughput_sweep_v0.3.py"
)
sweep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sweep)

# 30 828 343 296 B — ta sama liczba, ktora stoi w finding 12 audytu.
VRAM_B = 30_828_343_296
VRAM_GIB = 28.711
VRAM_GB = 30.828


def _sample(t: float, p0: float, p1: float, temp: float, vram_b: int) -> str:
    """Jedna probka samplera: dwie karty dyskretne + iGPU bez pomiaru mocy."""
    return json.dumps(
        {
            "t": t,
            "gpus": [
                {"idx": 0, "power_w": p0, "temp": temp, "vram_used_b": vram_b},
                {"idx": 1, "power_w": p1, "temp": temp - 2, "vram_used_b": vram_b},
                {
                    "idx": 2,
                    "power_w": None,
                    "temp": 99.0,
                    "is_igpu": True,
                    "vram_used_b": 10**12,
                },
            ],
        }
    )


def _fixture(tmp: Path, with_gen: bool) -> Path:
    """Slad: probki 0..6 s. Generacja trwa 4..6 s, reszta to ladowanie i warmup."""
    jsonl = tmp / "q-tp2-n10-thermals.jsonl"
    lines = [
        _sample(-1.0, 900.0, 900.0, 80.0, VRAM_B),  # przed oknem przebiegu
        _sample(0.0, 15.0, 15.0, 44.0, 60_000_000),  # idle przed startem procesu
        _sample(1.0, 120.0, 100.0, 50.0, VRAM_B),  # ladowanie wag
        _sample(2.0, 130.0, 110.0, 52.0, VRAM_B),
        _sample(3.0, 200.0, 180.0, 58.0, VRAM_B),  # warmup
        _sample(4.0, 300.0, 280.0, 66.0, VRAM_B),  # generacja
        _sample(5.0, 340.0, 300.0, 69.0, VRAM_B),
        _sample(6.0, 310.0, 290.0, 68.0, VRAM_B),
        _sample(99.0, 900.0, 900.0, 90.0, VRAM_B),  # po oknie przebiegu
    ]
    jsonl.write_text("\n".join(lines))
    events = [
        {"t": 0.0, "label": "bench start (q TP=2 N=10)"},
        {"t": 6.5, "label": "bench end"},
    ]
    if with_gen:
        events += [
            {"t": 4.0, "label": "gen start"},
            {"t": 6.0, "label": "gen end"},
        ]
    (tmp / "q-tp2-n10-events.json").write_text(json.dumps(events))
    return jsonl


def test_generation_window_and_card_sum():
    with tempfile.TemporaryDirectory() as td:
        jsonl = _fixture(Path(td), with_gen=True)
        got = sweep.aggregate_thermals(jsonl, 0.0, 6.5, 4.0, 6.0)

    # Sumy kart w oknie generacji: 580, 640, 600 -> srednia 606.666..., szczyt 640.
    assert got["power_mean_w"] == 606.7, got
    assert got["power_peak_w"] == 640.0, got
    # Maksimum POJEDYNCZEJ karty to 340 W. Gdyby `W_peak` liczyl sie po kartach,
    # stalby tu 340 i dwie kolumny obok siebie opisywalyby rozne obiekty (P7).
    assert got["power_peak_w"] != 340.0
    # Usrednienie po kartach dalo by dokladnie polowe — defekt z findingu 4.
    assert abs(got["power_mean_w"] - 2 * 303.3) < 0.2


def test_bench_window_fallback_is_lower():
    """Bez znacznikow generacji moc rozciera sie na ladowanie i warmup."""
    with tempfile.TemporaryDirectory() as td:
        jsonl = _fixture(Path(td), with_gen=False)
        bench = sweep.aggregate_thermals(jsonl, 0.0, 6.5)
        gen = sweep.aggregate_thermals(jsonl, 0.0, 6.5, 4.0, 6.0)
    # Sumy w calym oknie: 30, 220, 240, 380, 580, 640, 600 -> srednia 384.3.
    assert bench["power_mean_w"] == 384.3, bench
    assert bench["power_mean_w"] < gen["power_mean_w"], (bench, gen)
    # Oba okna widza ten sam szczyt, bo szczyt wypada w generacji.
    assert bench["power_peak_w"] == gen["power_peak_w"] == 640.0


def test_vram_is_gibibytes_and_named_so():
    with tempfile.TemporaryDirectory() as td:
        jsonl = _fixture(Path(td), with_gen=True)
        got = sweep.aggregate_thermals(jsonl, 0.0, 6.5, 4.0, 6.0)
    assert "vram_peak_gib" in got, got.keys()
    assert "vram_peak_gb" not in got, "stara nazwa klamala o jednostke (P6)"
    assert abs(got["vram_peak_gib"] - VRAM_GIB) < 0.001, got["vram_peak_gib"]
    assert abs(got["vram_peak_gib"] - VRAM_GB) > 2.0, "to nie moga byc GB dziesietne"
    # iGPU ma 10^12 B i musi byc odfiltrowane, inaczej szczyt poszedlby w setki GiB.
    assert got["vram_peak_gib"] < 100.0


def test_peaks_use_run_window_not_generation_window():
    """VRAM i temperatura opisuja caly przebieg, moc tylko generacje (D3)."""
    with tempfile.TemporaryDirectory() as td:
        jsonl = _fixture(Path(td), with_gen=True)
        got = sweep.aggregate_thermals(jsonl, 0.0, 6.5, 4.0, 6.0)
    # 69 C wypada w generacji, ale 90 C z t=99 jest poza oknem przebiegu.
    assert got["temp_peak_c"] == 69.0, got


def test_schema_has_mandatory_columns():
    """§7.1 wymaga `vs_baseline_%`; audyt (finding 20) stwierdzil jego brak."""
    assert "vs_baseline_%" in sweep.CSV_COLS
    assert "vram_peak_gib" in sweep.CSV_COLS
    assert "vram_peak_gb" not in sweep.CSV_COLS
    assert "power_window" in sweep.CSV_COLS, "okno mocy to czesc proweniencji"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK  {name}")
    print("wszystkie testy agregacji termicznej przeszly")
