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
