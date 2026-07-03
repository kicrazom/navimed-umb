# RUN PLAN — N=1 single-stream anchor (n=10, 23 configs)

**Status:** ✅ READY TO FIRE — czeka na słoneczny dzień (compute na solar).
**Created:** 2026-06-21
**Protocol:** METHODOLOGY §5.2/§7.4 + `paper/2026-06-21-N1-singlestream-anchor.md`
**Embargo:** EMBARGO §11.2/§11.3 — `benchmarks/results/` gitignored.

## TL;DR — odpal jednym ruchem (no-sleep obowiązkowy)

```bash
systemd-inhibit --what=sleep:idle --who=navimed-n1 --why="N=1 anchor n=10" --mode=block \
  bash -c 'cd ~/Vaults-main/10_Projekty/0001-navimed-umb &&
    bash benchmarks/scripts/orchestrators/run_n1_anchor_smallmid.sh &&
    bash benchmarks/scripts/orchestrators/run_n1_anchor_70b.sh'
```
Uruchom w tle (background). Gotowe gdy oba sentinele istnieją:
`benchmarks/results/_n1_anchor_smallmid_logs/SWEEP_COMPLETE` +
`benchmarks/results/_n1_anchor_70b_logs/SWEEP_COMPLETE`.

## Pre-flight checklist
- [ ] **Słońce** ☀️ (cel: solar)
- [ ] Oba GPU idle (`pgrep -af 'vllm|bench_with_thermals|throughput_scaling'` puste)
- [ ] vLLM 0.19.0+rocm721 (wrappery same asertują)
- [ ] **no-sleep**: komenda już owija w `systemd-inhibit` (bez tego idle-suspend zabije run — memory `feedback_no_sleep_during_compute`)
- [ ] NIE edytować/commitować działających skryptów w trakcie (memory `feedback_no_edit_running_script`)

## Co liczy (230 runów = 23 configi × 10 reps)
- **small/mid** (`run_n1_anchor_smallmid.sh`, keyed runner `bench_with_thermals.py`): 15 configów —
  bielik-11b(fp16), bielik-11b-v30(bf16), bielik-11b-v30-instruct-awq(awq),
  bielik-4.5b-v30(bf16), bielik-pl-11b-v30-instruct(bf16), pllum-12b-awq, pllum-8b-awq — każdy ×{TP1,TP2};
  qwen3.5-9b(bf16) TP1. Output: `results/<key>/n1-anchor/`.
- **70B** (`run_n1_anchor_70b.sh`, path runner `throughput_scaling_phase2.py --ns "1"`): 8× Llama-PLLuM-70B
  {base,chat,instruct}×{2412,2508,2512}-awq (TP=2, compressed-tensors). Output: `results/<model>/scaling-n1/rep<NN>/`.
- Oba osobne od drabiny {10..1000} (§7.4: anchor reported separately, wykluczony z knee + Holm-Bonferroni).

## Estymata (z realnego smoke 2026-06-21)
| Leg | Runów | Czas |
|---|---|---|
| small/mid | 150 | ~3–3.5 h |
| 70B (decode-bound: single-stream [EMBARGOED §11.3]) | 80 | ~5 h |
| **TOTAL** | **230** | **~8–9 h (overnight/cały dzień)** |

Opcja skrócenia: w obu wrapperach zmień `COOLDOWN_S=30`/`INTER_REP_COOLDOWN_S=30` → `5`
(uzasadnione: N=1 ~zero thermal, smoke stabilny bez cooldownu) → **~7 h**.

## Smoke (zwalidowane 2026-06-21, oba runnery OK)
- Bielik-4.5B BF16 TP=1 N=1 → **[EMBARGOED §11.3]** (σ ≈ 0.2%, 2 reps), artefakty §7.1 OK.
- PLLuM-70B-base-2412 AWQ TP=2 N=1 → **[EMBARGOED §11.3]**, artefakty OK. (smoke posprzątany)

## Monitoring w trakcie
- Progress: `results/_n1_anchor_smallmid_logs/progress.log`, `_n1_anchor_70b_logs/progress.log` (ETA per run)
- Orchestrator log: `…_logs/orchestrator.log`

## PO runie (sentinel → regeneracja WSZYSTKIEGO z realnych liczb)
1. **Agregacja** N=1 anchor (median/p95/p99 z n=10) — osobno od drabiny.
2. **Generatory** (już przygotowane w impact-mapie do edycji): `plot_canonical.py`/`plot_scaling*` (anchor-marker lewy),
   `stats_holm_bonferroni.py` (wyklucz N=1), `finalize_phase2_generic.py` (osobny wiersz).
3. **Rendery + tabele**: F1 (punkt single-stream), `canonical_dataset.csv` (+23 wiersze `anchor`), per-model
   `scaling_curve/efficiency/SUMMARY`, **nowa Tab.X cross-framework** (NaviMed N=1 vs MLC `llm-perf-bench`).
4. **Site**: `results.html`, `conclusions.html`, `limitations.html`, `index.html`, `models.html`, `methodology.html`, `reproduce.html`.
5. **Paper**: `results-section-draft.md` §3.x + `v0.1-hardware-envelope.md`.
6. Embargo §11.3 respektowany; commit dopiero po akceptacji per artefakt.

## Finding preview (czemu to się opłaca)
70B-AWQ single-stream na R9700 = **[EMBARGOED §11.3]** (gfx1201 AWQ kernel slowdown, §5.2 errata) — w benchmarku
„jedna liczba" wygląda fatalnie (MLC Llama2-70B 7900XTX = 29.9). Ale agregat pod współbieżnością = **[EMBARGOED §11.3]**.
Anchor N=1 + drabina = twardy dowód **„envelope > single-number"**: single-stream ukrywa, że R9700 jest viable
do multi-user CDSS. To jest punkt, który domyka paper i daje materiał na talk AMD (PyStok jesień).

## Pliki tej zmiany (do commita — propose-first, workflow navimed)
- `METHODOLOGY.md` §5.2 + §7.4 (N=1 anchor protocol)
- `paper/2026-06-21-N1-singlestream-anchor.md` (spec)
- `benchmarks/scripts/orchestrators/run_n1_anchor_smallmid.sh`, `run_n1_anchor_70b.sh`
- `benchmarks/PLAN-2026-06-21-N1-anchor-run.md` (ten plik)
