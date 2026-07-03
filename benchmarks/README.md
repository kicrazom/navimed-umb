# Benchmarks

![The battle of the models in the AMD kingdom on vLLM-powered horses](assets/battle_of_LLM_models_gemini.png)

Performance characterization of vLLM 0.19 + ROCm 7.2.0 on 2× R9700
(gfx1201 / RDNA 4). The driving question: **when does TP=2 help, hurt, or
become mandatory** as model size and quantization vary?

## The TP=2 arc

| Regime | Representative model | TP=2 verdict |
|---|---|---|
| Harmful | Qwen 2.5 7B FP16 (15 GB) | TP=2 plateau ~24% below TP=1 — sync cost > parallelism gain |
| Envelope-defining | Qwen 3.6 27B FP8 / BF16 | FP8 OOMs on TP=1; both variants need TP=2 |
| Mandatory | Qwen 2.5 72B AWQ (39 GB) | Even quantized doesn't fit one 32 GB card |

Headline numbers and per-model analysis live in each study's `results/`
subdir and in [`../RELEASES.md`](../RELEASES.md).

## Sub-studies (Paper #1)

Two design-doc-led sub-studies extend the core concurrency sweep. Both
report structure and method publicly; the measured numbers are embargoed
per METHODOLOGY §11.2/§11.3.

- **Precision ablation — BF16 vs AWQ**
  ([`PLAN-2026-06-30-precision-ablation-bf16-vs-awq.md`](PLAN-2026-06-30-precision-ablation-bf16-vs-awq.md))
  — a same-checkpoint BF16 ↔ AWQ matrix spanning architecture × size
  (4.5–12B across Qwen, Llama, Mistral, Bielik) on RDNA 4, plus a W/token
  energy axis. De-confounds the AWQ-kernel finding from the Polish-only
  model pairs. Drivers: `scripts/orchestrators/run_ablation_bielik45_awq_sweep.sh`
  (single-cell full-ladder Tier-A sweep of the AWQ half) and
  `run_envelope_gate1_ablation.sh` (envelope probe + Gate-1 for the fresh
  AWQ quants); same-checkpoint PLLuM pairs run both halves back-to-back via
  `run_ablation_pllum8b_pair_sweep.sh` and `run_ablation_pllum12b_pair_sweep.sh`
  (each sweeps the BF16 cell then the AWQ cell of one checkpoint, keyed
  `pllum-8b` / `pllum-12b` alongside the existing `pllum-8b-awq` / `pllum-12b-awq`
  in `run_concurrent.py` + `bench_with_thermals.py`). Aggregation via
  `scripts/analysis/aggregate_power_efficiency.py` + `power_efficiency_plots.R`
  and `plot_family_split.py`.
- **N=1 single-stream anchor**
  ([`PLAN-2026-06-21-N1-anchor-run.md`](PLAN-2026-06-21-N1-anchor-run.md))
  — the single-request (sequential decode) latency-regime baseline at
  Tier A, kept in a separate results tree and reported apart from the
  {10..1000} concurrency ladder (METHODOLOGY §7.4). Drivers:
  `scripts/orchestrators/run_n1_anchor_smallmid.sh` (small/mid configs) and
  `run_n1_anchor_70b.sh` (Llama-PLLuM-70B AWQ family). Aggregation via
  `scripts/analysis/aggregate_n1_anchor.py` + `ladder_table_plots.R`
  (joined into one N {1..1000} ladder by `regen_ladder.sh`).

## Layout

```
assets/                    Cover image and static media
methodology/               Sweep design, gfx1201 env vars, hardware/iGPU separation
scripts/                   Benchmark harness (see below)
results/<model-config>/    One subdir per study, each with its own README
```

`scripts/` is organized by role: `low_level/` (GEMM ceiling),
`runners/` (vLLM entry points), `instrumentation/` (thermal wrappers +
sampler), `orchestrators/` (sweep drivers), `plotting/`, `analysis/`.

## Model suite

21 models across the Phase 2 v0.3 campaign (Qwen 2.5/3.5/3.6, Bielik v2.3
& v3.0 family, PLLuM, Mistral/Mixtral). Full table with repo IDs, sizes,
and quantizations: [`METHODOLOGY.md`](../METHODOLOGY.md) §4.

## Methodology and embargo

- Sweep design, gfx1201 env-var floor, negative results: [`methodology/`](methodology/README.md)
- Public vs. paper-embargoed result split: [`results/README.md`](results/README.md)
