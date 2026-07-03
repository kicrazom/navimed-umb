# Release history

Per-release notes for NaviMed-UMB: scope, headline findings, and scaling
results for each tagged version. The current release summary lives in
[`README.md`](README.md); the universal benchmark protocol lives in
[`METHODOLOGY.md`](METHODOLOGY.md).

## 2026-05-26 — Run-3 consumer-GPU PLLuM AWQ (between-version event, under v0.4.0)

Run-3 closes the consumer-GPU surface of the PLLuM family. Two new public AWQ-4bit checkpoints quantized locally on a single Radeon AI PRO R9700 (gfx1201) and published on HuggingFace under `mozarcik/`:

- [`mozarcik/Llama-PLLuM-8B-chat-2512-awq`](https://huggingface.co/mozarcik/Llama-PLLuM-8B-chat-2512-awq) (Llama 3.1 base, full Llama 3.1 Community License compliance: `LICENSE`, `NOTICE` with exact Meta wording, `USE_POLICY.md`).
- [`mozarcik/PLLuM-12B-chat-2512-awq`](https://huggingface.co/mozarcik/PLLuM-12B-chat-2512-awq) (Mistral base, Apache 2.0 — no Llama overlay needed).

Both share the same `mozarcik/clinical-pl-smpc-awq-calibration` corpus as the Run-2 70B family (418 Polish SmPC fragments, EMA-sourced, No PHI), so cross-variant quantization-quality comparisons across 8B / 12B / 70B are corpus-controlled.

Gate 1 sanity 5/5 PASS for both variants via `/v1/completions` on the standard five Polish clinical prompts (factual + four clinical: tiotropium, astma, ostra duszność, spirometria). Raw outputs committed under `environment/sanity-tests/2026-05-26-*.json` (PUBLIC §11.1). Engineering envelope (PUBLIC §11.1): 8B at 5.53 GiB weights / 22.22 GiB KV cache / 88.89× max-concurrency on 1× R9700; 12B at 8.03 GiB weights / 19.77 GiB KV cache / 63.27× max-concurrency on 1× R9700. Phase 2 throughput sweep for Run-3 variants is scoped for v0.5.0 — when produced those numbers will be EMBARGOED §11.2 (§11.3 for Polish models).

The 4B-chat-2512 (multimodal Gemma3) variant is explicitly out of Run-3 scope — it requires `llm-compressor` main + cherry-pick of PR #2571 and is deferred to a separate mini-project.

Failure post-mortem (overnight `hf download` library run stalled on shards 3-5 — root cause `hf_transfer` accelerated mode silently truncating shards, misleading downstream "protobuf missing" error as the visible symptom — rescued by curl-per-shard against `cas-bridge.xethub.hf.co` direct path, IPv4-forced, ~60 min at ~31 Mbps; followed by ~25 min local quantization on R9700) and the snap-Obsidian `XDG_CACHE_HOME` leak workaround (`HF_HOME=$HOME/.cache/huggingface` override in `scripts/_env.sh`) are recorded in [`logbook/2026-05-26.md`](logbook/2026-05-26.md). METHODOLOGY §4.3 Run-3 addendum added in v1.2 (see METHODOLOGY changelog).

Ancillary infrastructure: `ai-workstation-dashboard/` bumped to v1.1.1 (added TX upload chart in cyan, stacked beneath the existing amber RX chart with independent auto-scale — closes the v1.1.0 README gap that promised both directions visible while only RX rendered).

## v0.4.0 — 2026-05-24

This release widens the project's scope from internal engineering log to a
public release pipeline plus an opened model-quality evaluation track. It
consolidates four working days of work (2026-05-21 through 2026-05-24)
that built on the v0.3.0 Phase 2 v0.3 sweep harness.

**Public release surface.** To the author's knowledge, this release ships
the **first public AWQ W4A16 vLLM-native quantization of the entire
Llama-PLLuM-70B family**: eight model cards under `mozarcik/`
(`base × {2412, 2508}` + `instruct × {2412, 2508, 2512}` + `chat × {2412,
2508, 2512}`), each with Llama 3.1 Community License compliance artifacts
(`NOTICE`, `LICENSE`, `USE_POLICY.md`), dual-platform vLLM usage snippets
(AMD ROCm validated; NVIDIA portable via `awq_marlin`), Gate 1 hardware
envelope + Gate 2 coherence-probe evidence, and an explicit "to the author's
knowledge" qualifier for the first-public claim. The reusable Polish
clinical SmPC calibration corpus is published separately as
[`mozarcik/clinical-pl-smpc-awq-calibration`](https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration)
(418 fragments, ~512 tokens each, 61 medicines from an 81-INN catalog, 9 NFZ drug programmes, No PHI).

**Phase 2 scaling sweep — 6/6 sanity-PASS Llama-PLLuM-70B AWQ variants.**
All six sanity-PASS variants (the three already covered overnight 2026-05-23
plus the three remaining `instruct-2412`, `chat-2412`, `chat-2508` covered
on 2026-05-24) were swept on the METHODOLOGY §6 standard N grid
`{10, 25, 50, 100, 200, 500, 1000}`. Engineering envelope is identical
across the family as expected for the shared Llama-3.1-70B architecture
(37.56 GB footprint at TP=2, ~55k KV cache at 8192 max_seq_len,
max_concurrency 6.7, junction peak 92-94 °C with ~16 °C headroom to the
gfx1201 throttle limit, ~290-320 W package power per GPU under load, no
thermal throttling observed). Per-N throughput, latency, scaling, and W/tok
numbers are EMBARGOED §11.2 (and stricter §11.3 for Polish models) and
remain in the gitignored `benchmarks/results/` tree pending paper
acceptance.

**METHODOLOGY §8 extension — Gate 2 human override.** The Gate 2 coherence
probe (`scripts/awq_coherence_probe.py`) uses an intentionally conservative
n-gram repetition heuristic that produces false positives on short correct
answers ("Stolicą Polski jest Warszawa." → `coherent=false` at
top_ngram_share 0.5 with word_count 4, despite being perfectly correct).
The `--stage sweep` orchestrator now honors a sibling
`<probe>.human_verdict.json` file: if present with `verdict: PASS`, it
overrides the auto verdict and is logged as a `[note]` line so both values
appear in the audit trail. Six such verdict files were committed for the
six sanity-PASS variants. This is consistent with the §8 boundary that
auto-flags are mechanical and human spot-check is part of the gate by
design.

**`eval-rag/` sub-project opened.** A new sub-project under
[`eval-rag/`](eval-rag/) opens a methodologically-distinct evaluation
question — *given that PLLuM-70B AWQ now fits on consumer 2× R9700, does
it actually answer Polish clinical-regulatory questions better than the
smaller PL-native Bielik or the larger multilingual Mistral / Qwen?* The
full design (five candidate LLMs, hybrid BM25 + multilingual-e5 retrieval
with RRF fusion, fifty Polish clinical questions in seven safety-weighted
categories, five-point manual review by three reviewers, conditional
single-card AQLM 2-bit sixth model gated on the five-model result) is
checked in along with outreach drafts to two proposed external co-authors
(identities withheld pending their consent). Generation pipeline
is BLOCKED on reviewer responses; no answers have been generated.

**Coordinated multi-paper publication roadmap.** This release adds a
four-paper publication plan (`#1` Quantization Trade-offs / MDPI
Electronics or IEEE Access · `#2` Broncho-Nome HL7 normalization / JBI or
JAMIA Open · `#3` Capno-Nome persistent homology / Respiratory Medicine or
Sensors · `#4a/4b` NaviMed L2 RAG architecture + L3 Arena methodology /
IEEE Access or JBI / JAMIA Open) plus a synthesis paper (`★` Three-Layer
Architecture for Sovereign Clinical Knowledge Management / Patterns or NPJ
Digital Medicine) targeted as the third pillar of the author's habilitation.
The papers are scaffolded by the QAIF AIntern 2026 submission round (Phase
1 deadline 2026-05-31).

**Documentation.** The repository README has been rewritten to reflect the
widened scope (benchmark suite + release pipeline + paper hub, rather than
the v0.3.0-era "engineering log of a workstation build"). The
`AI_USAGE_DISCLOSURE.md` tools table is extended with Gemini (web review)
and a locally-served Bielik-11B-v3.0-instruct-AWQ on a single R9700 used
for Polish-language proofreading. Plotting was patched — `plot_phase2_sweep.py`
now accepts both the post-2026-05 snake_case schema and the legacy
PascalCase one (backwards compatible with v0.1 / v0.2 sweeps).

**Embargo classification (PUBLIC §11.1, in this release).** Engineering
envelope, walltimes, thermal headroom, hardware configuration, methodology,
model cards, license/notice/policy attribution, and decision logs.

**Embargo classification (EMBARGOED §11.2 / §11.3, NOT in this release).**
Per-N throughput tok/s, request/s, total time, latency distributions, KV
cache occupancy curves, mean output length, W/tok, and any cross-model
comparative claim that uses concrete numbers. These remain in the
gitignored `benchmarks/results/` tree on the workstation, retained for the
forthcoming paper #1.

## 2026-05-23 — Llama-PLLuM-70B AWQ public release (between-version event, under v0.3.0)

To the author's knowledge, the **first public AWQ W4A16 (vLLM-native
`compressed-tensors`) quantization of the entire Llama-PLLuM-70B family**
was published on HuggingFace under `mozarcik/`. Eight variants live:
`base-{2412, 2508}` + `instruct-{2412, 2508, 2512}` + `chat-{2412, 2508,
2512}`. Calibration corpus
[`mozarcik/clinical-pl-smpc-awq-calibration`](https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration)
(418 fragments of Polish SmPC text, sourced from EMA, No PHI) is published
separately and reusable. Model cards ship as v1.1 with Llama 3.1 Community
License compliance (`NOTICE` + `LICENSE` + `USE_POLICY.md` in every repo),
dual-platform vLLM snippets (AMD ROCm validated; NVIDIA portable via
`awq_marlin`), Gate 1 hardware envelope + Gate 2 coherence-probe evidence
linked to this repository, and explicit "first AWQ to the author's
knowledge" qualifier (GGUF alternatives by mradermacher are acknowledged
for llama.cpp / ollama users).

This event is documented in
[`logbook/2026-05-23.md`](logbook/2026-05-23.md) and
[`docs/sessions/2026-05-23-pllum-awq-release-pipeline.md`](docs/sessions/2026-05-23-pllum-awq-release-pipeline.md).
The Gate 1 sanity JSON+log artifacts (eight variants, fresh re-run on
2026-05-23 in addition to the original 2026-05-22 batch) and the six Gate 2
coherence-probe JSON + raw-text artifacts are committed under
`environment/sanity-tests/` and `environment/coherence-probes/` respectively
(PUBLIC §11.1). No throughput numbers are published; Gate 3 (Phase 2
scaling sweep) remains EMBARGOED §11.2 / §11.3 pending paper acceptance.

Cross-channel surface: HuggingFace (8 model cards + dataset), GitHub
(this repository), Zenodo (DOI
[`10.5281/zenodo.20317011`](https://doi.org/10.5281/zenodo.20317011)
inherited from v0.3.0), LinkedIn (post `activity-7464059097575907328`).

## v0.3.0 — 2026-05-20

This release expands the benchmark scope toward the Phase 2 v0.3 campaign.
METHODOLOGY §4 grows from 11 to 21 models (Qwen 3.5/3.6, Bielik v3.0 family,
PLLuM, Mistral/Mixtral, Kimi); the PLLuM-70B rows are corrected to reflect
that BF16 weights exceed the 64 GB aggregate VRAM of 2× R9700, requiring
AWQ-4bit quantisation (Phase 3).

It adds the Phase 2 v0.3 sweep harness — TP=1 parallel (co-located
dual-instance) and isolated TP=1/TP=2 runners with thermal/power
instrumentation — and the Bielik v3.0 family environment envelope
(4.5B, 11B, PL-11B sanity-test PASS, TP=1 and TP=2). Tooling additions:
AI workstation dashboard v1.1.0, vLLM 0.19 compatibility fixes, and
repo hardening (pre-commit, detect-secrets, canonical licensing).

Raw Phase 2 scaling data remains under publication embargo per
[`METHODOLOGY.md`](METHODOLOGY.md) §11; methodology and environment
manifests are public.

## v0.2.0 — 2026-04-29

This release introduces the universal Phase 1 envelope + Phase 2 scaling sweep
methodology and applies it to Qwen 3.6 27B BF16 on 2× R9700. Engineering
findings (knee, scheduler robustness, energy/throughput trade-off) are public;
concrete throughput, latency, and power numbers are reserved for the
forthcoming preprint per the per-artifact policy in
[`METHODOLOGY.md`](METHODOLOGY.md) §11.

The 7B Plan A sweep from v0.1.0 has been retrofit to the same schema for
cross-model comparability.

**Statistical methodology note:** Phase 2 v0.2.0 reports n_runs=1 (single-shot
exploratory). Tier A reruns (n=10 with Holm-Bonferroni FWER correction) for
key configurations are scheduled for v0.2.1 per METHODOLOGY §7.4. Current
results characterize qualitative shape; statistical envelopes follow.

### Qwen 3.6 27B — concurrency scaling on 2× R9700

Phase 2 throughput sweep across N={10, 25, 50, 100, 200, 500, 1000} concurrent
prompts on the Phase 1 best BF16 configuration. Single-shot exploratory
measurements (n_runs=1); Tier A statistical reruns (n=10 with Holm-Bonferroni
FWER correction) scheduled for v0.2.1 per
[METHODOLOGY §7.4](METHODOLOGY.md).

[![Scaling curve](benchmarks/results/qwen36-27b/scaling_curve.png)](benchmarks/results/qwen36-27b/scaling_curve.png)

Three engineering findings (PUBLIC; concrete numbers reserved for forthcoming
preprint):

- **Throughput knee at ~8× the vLLM scheduler `max_concurrency` estimate.**
  Optimum batch size is substantially higher than the scheduler default for
  this model+config. Practitioners should sweep N empirically rather than
  trust scheduler heuristics.
- **vLLM scheduler graceful degradation.** At 5× over the throughput knee
  (40× over scheduler estimate), output throughput regresses by less than 1%
  versus peak. PagedAttention plus continuous batching are well-tuned for
  over-saturation; no starvation pathology observed.
- **Energy-optimal operating point ≠ throughput-optimal.** Lowest mWh per
  token occurs at a much lower concurrency than peak throughput. Operators
  should select N by priority — interactive (low N), throughput-max (peak N),
  energy-min (low N) — a trade-off invisible in marketing benchmarks
  reporting only peak aggregate tok/s.

See [`benchmarks/results/qwen36-27b/SUMMARY.md`](benchmarks/results/qwen36-27b/SUMMARY.md)
for the full per-N table, embargo classification, and methodological humility
statement. [`METHODOLOGY.md`](METHODOLOGY.md) v1.0 documents the universal
Phase 1/Phase 2 protocol applied across all 13 models in the suite.

## v0.1.0 — 2026-04-26

This release captures the engineering snapshot as of 2026-04-26: 13
benchmark models downloaded (~770 GB), validated working
configurations for Qwen 3.6 27B in both quantizations, and the full
software/hardware environment archived for reproducibility.

The release scope is strictly empirical: hardware/software envelope
measurements on this workstation. No claims are made in this release
about specific applications, downstream use cases, or future research
directions; those will be addressed in subsequent releases as the work
progresses.

For the canonical citation, see [`CITATION.cff`](CITATION.cff) or use
the **"Cite this repository"** button on GitHub.

A preprint extracting the empirical envelope findings into paper form
is in preparation: see [`paper/`](paper/).

### Software stack

Snapshot from 2026-04-26 (release v0.1.0):

| Component | Version |
|---|---|
| Python | 3.12.3 |
| vLLM | 0.19.0 (ROCm 7.2.1 wheel) |
| PyTorch | 2.10.0+git8514f05 |
| HIP | 7.2.53211 |
| flash-attn | 2.8.3 |
| triton | 3.6.0 |
| transformers | 4.57.6 |

Full pip freeze and system manifests are archived in
[`environment/`](environment/) for full reproducibility of all
benchmark runs in this release.

### Qwen 2.5 7B Instruct — concurrency scaling (April 2026)

Full concurrency sweep on vLLM 0.19 with both tensor-parallel
configurations, including per-run thermal instrumentation.

[![Scaling curve](benchmarks/results/qwen2.5-7b-fp16/scaling_curve.png)](benchmarks/results/qwen2.5-7b-fp16/scaling_curve.png)

Key findings (PUBLIC; concrete throughput numbers reserved for the forthcoming
preprint per [METHODOLOGY §11.2](METHODOLOGY.md)):

- TP=1 throughput saturates at high concurrency, with very low run-to-run variance.
- TP=2 pays a PCIe all-reduce penalty and plateaus below TP=1.
- TP=2 wins only at low concurrency; TP=1 leads at every higher batch size.
- Thermal asymmetry between GPU 0 and GPU 1 (airflow-dependent).

See
[`benchmarks/results/qwen2.5-7b-fp16/README.md`](benchmarks/results/qwen2.5-7b-fp16/README.md)
for the full writeup, all 14 measurement points, and methodology.

### Qwen 3.6 27B — practical envelope on 2× R9700

First documented working configuration of Qwen 3.6 27B (released
2026-04-22) on this hardware. Both FP8 and BF16 variants reach
inference; both require `tensor_parallel_size=2` and
`enforce_eager=True` due to a CUDA-graph capture incompatibility on
gfx1201.

**Working configurations for Qwen 3.6 27B on 2× R9700:**

| Quantization | TP | enforce_eager | max_len | Memory util | Weights/GPU | KV cache | Cold tok/s |
|---|---|---|---|---|---|---|---|
| BF16 | 2 | true | 1024 | 0.95 | 25.76 GiB | 2.68 GiB | **7.23** |
| FP8 | 2 | true | 2048 | 0.85 | 15.35 GiB | 7.53 GiB | 4.15 |

A counter-intuitive finding: under vLLM 0.19.0, **BF16 outpaces FP8 by
approximately 75%** on R9700 (cold first inference: 7.23 vs
4.15 tok/s). The cause is the absence of R9700-specific FP8 kernel
configurations in vLLM, forcing the runtime onto a generic block-FP8
fallback path.

Full debugging trail, working configs table, environment variable
corrections, and cross-reference to CUDA llama.cpp baselines:
[`docs/sessions/2026-04-26-qwen36-vllm-envelope.md`](docs/sessions/2026-04-26-qwen36-vllm-envelope.md).

Per-config Phase 1 envelope details (10 configurations, BF16 + FP8 + KV variants):
[`benchmarks/results/hardware_envelope/SUMMARY.md`](benchmarks/results/hardware_envelope/SUMMARY.md).

## Build timeline

- Hardware assembled and validated (2026-02-28 / 2026-03-04)
- ROCm 7.2.1 + PyTorch validation (2026-03-08)
- UPS monitoring operational (NUT + nutdrv_qx, 2026-03-30)
- AI workstation dashboard deployed (systemd autostart)
- vLLM 0.19 + ROCm 7.2.1 stack validated (2026-04-17)
- Qwen 2.5 7B Instruct: TP=1 vs TP=2 scaling sweep with thermal data (2026-04-22)
- Qwen 2.5 72B AWQ: pilot benchmark on TP=2 (2026-04-23)
- 13-model benchmark suite assembled (~770 GB, 2026-04-25)
- Qwen 3.6 27B envelope on R9700 / gfx1201 (2026-04-26, **v0.1.0**)
- Phase 2 scaling sweep — Qwen 3.6 27B BF16 (N=10..1000), exploratory (2026-04-29)
- METHODOLOGY.md v1.0 — universal Phase 1/Phase 2 protocol (2026-04-29, **v0.2.0**)
- Bielik v3.0 family envelope — 4.5B, 11B, PL-11B sanity PASS (2026-05-17/19)
- Phase 2 v0.3 sweep harness + 21-model suite (2026-05-20, **v0.3.0**)
