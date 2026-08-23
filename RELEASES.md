# Release history

Per-release notes for NaviMed-UMB: scope, headline findings, and scaling
results for each tagged version. The current release summary lives in
[`README.md`](README.md); the universal benchmark protocol lives in
[`METHODOLOGY.md`](METHODOLOGY.md).

## v0.5.1 — 2026-08-23

Documentation-and-platform erratum release. No new benchmark results are published;
the §11.2/§11.3 embargo is unchanged.

**PCIe topology erratum** ([`bom/pci-topology.md`](bom/pci-topology.md)). The v0.5.0
record described both R9700 cards at "full x16 bandwidth each", and the v0.5.0 notes
attributed the restoration of a symmetric link to the BIOS 2202 flash. Both were wrong.
The x16 reading came from the GPU endpoints (`03:00.0`, `07:00.0`), which report the
card-internal GPU↔switch link — not the CPU↔GPU link. Measured on the root ports
(`00:01.1` / `00:01.3`), both GPUs run at a symmetric **x8/x8, Gen4 16 GT/s** — the
quantity that actually bounds tensor-parallel traffic. The 2202 flash in fact *broke*
the allocation (GPU1 fell to x4); symmetry was restored the following day, 2026-06-14,
by moving one NVMe drive off the CPU lanes to a chipset M.2 slot. The file now documents
the measurement procedure (`max_link_width` on the root port; `current_link_width`
under-reports at idle because ASPM collapses width and speed). All published envelope
quantities — load success, VRAM footprint, KV-cache capacity, max-concurrency — are
unaffected: they do not depend on link width.

**CPU-cooling A/B/C study** ([`bom/cooling-test/`](bom/cooling-test/)). The NH-D15 G2
air tower was replaced by an NL-LC1-42 420 mm AIO on 2026-08-23. Three instrumented runs
(10 min idle → 40 min all-core stress-ng → 10 min cooldown, sensors every 5 s): run A
(tower, valid), run B (AIO — **invalidated**: radiator fans at 0 RPM throughout, retained
as a negative control), run C (AIO, fans running, valid). Verdict: **thermal parity under
sustained all-core load** — ΔT above ambient 56.8 vs 56.1 K, identical 81.2 °C Tctl max,
clocks and stress-ng throughput within noise. The AIO cools down faster and measures
marginally quieter. The invalidation is documented in full, including the measurement
lesson that a zero on a channel able to report is a measurement, not missing data. Two
verification items remain open (BIOS PWM percentage against the manufacturer's ≥80 %
requirement; whether `CPU_Opt` reports the fans or the pump — every per-revolution figure
inherits that uncertainty). Run C's ΔT 56.8 K is recorded as the coolant-degradation
baseline for future re-checks.

**Public-site maintenance.** New bilingual Hardware page (bill of materials, PCIe topology
including the erratum, power and UPS, cooling study) and a fan-efficiency-per-revolution
page. Hardware content that was duplicated in Reproduce has been merged into the Hardware
page; the software pins stay with Reproduce. The architecture and evidence-percolation
pages were withdrawn from the public site on 2026-07-11 pending publication; the v0.5.0
release note describing them stands as the historical record.
[`scripts/deploy-site.sh`](scripts/deploy-site.sh) makes the `gh-pages` deploy reproducible
— between 2026-07-11 and 2026-08-23 the live site had silently drifted six weeks behind
the repository.

**Also in this release.** Post-v0.5.0 embargo scrub (internal publication-strategy working
notes removed from the tree), workstation dashboard v1.2.0, and N=1 energy-measurement
scripts plus a Qwen3.5 TP2 orchestrator under [`benchmarks/`](benchmarks/) — scripts only,
no results published.

**Embargo classification.** PUBLIC §11.1 in this release: the PCIe topology erratum, the
cooling-study procedure and its thermal/acoustic results, the site pages and the deploy
tooling. EMBARGOED §11.2/§11.3, unchanged and not in this release: all per-N throughput,
latency, power, and BF16↔AWQ precision-ablation numbers.

## v0.5.0 — 2026-07-05

This release closes the statistical-rigor and documentation surface opened by
the v0.4.0 public pipeline. It consolidates the Tier-A re-run campaign, a
precision-ablation sub-study, the single-stream latency anchor, a host-firmware
provenance reconciliation, and the first public documentation of the Layer 2
retrieval architecture. Per the per-artifact embargo policy
([`METHODOLOGY.md`](METHODOLOGY.md) §11), this entry describes the work
performed; per-N throughput, latency, and power figures remain EMBARGOED
§11.2 / §11.3 pending paper acceptance.

**Tier-A statistical re-runs (§7.4).** The Phase 2 concurrency sweep is re-run
at the full Tier-A protocol — n = 10 reps per `(quant, TP, N)` cell, each rep a
fresh vLLM process with a full model load and cooldown, results reported as
descriptive statistics (median / IQR / p95 / p99 / min / max) rather than the
single-shot exploratory (Tier 0) measurements of the v0.2 era. This puts the
suite on one statistical standard and supersedes the n = 1 characterisations for
the covered cells.

**Precision-ablation sub-study (§5.3).** A same-checkpoint BF16 ↔ AWQ
comparison over three model pairs — Bielik-4.5B-v3.0, PLLuM-8B, PLLuM-12B —
computed 2026-07-03, holding model identity fixed to isolate the quantisation
effect (the fixed-model-identity condition of Limitation 9). **Raw compute is
complete; the aggregation script is still in progress** — this release does not
yet ship a finished BF16/AWQ comparison table. Firmware consistency is noted per
pair (both PLLuM pairs on BIOS 2202; the Bielik-4.5B pair reuses a 1715 BF16
member, carrying a cross-firmware caveat).

**N = 1 single-stream anchor (§5.2 / §7.4).** The single-stream latency anchor
is complete for all model families, including the full eight-variant
Llama-PLLuM-70B AWQ family. It provides the lower-concurrency end of the
single-stream-to-plateau envelope; because it was collected under BIOS 2202
while the concurrency plateau was collected under BIOS 1715, the envelope ratio
is reported with an explicit cross-firmware provenance caveat.

**Firmware / PCIe reconciliation (§2.1).** Host-firmware provenance is
reconciled against the per-run records (referee finding M7): the Phase 1
envelope and the Phase 2 concurrency ladder were collected under BIOS 1715, the
N = 1 anchor and the precision-ablation pre-checks under BIOS 2202 (flashed
2026-06-13). The 2202 flash initially *broke* the PCIe allocation — GPU1 dropped
to x4 — and the symmetric x8/x8 link was restored the next day (2026-06-14) by
moving one NVMe drive off the CPU lanes to a chipset M.2 slot, not by the firmware
update itself. Corrected in v0.5.1; see `bom/pci-topology.md`. Envelope quantities (load success, VRAM footprint, KV-cache
capacity, max-concurrency) are firmware-independent; only the
single-stream-to-plateau ratio crosses the boundary and is flagged as such.

**Site — Layer 2 architecture documentation.** Two new pages describe the
retrieval layer publicly for the first time: `architecture.html` (the
three-layer design and the Layer 2 retrieval schematic) and
`evidence-percolation.html` (hybrid retrieval — BM25 + dense embeddings +
reciprocal-rank fusion — a frozen measurement baseline, an ablation grid, the
emergent wikilink-graph direction, and percolation-RAG as the next step). The
architecture schematic was redesigned (no crossing edges, labels off the paths),
an index-layout fix was applied, and the cite and disclosure pages were updated.

**AI usage disclosure (v1.5).** Claude Opus 4.8 and Claude Fable 5 (Anthropic)
are added to the tooling profile — Opus 4.8 for orchestration and analysis,
Fable 5 for Claude Code subagent tasks (the RAG-architecture and
evidence-percolation pages, the site redesign, adversarial pre-release review,
compute-results table extraction and figure generation, repository-consistency
auditing, and RAG backend-abstraction code), in every case operating on the
author's own measured data and decisions. The Fable 5 disclosure now appears on
both the Zenodo deposit notes and the cite page.

**Documentation consistency pass.** This release resolves a batch of
documentation gaps found in a repository-consistency audit: the version string
is synced to 0.5.0 across README, `CITATION.cff`, the site, and the
METHODOLOGY §13 version table; `CITATION.cff` gains an `identifiers:` block
carrying the concept DOI; and the METHODOLOGY citation line is corrected from
the v0.1.0 version DOI to the concept DOI.

**Embargo classification (PUBLIC §11.1, in this release).** Tier-A protocol
description, engineering envelope, firmware provenance, single-stream-anchor
methodology, precision-ablation design, site documentation, AI-usage
disclosure, and version/citation metadata.

**Embargo classification (EMBARGOED §11.2 / §11.3, NOT in this release).**
Per-N throughput, latency distributions, KV-cache occupancy curves, mean output
length, W/tok, single-stream tok/s, the single-stream-to-plateau ratio, the
BF16-vs-AWQ precision-ablation numbers, and any cross-model comparative claim
using concrete numbers. These remain in the gitignored `benchmarks/results/`
tree pending paper #1 acceptance.

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
checked in. Generation pipeline
is BLOCKED on reviewer responses; no answers have been generated.

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
