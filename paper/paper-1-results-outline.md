# Paper #1 — Results section outline

**Working title:** Quantization Trade-offs for Polish Clinical LLMs on AMD RDNA 4
**Target venue:** MDPI Electronics / IEEE Access (Q1, 2027)
**Status:** structure locked 2026-05-24 (data complete from v0.4.0 sweep); draft pending
**Embargo classification:** §11.2 (per-N throughput, scaling numbers) until paper acceptance; §11.1 (engineering envelope) public

---

## 3. Results

### 3.1. Quantized model release and artifact completeness

- 8 PLLuM-70B checkpoints quantized to AWQ W4A16 (`base × {2412, 2508}` + `instruct × {2412, 2508, 2512}` + `chat × {2412, 2508, 2512}`)
- Model cards (per-variant, dual-platform vLLM snippets, Gate 1+2 evidence linked)
- Llama 3.1 Community License compliance artifacts: `LICENSE`, `NOTICE` (exact Meta wording), `USE_POLICY.md`
- Calibration dataset published separately and reusable: `mozarcik/clinical-pl-smpc-awq-calibration` (418 fragments, Polish ChPL/SmPC, EMA-sourced, 81 INNs, 9 NFZ programmes, No PHI)
- DOI-linked benchmark repository on Zenodo (concept DOI 10.5281/zenodo.19851346; version DOI assigned per release)
- Public LinkedIn announcement reaching Polish clinical-AI community (activity 7464059097575907328)

### 3.2. Deployment feasibility on dual Radeon AI PRO R9700

- Load success: 6/6 sanity-PASS variants load consistently on 2× R9700 (gfx1201, TP=2, vLLM 0.19.0+rocm721, enforce_eager)
- Memory footprint: identical envelope across the family (architectural property of shared Llama-3.1-70B base)
- Load time
- KV cache capacity at default and extended `max_seq_len`
- Maximum context: limited by HBM and KV cache budget
- Concurrency envelope: `max_concurrency` at max_seq_len 8192 per Phase 1 (PUBLIC §11.1: 6.7 req)

### 3.3. Inference performance under vLLM / ROCm

- Throughput (tok/s) as a function of concurrent prompts `N ∈ {10, 25, 50, 100, 200, 500, 1000}`
- Per-token latency distribution (TTFT, TPOT)
- Scaling with concurrency: knee location and plateau value
- Prompt / output length sensitivity (METHODOLOGY §6 synthetic workload — 8 templates × 20 topics, temp=0.7, max_tokens=128)
- **§11.2/§11.3 embargo:** all numerical throughput, latency, scaling, and power values are paper-bound; aggregated qualitative shape (knee, plateau, regime transitions) is reportable

### 3.4. Runtime stability and ROCm-specific constraints

- vLLM `0.19.0+rocm721` PINNED; nowsze ROCm wheels mają regresje na gfx1201 (cf. Capitelli #40980 tracker)
- `enforce_eager=True` MANDATORY na gfx1201 — CUDA graphs ścieżka segfault'uje `libhsa-runtime64`
- Required env vars: `VLLM_ROCM_USE_AITER=0`, `AMD_SERIALIZE_KERNEL=1`, `HIP_LAUNCH_BLOCKING=1`, `ROCR_VISIBLE_DEVICES=0,1`, `NCCL_P2P_DISABLE=1`
- Known failure modes: chat-template absence for `base` variants (HTTP 400 on `/v1/chat/completions`; resolved by routing to `/v1/completions`), `llm-compressor` `v_proj` skip artifact on GQA architectures (Llama 3.1 family), AWQ kernel performance gap on gfx1201 vs comparable NVIDIA tiers
- Reproducible environment: pinned versions in `environment/` manifests, exact env var set in `scripts/_env.sh`, hardware envelope numbers per Phase 1 sanity (PUBLIC §11.1)

### 3.5. Coherence probe as vehicle-integrity check (METHODOLOGY §8 boundary)

- Polish-language outputs across five varied prompt categories (factual, instruction, summarization, definition, comparison)
- No repetition collapse on extended generation (`max_tokens=256`)
- No mechanical degeneration: outputs remain coherent Polish across all six sanity-PASS variants
- **Explicit §8 boundary:** this is NOT a clinical-task evaluation. Coherence probe is a *vehicle-integrity* check answering one question — *did quantization damage the model such that it can no longer produce coherent Polish text?* — not *is the model good at Polish clinical Q&A?* The latter is the scope of the separately-tracked `eval-rag/` sub-project.
- Auto-flag mechanism (n-gram heuristic) + human override pattern (`<probe>.human_verdict.json`, audit-trail logged) — METHODOLOGY §8 extension

---

## Discussion structure (notes for later)

- 5.1. Within-family observation: chat-2508 outperforms chat-2512 by ~12% peak throughput despite being older; decomposition into shorter-output (SFT improvement) + prefill overhead + per-token decode regression
- 5.2. Implications for clinical deployment (which variant to pick for what use case)
- 5.3. Limitations
  - Single-shot exploratory measurements (Tier A statistical reruns scheduled for v0.5.0 per METHODOLOGY §7.4)
  - No model-quality evaluation in this paper — explicit §8 boundary, deferred to `eval-rag/` follow-up
  - AWQ-specific findings — AQLM 2-bit single-card variant scoped for v0.5.0
  - Hardware-specific (gfx1201) — NVIDIA portability claimed via `awq_marlin` but not independently validated in this release
- 5.4. Future work
  - Tier A statistical reruns (n=10 with Holm-Bonferroni FWER per METHODOLOGY §7.4)
  - AQLM 2-bit single-card quantization (conditional on `eval-rag/` result and pre-flight on R9700)
  - Cross-tier `plot_canonical.py` (PLAN-NEXT §1.5 outstanding)
  - Companion model-quality paper (eval-rag pilot or full PTChP-aligned study with Białas / Radliński as proposed co-authors)
