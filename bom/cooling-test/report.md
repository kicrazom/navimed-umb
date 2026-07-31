# Cooling A/B: Noctua NH-D15 G2 → LC1-42

CPU: AMD Ryzen 9 9950X3D (16C/32T, Tctl limit 95 °C — throttling objawia się spadkiem MHz, nie wzrostem temperatury).
Procedura: `cooling_ab_test.sh` — 10 min idle → 40 min stress-ng `matrixprod` (32 wątki) → 10 min cooldown, próbkowanie sensorów co 5 s (k10temp + asusec). Walltime ~61 min / przebieg.

## Warunki kontrolowane (identyczne w obu przebiegach)

- BIOS / PBO / krzywa wentylatorów: bez zmian między przebiegami (BIOS 2202)
- GPU bezczynne (vLLM zatrzymany, `rocm-smi` PPT < 15 W)
- Temperatura otoczenia zmierzona termometrem i podana do skryptu (metryka porównawcza = ΔT nad otoczeniem)
- Maszyna nieużywana w trakcie testu, `systemd-inhibit` aktywny

## Wyniki

| Metryka | NH-D15 G2 | LC1-42 | Δ |
|---|---|---|---|
| idle Tctl (śr. ost. 5 min) [°C] | | | |
| load Tctl (śr. ost. 10 min) [°C] | | | |
| ΔT nad otoczeniem [K] | | | |
| load Tctl max [°C] | | | |
| zegar śr. pod obciążeniem [MHz] | | | |
| bogo-ops/s (stress-ng) | | | |
| fan/pompa śr. [RPM] | | | |
| cooldown do <50 °C [s] | | | |
| otoczenie [°C] | | | |
| głośność (subiektywnie) | | | |

## Interpretacja

_(po obu przebiegach: różnica zegarów + bogo-ops = realny zysk wydajności; ΔT = zapas termiczny; wpisać werdykt)_

## Provenance

- Przebieg A (noctua): `noctua_YYYYMMDD-HHMM.csv` + log stress-ng
- Przebieg B (lc142): `lc142_YYYYMMDD-HHMM.csv` + log stress-ng
