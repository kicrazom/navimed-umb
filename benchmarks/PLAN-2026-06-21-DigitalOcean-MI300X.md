# RUN PLAN — DigitalOcean MI300X (datacenter-AMD tier)

**Status:** 📋 PLAN — prowizjonowanie przez **Playwright** (konsola DO), benchmark przez SSH. Wykonać gdy gotowi.
**Created:** 2026-06-21
**Cel:** domknąć spektrum AMD — *R9700 prosumer (pod-biurko)* → *MI300X datacenter* — paralela do NVIDIA 3090→H100 z PyStok #83. **NIE do papera #1** — to **ocena/charakteryzacja** + materiał na **talk AMD (PyStok jesień)**, z **uwidocznionym użyciem AMD Developer Program** (sekcja niżej).
**Embargo:** liczby = §11.2/§11.3; cloud-run = synthetic prompts (§6), **zero PHI**.

## Po co dokładnie (hipoteza do testu)
Na R9700 (gfx1201) **AWQ jest 4–10× wolniejszy od BF16** (§5.2 errata — brak AITER, słabe FP8 W8A8 kernele; single-stream 70B-AWQ = **[EMBARGOED §11.3]**). **MI300X (gfx942) MA AITER** → hipoteza: **AWQ na MI300X NIE ma tego slowdownu**. Jeśli się potwierdzi, to mocny wynik: ten sam stack (vLLM-ROCm) na innym AMD daje radykalnie inny obraz — i wyjaśnia, że slowdown to artefakt gfx1201, nie formatu. `[hipoteza — do zmierzenia]`

## AMD Developer Program — uwidocznienie (acknowledgment + provenance)
MI300X compute jedzie na **AMD Developer Program** (przez DigitalOcean) — tak jak wcześniej kwantyzacja 70B×8
(memory `navimed_quant_provenance`). To **ocena**, nie roszczenie do papera #1; ma być **widoczne i skredytowane**,
spójnie z dyscypliną disclosure:
- **Acknowledgment**: na stronie (stopka / „Compute & acknowledgments") + w nocie ewaluacyjnej —
  *„MI300X benchmarks run on AMD Developer Program compute (DigitalOcean)."*
- **Provenance**: kolumna `device=MI300X` + jawne źródło compute w raw/SUMMARY; NIE implikować „all local" (to cloud).
- Warstwa: **eval / disclosure**, NIE §Results głównego papera.

## Faza 1 — Prowizjonowanie (Playwright → cloud.digitalocean.com)
> Playwright robi TYLKO create/destroy/monitor dropletu w konsoli. Sam benchmark = SSH.
1. Login do DO (konto Łukasza — Playwright potrzebuje aktywnej sesji; zaloguj się ręcznie w oknie Playwrighta **albo** użyj live-browser CDP).
2. **Create GPU Droplet** → AMD **MI300X** (192 GB HBM3, gfx942). Region: `[verify — gdzie dostępne]`.
3. Image: ROCm-ready (DO AI/ML image) lub Ubuntu 24.04 + ROCm install. SSH key: dodać klucz Łukasza.
4. Create → odczytać IP dropletu.
> **Robustniejsza alternatywa (gdyby browser-flow padał):** `doctl` + API token (1 komenda `doctl compute droplet create`). GPU droplety bywają tylko w konsoli — stąd Playwright jako default. `[verify czy doctl wspiera MI300X]`

## Faza 2 — Setup (SSH na dropletcie)
- ROCm + **vLLM 0.19.0** (pin dla porównywalności z R9700; jeśli MI300X wymaga nowszego — **zanotować wersję**, to confounder).
- HF models: comparator subset → `~/models/` (login HF; `HF_HUB_ENABLE_HF_TRANSFER=1`).
- Harness: `git clone` navimed repo (lub scp `benchmarks/scripts/` + `scripts/`). Reuse **te same** runnery + wrappery.
- `pip`/env: numpy/matplotlib (ploty robimy lokalnie po pobraniu raw — na dropletcie tylko raw).

## Faza 3 — Run (te same configi co R9700 + to, czego R9700 nie uciągnie)
- **Ten sam protokół**: drabina `{1,10,25,50,100,200,500,1000}` + **N=1 anchor**, Tier A n=10, workload §6.
- Configi: **AWQ 70B** (head-to-head z R9700) + small/mid + **BF16 70B na TP=1** (MI300X 192 GB → mieści, R9700 nie — nowy punkt).
- TP=1 baseline (1× MI300X) + opcjonalnie TP=2/4/8 jeśli multi-GPU droplet (skalowanie jak MLC A100×2/4/8).
- Output do osobnego drzewa `results/_mi300x/<model>/…` + tag `device=MI300X` w schemacie §7.1 (kolumna `device_name`).

## Faza 4 — Capture + teardown (KOSZT!)
1. `scp` raw (`thermal-runs/`, `results_table.csv`, `SUMMARY.md`) → lokalnie do `benchmarks/results/_mi300x/`.
2. **Zniszcz droplet** (Playwright: Destroy w konsoli, lub `doctl compute droplet delete`) — MI300X jest drogi, nie zostawiać.
3. Ploty/tabele/agregacja **lokalnie** (po pobraniu).

## Koszt + czas `[verify pricing — nie zmyślam stawki]`
- MI300X droplet ≈ `$X/h` (sprawdź aktualny cennik DO / kredyty AMD Developer Program — Łukasz już z nich korzystał przy kwantyzacji).
- Sweep: pełny ~kilka h (jak na R9700, MI300X szybszy → krócej). **Trzymać krótko**, destroy zaraz po `scp`.

## Caveaty (jawnie w paperze/talku)
- **gfx942 (MI300X) ≠ gfx1201 (R9700)** — inna architektura; AITER obecny → to JEST zmienna, nie uśredniać z R9700, osobny tier.
- **vLLM/ROCm version parity** — pin 0.19 jeśli się da; różnica = confounder, zanotować.
- **Cloud ≠ deployment** — to charakteryzacja sprzętu, nie wdrożenie. **Produkcja kliniczna zostaje lokalnie na R9700** (suwerenność, PHI). Benchmark na cloud = OK (synthetic, zero PHI).
- Single-GPU MI300X (192 GB) vs dual-R9700 (64 GB) — inny VRAM budget; raportować per-device.

## Powiązania
- Komplementarne do `PLAN-2026-06-21-N1-anchor-run.md` (R9700) — razem dają tabelę cross-device.
- Tab.X cross-framework rośnie: NaviMed R9700 + NaviMed MI300X + MLC (NVIDIA/7900XTX).
- Materiał: talk AMD PyStok jesień + **nota ewaluacyjna** (NIE paper #1; osobna ocena z jawnym creditem AMD Developer Program).
