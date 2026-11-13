---
type: intent
status: draft
stage: plan
project: "[[10_Projekty/0001-navimed-umb/NaviMed_UMB_index|navimed-umb]]"
slug: lechat-agentic-benchmark
created: 2026-11-13
nastepny_artefakt: spec.md
baseline: "site/lechat.html § Measured (2026-11-13, N=3, bez mocy, bez zadań)"
tags: [intent, sdlc]
---

# intent — leChatonFat4Navi jako benchmark aplikacyjny: energia na zadanie i skuteczność agenta

## Problem

NaviMed mierzy **kopertę sprzętu** (przepustowość, latencja, moc, temperatury) pod obciążeniem
syntetycznym. Nie mierzy, czy na 2× R9700 da się realnie pracować z agentem — a to pierwsze pytanie
recenzenta i czytelnika.

[leChatonFat4Navi](https://github.com/kicrazom/leChatonFat4Navi) daje obciążenie aplikacyjne
(Opencode + llama.cpp + MCP), ale dziś jedyne liczby to prędkość z 13.11:

| backend | prompt | generowanie | moc | zadania |
|---|---|---|---|---|
| ROCm 7.2.1 | ~2 650 tok/s | 76,9 tok/s | **niezmierzona** | **niezmierzone** |
| Vulkan | ~1 720 tok/s | 88,4 tok/s | **niezmierzona** | **niezmierzone** |

Źródło: `site/lechat.html` § Measured. Qwen3.6-35B-A3B-UD-Q4_K_XL, prompt 600 tok, 256 tok
generacji, N=3, bez gatingu termicznego, na GPU0 równolegle dwa serwisy vLLM 0050.

**Liczby wyjściowej dla energii i skuteczności nie ma.** Zgodnie z regułą tego vaultu pierwszym
krokiem jest jej zmierzenie, nie optymalizacja czegokolwiek.

## Oczekiwany rezultat

Harness, który dla stałego zestawu zadań produkuje, per `(backend, model, zadanie, powtórzenie)`:
rozwiązane tak/nie, liczbę wywołań narzędzi (poprawnych / niepoprawnych składniowo), tokeny wejścia
i wyjścia, czas ścienny, TTFT pierwszego kroku oraz **energię na zadanie [J]** liczoną po
regułach METHODOLOGY (moc = suma kart dyskretnych z próbnika 1 Hz, iGPU wykluczone; okno = czas
generacji, nie cały przebieg).

**Kryterium sukcesu (jedno):** pełna siatka **K ≥ 20 zadań × N = 3 powtórzenia × 2 backendy
(ROCm, Vulkan)** zakończona, z oknami mocy pokrywającymi **≥ 95 %** czasu generacji każdego zadania,
i z tabelą `success_rate`, `J/zadanie`, `tok/zadanie` per backend. Same liczby mogą wyjść dowolne —
sukcesem jest to, że istnieją i są powtarzalne.

**Porażka:** okna mocy nie da się przypisać do zadania (agent woła serwer wieloma żądaniami,
przeplatanymi narzędziami na CPU), więc J/zadanie jest nieokreślone; albo wynik zadania wymaga
ręcznej oceny, więc `success_rate` nie jest odtwarzalny.

## Kogo i co dotyczy

- **Dotyczy:** fork `~/code/leChatonFat4Navi` (instrumentacja: znaczniki start/koniec zadania,
  eksport `/metrics` llama.cpp), próbnik mocy NaviMed (`benchmarks/scripts/`), nowy katalog
  wyników w `benchmarks/results/` z osobnym prefiksem, strona `site/lechat.html`.
- **Zestaw zadań — kandydaci:** podzbiór Terminal-Bench lub DeepSWE (używa ich Unsloth dla
  Qwen3.8, więc jest punkt odniesienia), plus zadania własne z automatyczną weryfikacją
  (np. „napraw failujący test” w repo z CI — Capno-Nome). Weryfikacja wyłącznie testem, nie oceną LLM.
- **NIE dotyczy:** głównej koperty i sweepu skalowania (embargo) — to osobny wątek, nie wolno mieszać
  wyników. Nie dotyczy publikacji #1. Nie dotyczy modeli AWQ/vLLM (backend vLLM w leChat = osobny intent).

## Ograniczenia i pytania otwarte

- **Twarde:** wszystko lokalnie (zero zewnętrznych API, SearXNG zamiast wyszukiwarki zewnętrznej);
  API modelu tylko na `127.0.0.1`; na czas pomiaru zatrzymać vLLM 0050 (dziś współdzieli GPU0);
  `systemd-inhibit` na czas przebiegu; nic z danymi pacjentów w zadaniach.
- **Pytania do spec.md:**
  1. Jak wyznaczyć okno generacji dla zadania wieloetapowego — suma okien żądań z logów llama.cpp
     czy znaczniki z harnessu?
  2. Temperatura próbkowania: 0 (powtarzalność) czy domyślne 0,6 z leChat (realizm)? Wpływa na N.
  3. Ile tokenów kontekstu na zadanie — czy 98K z KV `q4_0` nie fałszuje jakości względem f16?
  4. Gating termiczny jak w METHODOLOGY (cooldown między przebiegami) — tak, ale ile trwa.
- **Pytanie otwarte, celowo poza zakresem:** *czy to środowisko jest tańsze od odpowiednika na RTX.*
  Wymaga pomiaru na NVIDII w tej samej konfiguracji (dane autora leChat z RTX 2070S + 1080 Ti
  nie są porównywalne — model się nie mieści) i **bieżących** cen kart, nie z pamięci
  (szortaż DRAM 2026). Metryka do porównania: zł / (tok/s) i J/zadanie. Osobny intent.
