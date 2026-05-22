# Llama-PLLuM-70B family — AWQ W4A16 quantization on AMD MI300X

**Date:** 2026-05-21 / 2026-05-22
**Operator:** Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>
**Methodology:** METHODOLOGY.md v1.1 §4.3 (PLLuM-70B errata), §11 (embargo)
**Embargo:** PUBLIC — quantization (sizes, wall times) and publication are
public; downstream Phase 2 throughput sweeps remain EMBARGO_paper_bound (§11).

## Summary

All five Llama-PLLuM-70B checkpoints in the benchmark suite (and three
additional checkpoint variants) were quantized from BF16 to AWQ W4A16 on a
single AMD Instinct MI300X, awarded through the AMD Developer Cloud program.
Eight checkpoints total — base, instruct, and chat post-training variants
across three release versions (2412 / 2508 / 2512) — converted at roughly
40 min/model, ~132 GB BF16 → ~37 GB AWQ each. All eight are published as
public Hugging Face repositories. The navimed-umb repository received the
clinical-PL SmPC calibration corpus and an 8-model AWQ sanity+sweep runner.

This session unblocks the PLLuM-70B family for local deployment: in BF16
these models exceed the 64 GB aggregate VRAM of the 2× R9700 workstation
pair (METHODOLOGY §4.3 errata, 2026-05-21) and were not deployable locally.
The AWQ checkpoints (~37 GB) fit and are serveable.

## Rationale

The 2026-05-20 batch sanity sweep confirmed a hard physical limit: all five
PLLuM-70B BF16 checkpoints OOM on the 2× R9700 pair even at TP=2 — ~132 GB
of BF16 weights against 64 GB of aggregate VRAM. METHODOLOGY §4.3 rows
#14-18 were corrected the same day (commit `b76dd8a`, "PLLuM-70B status —
BF16 OOM, AWQ required"); AWQ W4A16 (~37 GB) is the smallest deployable
form that fits.

Local AWQ quantization of a 70B model is technically feasible on the R9700
pair — AutoAWQ proceeds layer-wise / sequentially or with CPU offload — but
the decision to route these quantizations to external compute is a
**resource-allocation choice** (METHODOLOGY §4.3 errata): it uses awarded
external GPU credit and keeps the local pair free for sweep work. The
operating rule going forward: models whose deployable form exceeds 64 GB
VRAM are routed to AMD compute for quantization; the quantized checkpoints
then re-enter the suite for local Phase 1/Phase 2.

## Platform

| Component | Configuration |
|---|---|
| Provider | AMD Developer Cloud (promotional GPU credit, ~30-day validity) |
| Accelerator | 1× AMD Instinct MI300X, 192 GB HBM3 |
| Instance | Single-GPU AMD Developer Cloud instance |
| Quantization tool | llm-compressor 0.10.0.2 (compressed-tensors, pack-quantized W4A16) |

The 192 GB HBM3 of a single MI300X holds the full 70B BF16 model (~132 GB)
in device memory during quantization, so the conversion runs without the
layer-wise / CPU-offload contortions that local quantization on the R9700
pair would require — the headroom is what makes ~40 min/model possible.

### Tooling pivot — autoawq → llm-compressor

The initial plan (METHODOLOGY recovery Faza 3) named AutoAWQ. AutoAWQ is
incompatible with transformers 4.57 — and transformers 5.8.1 is the v0.3+
stack. The campaign pivoted to **llm-compressor 0.10.0.2**, which produces
the `compressed-tensors` pack-quantized W4A16 format. This is the AWQ
algorithm (activation-aware weight quantization, 4-bit weights with
per-group scales) delivered through a maintained, transformers-5-compatible
toolchain.

## Calibration corpus — clinical-PL SmPC

AWQ is activation-aware: it needs a calibration corpus to estimate which
weight channels carry the most activation energy and scale them to
minimize quantization error. For a Polish-language clinical LLM, a generic
English calibration sample (pileval / C4) would mis-estimate the
activation profile. A domain- and language-matched corpus was built
instead.

| Property | Value |
|---|---|
| Source | EMA-published ChPL / SmPC documents (Summary of Product Characteristics) — public regulatory documents |
| Scope | 418 chunks, 61 Polish medicines |
| Provenance | 10-field per-chunk schema (`source_authority`, `medicine`, `brand_name`, `source_url`, `chunk_id`, …) |
| Published as | HF dataset `mozarcik/clinical-pl-smpc-awq-calibration` + repo `calibration/` |
| License | Source-specific — EMA reproduction terms with attribution, **NOT** the root CC-BY-4.0 / MIT |

No patient data (PHI) is involved at any point — the corpus is built
entirely from public, EMA-published product characteristics. The raw ChPL
PDFs are third-party copyrighted and stay local-only (`.gitignore`); the
extracted text corpus, the drug catalog (PL/EN), and the reproducible
`extract_corpus.py` are committed under `calibration/` with a separate
`calibration/LICENSE`. The repo `README.md` flags `calibration/` as
separately governed (commit `f6ab293`).

## Quantization run

Eight checkpoints were quantized — base, instruct, and chat post-training
variants across three release versions:

| # | Checkpoint | Version |
|---|---|---|
| 1 | `Llama-PLLuM-70B-base-2412` | Dec 2024 |
| 2 | `Llama-PLLuM-70B-instruct-2412` | Dec 2024 |
| 3 | `Llama-PLLuM-70B-chat-2412` | Dec 2024 |
| 4 | `Llama-PLLuM-70B-base-2508` | Aug 2025 |
| 5 | `Llama-PLLuM-70B-instruct-2508` | Aug 2025 |
| 6 | `Llama-PLLuM-70B-chat-2508` | Aug 2025 |
| 7 | `Llama-PLLuM-70B-instruct-2512` | Dec 2025 |
| 8 | `Llama-PLLuM-70B-chat-2512` | Dec 2025 |

(base ×2, instruct ×3, chat ×3.) Each conversion: ~132 GB BF16 → ~37 GB
AWQ, roughly 40 min/model on the MI300X. The run was split into two batches
(5 + 3 checkpoints) within the ~30-day credit window.

### Known artefact — v_proj skipped on GQA layers

On these models — the Llama-3.1-70B architecture, which uses grouped-query
attention (GQA, fewer key/value heads than query heads) — llm-compressor
**skips AWQ scaling for `v_proj`**. The `v_proj` weights are still quantized
to 4-bit; they are simply not activation-scaled. This is documented
library behaviour for GQA layouts, not a defect in this run. It is recorded
here so that anyone reading the quantized checkpoints' config does not
mistake the missing `v_proj` scales for a corrupted conversion. Whether it
has any measurable effect on output quality is a question for the
downstream sanity + sweep, not for this quantization session.

## Publication

All eight AWQ checkpoints are published as public Hugging Face
repositories under the canonical naming scheme:

```
mozarcik/Llama-PLLuM-70B-{base,instruct,chat}-{2412,2508,2512}-awq
```

Concretely: `base-2412`, `instruct-2412`, `chat-2412`, `base-2508`,
`instruct-2508`, `chat-2508`, `instruct-2512`, `chat-2512` (8 repos).

## Artefacts delivered to navimed-umb

| Artefact | Description |
|---|---|
| `calibration/clinical-pl/corpus.jsonl` | 418-chunk calibration corpus, 10-field provenance |
| `calibration/clinical-pl/extract_corpus.py` | reproducible extraction script |
| `calibration/clinical-pl/drug-catalog-{PL,EN}.md` | drug catalog (61 medicines) |
| `calibration/{LICENSE,README.md}` | source-specific licensing (EMA reproduction terms) |
| `scripts/sanity_sweep_pllum70b_awq.sh` | 8-model AWQ sanity + Phase 2 sweep runner |

The runner (commit `d42ef20`): vLLM serve TP=2, AITER off, enforce-eager,
3-state response classification (ok / degenerate / parse_fail) for the 8
checkpoints, then a Phase 2 scaling sweep for sanity-PASS models only. It
reuses `_env.sh`, `kill_port.sh`, and `throughput_scaling_phase2.py`. A
readiness guard checks `config.json` + `*.safetensors` so partial
downloads are rejected. Embargo split per METHODOLOGY §11 — sanity JSON
public, sweep throughput numbers gitignored. Produced by the code agent
team (writer + verifier).

## Embargo classification (METHODOLOGY §11)

- **PUBLIC:**
  - Quantization run — checkpoint list, BF16/AWQ sizes, per-model wall time
  - The tooling pivot (autoawq → llm-compressor) and the v_proj artefact
  - The calibration corpus and its provenance/licensing
  - HF publication of the 8 AWQ checkpoints
  - The sanity+sweep runner script
- **EMBARGO_paper_bound (Polish models, §11.3):**
  - All downstream Phase 2 throughput / knee / plateau numbers for the
    AWQ checkpoints once the local sweep runs

## Next steps

1. Run the 8-model AWQ sanity sweep on the local 2× R9700 pair
   (`sanity_sweep_pllum70b_awq.sh`) — confirm each checkpoint serves
   (load, VRAM, KV envelope) under METHODOLOGY §3.3 causal closure.
2. Phase 2 throughput sweep for sanity-PASS checkpoints (N ladder,
   thermal instrumentation) — results EMBARGOED per §11.3.
3. METHODOLOGY §4.3 — add the published AWQ checkpoints as deployable
   suite entries once local sanity confirms.

## AI usage disclosure (METHODOLOGY §9)

- **Layer 1 (data):** calibration corpus extracted from public EMA-published
  ChPL/SmPC documents via the deterministic `extract_corpus.py`; no AI
  generation of corpus content.
- **Layer 2 (pipeline):** the `sanity_sweep_pllum70b_awq.sh` runner drafted
  by the code agent team (writer + verifier); quantization performed by
  llm-compressor 0.10.0.2 (not an LLM agent).
- **Layer 3 (manuscript):** TBD per paper submission.
