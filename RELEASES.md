# Release history

Per-release notes for NaviMed-UMB: scope, headline findings, and scaling
results for each tagged version. The current release summary lives in
[`README.md`](README.md); the universal benchmark protocol lives in
[`METHODOLOGY.md`](METHODOLOGY.md).

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

Key measurements:

- TP=1 plateau: 3870 tok/s (saturates from N=500, std dev 0.3%)
- TP=2 plateau: 2940 tok/s (24% PCIe all_reduce tax vs TP=1)
- TP=2 only wins at N=50 (+9%), loses at every higher concurrency
- Thermal asymmetry between GPU 0 and GPU 1 (5C delta, airflow-dependent)

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
