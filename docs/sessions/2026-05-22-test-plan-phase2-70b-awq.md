---
related:
  - "[[10_Projekty/0001-navimed-umb/docs/sessions/2026-05-21-pllum-70b-awq-amd-mi300x|2026-05-21-pllum-70b-awq-amd-mi300x]]"
---

# Test Plan — Phase 2 closure (70B AWQ tier) and forward roadmap

**Date:** 2026-05-22
**Maintainer:** Łukasz Minarowski (ORCID 0000-0002-2536-3508)
**Status:** active
**Scope:** Phase 1 + Phase 2 for the eight Llama-PLLuM-70B AWQ checkpoints; forward roadmap.

## Context

The Phase 2 v0.3 scaling sweep is complete for 12 models. The 70B tier was
blocked on quantization: every Llama-PLLuM-70B checkpoint in BF16 (~132 GB)
exceeds the 64 GB aggregate VRAM of the 2× R9700 pair (METHODOLOGY §4.3). Eight
checkpoints were quantized to AWQ W4A16 (~37 GB each) on AMD MI300X — see
`2026-05-21-pllum-70b-awq-amd-mi300x.md`. They now re-enter the suite for local
Phase 1 / Phase 2.

Models under test (8): `Llama-PLLuM-70B-{base,instruct,chat}-{2412,2508,2512}-awq`
— base ×2, instruct ×3, chat ×3.

## Evaluation strategy — four sequential gates

Each model passes through four gates in order; failing a gate stops that model.

### Gate 1 — Hardware envelope (Phase 1)

Loads on 2× R9700 at TP=2? (~37 GB AWQ < 64 GB; PLLuM-70B is a Llama-3.1-70B
base — `intermediate_size` 28672 divides evenly by `group_size` × TP, so it is
not expected to hit the shard/group alignment failure seen with
Kimi-Dev-72B-AWQ, §4.4). Record: load time, peak VRAM per GPU, KV-cache tokens,
`max_concurrency`. Sanity output classified three-state: `ok` / `degenerate` /
`parse_fail`. **Pass:** `ok`.

### Gate 2 — Quantization integrity (AWQ-QA)

These are first-party quantizations carrying a documented artifact:
llm-compressor skips AWQ activation-scaling for `v_proj` on GQA models. A
"not degenerate" verdict from Gate 1 is insufficient. A short Polish-language
probe (~5 prompts per model) checks that the quantized model still produces
coherent Polish text. This is a **vehicle-integrity check** — did quantization
damage the model — **not** a model-quality evaluation; the §8 boundary is
preserved. Probe output is auto-flagged (language, non-degeneracy, length) and
the raw text retained for human spot-check. **Pass:** coherent Polish output.
Degradation → recorded as a finding (v_proj artifact is real) and triggers a
re-quantization decision.

### Gate 3 — Phase 2 scaling sweep

For models past Gates 1–2: standard sweep, N ∈ {10…1000}; knee, plateau,
thermal envelope, power, W/tok. Numbers EMBARGOED per §11.2.

### Gate 4 — Comparative analysis

Within-family: base / instruct / chat across versions 2412 / 2508 / 2512 — does
the envelope or scaling differ between model versions? Cross-tier: 70B AWQ
against the existing tiers, observing §10 limitation 9 (cross-quantization
comparisons are valid only at fixed model identity — envelope, not raw
throughput).

## Planned steps

| # | Step | Owner | Notes |
|---|---|---|---|
| 0 | `chat-2508` download completes → 8/8 on disk | (running) | last model |
| 1 | Gate 1 — sanity, 8 models | runner | ~2 h (serve TP=2 + probe per model) |
| 2 | Gate 2 — Polish coherence probe, sanity-PASS models | runner | new probe; ~20 min |
| 3 | Review probe output; decide which models proceed | Łukasz + orchestrator | human-reviewed gate |
| 4 | Gate 3 — Phase 2 sweep, models past Gates 1–2 | runner | multi-hour; AWQ 4–10× slower — real ETA after first model |
| 5 | Gate 4 — comparative analysis → input to `paper/` | orchestrator | |
| 6 | Suite closure — confirm Phase 2 v0.3 complete (20 models) | orchestrator | |

The AWQ test runner is being restructured into three explicitly-launchable
stages — sanity, coherence probe, sweep — so the long sweep (Gate 3) starts only
after Gate 2 review.

## Forward roadmap (post-70B-AWQ)

- **Phase B** (separate manuscript track): Kimi-Linear-48B-A3B-Instruct and
  Qwen3.6-35B-A3B-FP8 (MoE benchmarks); Kimi-Dev-72B-AWQ head-to-head on AMD
  (not deployable on 2× R9700, §4.4).
- **v0.5 — undervolted re-run** (−75 mV / +15 W) of the full suite. Directly
  exercises the W/tok energy-efficiency axis (§7.1) — high value, retained.
- **Lemonade Server cross-stack (former v0.4) — DEFERRED.** A vLLM-vs-Lemonade
  comparison is a different inference stack, not core to the envelope/scaling
  question (§1). It stays in the roadmap only if it becomes a comparability
  requirement against the Capitelli (kyuz0) reference, or if a concrete
  desktop-latency research question is defined. Until then it is not scheduled;
  METHODOLOGY §4.7 / §10.3 to be updated accordingly.

## Open decisions

1. Verify whether the Capitelli (kyuz0) reference methodology has a Lemonade
   dependency before fully dropping the former v0.4 phase.
2. Re-quantization policy if Gate 2 flags v_proj-artifact degradation.
