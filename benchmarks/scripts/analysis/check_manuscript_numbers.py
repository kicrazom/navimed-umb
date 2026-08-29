#!/usr/bin/env python3
"""Sprawdza, czy kazda liczba w manuskrypcie ma pokrycie w kanonicznych CSV-ach.

Nie sprawdza arytmetyki — audyt liczbowy dal 74/74 PASS i arytmetyka byla poprawna
od poczatku. Sprawdza klase defektu, ktora faktycznie przezyla piec rund recenzji:
**tekst odjechal od artefaktow przeliczonych pozniej** (4.765 -> 4.782 po przeliczeniu
tabeli 16.07, podpisy figur mowiace min-max gdy figury rysuja bootstrap CI).

Liczba "osierocona" = wystepuje w tekscie, nie wystepuje w zadnym CSV przy zadnym
zaokragleniu. To kandydat na wartosc nieaktualna. NIE kazda osierocona liczba jest
bledem — daty, wersje, numery sekcji i wielkosci wyliczone recznie tez tu wpadna.
Narzedzie zaweza pole, nie wydaje werdyktu.

Uzycie:
    python3 check_manuscript_numbers.py <manuskrypt.md>
    python3 check_manuscript_numbers.py --demo     # self-check
"""

import csv
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
RESULTS = ROOT / "benchmarks" / "results"
NUM = re.compile(r"\d+\.\d+")


def csv_number_forms(results_dir):
    """Wszystkie liczby z CSV-ow, w kazdym zaokragleniu 1..4 miejsc po przecinku."""
    forms = set()
    for path in results_dir.rglob("*.csv"):
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                for row in csv.reader(fh):
                    for cell in row:
                        try:
                            v = float(cell)
                        except (ValueError, TypeError):
                            continue
                        for d in range(1, 7):  # do 6 miejsc — p_holm ma 6 (0.007629)
                            forms.add(f"{v:.{d}f}".rstrip("0").rstrip("."))
                            forms.add(f"{v:.{d}f}")
        except OSError:
            continue
    return forms


def check(manuscript, results_dir=RESULTS):
    text = pathlib.Path(manuscript).read_text(encoding="utf-8")
    forms = csv_number_forms(results_dir)
    found = NUM.findall(text)
    orphans = sorted(
        {n for n in found if n not in forms and n.rstrip("0").rstrip(".") not in forms}
    )
    return found, orphans, forms


def demo():
    """Self-check na znanym defekcie: 4.782 jest w tabeli, 4.765 nie."""
    forms = csv_number_forms(RESULTS)
    assert "4.782" in forms, "4.782 powinno byc w tabeli ablacji (PLLuM-12B TP1 N=200)"
    assert (
        "4.765" not in forms
    ), "4.765 to wartosc nieaktualna — nie powinno byc w zadnym CSV"
    print("demo OK — 4.782 ma pokrycie, 4.765 jest osierocone (zgodnie z oczekiwaniem)")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
    elif len(sys.argv) > 1:
        found, orphans, forms = check(sys.argv[1])
        print(f"liczb w tekscie: {len(found)} ({len(set(found))} unikalnych)")
        print(f"form liczbowych w CSV: {len(forms)}")
        print(f"osieroconych (brak pokrycia w zadnym CSV): {len(orphans)}\n")
        for o in orphans:
            print(" ", o)
    else:
        print(__doc__)
