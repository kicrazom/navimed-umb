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
| idle Tctl (śr. ost. 5 min) [°C] | 55.6 | | |
| load Tctl (śr. ost. 10 min) [°C] | 80.6 | | |
| ΔT nad otoczeniem [K] | 56.1 | | |
| load Tctl max [°C] | 81.2 | | |
| zegar śr. pod obciążeniem [MHz] | 5042 | | |
| bogo-ops/s (stress-ng, real time) | 25 942 | | |
| fan/pompa śr. pod obciążeniem [RPM] | 1436 | | |
| Tctl po 10 min cooldownu [°C] | 54.8 | | |
| otoczenie [°C] | 24.5 | | |
| głośność (subiektywnie) | | | |

Uwaga metodyczna: pierwotna metryka „cooldown do <50 °C" nieosiągalna — idle Tctl tej platformy to ~55 °C (X3D + przeglądarki aktywne); zastąpiona przez „Tctl po 10 min cooldownu".

## Interpretacja

Przebieg A: NH-D15 G2 trzyma pełny boost bez throttlingu — 5042 MHz śr. przez 40 min przy Tctl 80.6 °C (zapas ~14 K do limitu 95 °C). Dla LC1-42 realny zysk wydajności możliwy tylko, jeśli niższa temperatura odblokuje wyższy boost PBO (porównać MHz + bogo-ops); w przeciwnym razie różnica będzie w temperaturach i kulturze pracy.

## Provenance

- Przebieg A (noctua, 2026-07-31): `noctua_20260731-2232.csv` + `stressng_noctua_20260731-2232.log` — bogo ops 62 261 310 / 2400 s
- Przebieg B (lc142): `lc142_YYYYMMDD-HHMM.csv` + log stress-ng
