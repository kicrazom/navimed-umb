---
type: visibility-draft
target: researchgate
mirrors_zenodo_doi: 10.5281/zenodo.20364953
release: v0.4.0
created: 2026-05-26
status: ready-to-paste
language: en
purpose: |
  ResearchGate-facing description for the NaviMed-UMB project page and for the
  v0.4.0 research-item entry that mirrors the Zenodo DOI 10.5281/zenodo.20364953.
  RG audience is international (mostly non-Polish), so the tone is academic-formal
  IMRAD-style English; past tense for completed work; no marketing language.
sources:
  - logbook/2026-05-26.md
  - RELEASES.md
  - .zenodo.json
  - docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md
  - ~/models/Llama-PLLuM-8B-chat-2512-awq/README.md
  - ~/models/PLLuM-12B-chat-2512-awq/README.md
---

## Short abstract (~150-200 words, RG project-page summary)

NaviMed-UMB is a hardware-envelope study of local large language model deployment on consumer-grade dual AMD Radeon AI PRO R9700 workstations (32 GB VRAM per card, gfx1201, RDNA 4 / Navi 48) under ROCm 7.2.x and vLLM 0.19.x. The project targets medical-AI infrastructure for privacy-sensitive workloads in which cloud inference is contractually or legally unavailable, and reports a reproducible benchmark protocol together with public model-release pipelines. Release v0.4.0 ships a reproducible AWQ W4A16 quantization pipeline for the PLLuM family of Polish-language large language models, spanning 8B and 12B variants that fit on a single consumer R9700 and a 70B flagship deployed on two cards under tensor parallelism. The same Polish Summary-of-Product-Characteristics calibration corpus was used across the entire family, enabling controlled cross-scale comparison of post-training quantization quality. The release ships engineering-envelope evidence and Polish-clinical sanity gates as public artifacts; per-N throughput, latency, and energy measurements are held under a documented embargo pending peer-reviewed publication. (~190 words)

## Extended abstract (~300-450 words, v0.4.0 item description)

This research item documents NaviMed-UMB release v0.4.0, a hardware-envelope study of local large language model deployment on consumer-grade dual AMD Radeon AI PRO R9700 workstations (32 GB VRAM per card, gfx1201, RDNA 4 / Navi 48) executed under ROCm 7.2.x and the vLLM 0.19.0+rocm721 inference stack. The work targets medical-AI infrastructure for privacy-sensitive workloads — clinical natural language processing, regulatory and Summary-of-Product-Characteristics question answering, and Polish-language assistant deployment — in which cloud inference is not a permissible deployment path.

The v0.4.0 contribution is a reproducible AWQ W4A16 release pipeline for the PLLuM family of Polish-language large language models. The pipeline covers consumer-GPU-fitting 8B and 12B variants deployable on a single R9700, and the 70B family flagship deployed on two R9700 cards under tensor parallelism. The same Polish Summary-of-Product-Characteristics calibration corpus — 418 European Medicines Agency drug-information fragments, no patient health information — was reused across the entire family, so cross-scale comparisons of language preservation under post-training quantization are corpus-controlled.

The consumer-GPU engineering envelope, measured on a single R9700 with tensor-parallel size 1, eager execution, and max_seq_len = 2048, was as follows. The Llama-PLLuM-8B-chat-2512 AWQ checkpoint occupied 5.53 GiB of weights, leaving 22.22 GiB of KV-cache budget and a maximum-concurrency envelope of 88.89×. The PLLuM-12B-chat-2512 AWQ checkpoint occupied 8.03 GiB of weights, leaving 19.77 GiB of KV-cache budget and a maximum-concurrency envelope of 63.27×. Both checkpoints passed a five-prompt Polish-clinical sanity gate (5/5 PASS each) covering factual, definitional, syndromic, instructional, and procedural prompts, served via the /v1/completions endpoint of vLLM. Quantization was executed with llm-compressor 0.10.0.2 using device_map='auto' across two R9700 cards; the 12B AWQ pass completed in approximately 25 minutes of walltime.

The release also documents a reusable failure-mode post-mortem: the hf_transfer accelerated download path silently truncated tokenizer-adjacent shards of the 12B BF16 source, producing a misleading downstream ImportError for protobuf as the visible symptom. The rescue protocol — sequential curl-per-shard against the Xet content bridge cas-bridge.xethub.hf.co with IPv4 forced — restored deterministic shard integrity and is documented as reusable guidance for operators on flaky-IPv6 networks.

Per the project methodology document, this release ships public engineering-envelope evidence only (METHODOLOGY §11.1). Per-N throughput, latency distributions, KV-cache occupancy curves, and energy-per-token measurements remain under embargo (§11.2; the stricter §11.3 applies to Polish-language models) pending peer-reviewed publication. The outline of the corresponding engineering benchmark paper (Paper #1, MDPI Electronics / IEEE Access target) is locked in this release. (~445 words)

## Keywords (RG taxonomy, 5-10 terms)

- large language models
- model quantization
- AWQ
- LLM benchmarking
- local inference
- consumer GPU
- AMD RDNA 4
- ROCm
- vLLM
- medical AI
- Polish language models
- PLLuM
- post-training quantization
- reproducibility

## Suggested research items to upload separately as RG artifacts

1. **NaviMed-UMB v0.4.0 — Technical Report (primary item).**
   Upload as ResearchGate item type *Technical Report* and use the Extended abstract above as the description. Set the Zenodo DOI `10.5281/zenodo.20364953` as the primary identifier; link the GitHub source repository `https://github.com/kicrazom/navimed-umb` and the HuggingFace model repositories as supplementary URLs. RG will treat the Zenodo record as the canonical persistent identifier.

2. **Gate 1 sanity evidence — Llama-PLLuM-8B-chat-2512 AWQ.**
   Upload as ResearchGate item type *Data* (or *Raw Data* / *Dataset* depending on RG taxonomy availability for the account). Source file: `environment/sanity-tests/2026-05-26-Llama-PLLuM-8B-chat-2512-awq-sanity.json` from the source repository. Description: raw JSON output of the five-prompt Polish-clinical sanity gate, 5/5 PASS, served via /v1/completions. This is PUBLIC §11.1 evidence.

3. **Gate 1 sanity evidence — PLLuM-12B-chat-2512 AWQ.**
   Upload as ResearchGate item type *Data*. Source file: `environment/sanity-tests/2026-05-26-PLLuM-12B-chat-2512-awq-sanity.json`. Description: raw JSON output of the five-prompt Polish-clinical sanity gate, 5/5 PASS, served via /v1/completions. PUBLIC §11.1 evidence.

4. **Paper #1 — Results-section outline (preprint placeholder).**
   Source file: `paper/paper-1-results-outline.md`. Upload as ResearchGate item type *Preprint* if RG accepts an outline-stage artifact, otherwise note as *Forthcoming* on the project page and upload the preprint once Paper #1 reaches a citable manuscript form (MDPI Electronics or IEEE Access target, Q1 2027). The outline scope is the engineering benchmark trade-offs documented in §11.1 of the project methodology.

5. **Calibration corpus reference (link-only).**
   The Polish SmPC calibration corpus is published as a HuggingFace dataset (`mozarcik/clinical-pl-smpc-awq-calibration`, 418 fragments, no PHI). Link it as a *Supplementary Material* URL on the v0.4.0 RG item rather than re-uploading; this preserves a single canonical copy and avoids duplicate-artifact confusion across platforms.

## Author affiliation and AI assistance disclosure

Author: Łukasz Minarowski, Department of Respiratory Physiopathology, Medical University of Białystok, Poland. ORCID 0000-0002-2536-3508. Acknowledgements to the PLLuM consortium (SpeakLeash, OPI-PIB, NASK, Politechnika Wrocławska) and to the Ministry of Digital Affairs of the Republic of Poland for publishing the PLLuM base checkpoints used in this release.

AI assistance disclosure. Project documentation was prepared with assistance from large language models (Claude — Anthropic; GPT — OpenAI; a locally-served Bielik-11B-v3.0-instruct-AWQ on a single R9700 was used for Polish-language editorial work). All experimental design, hardware configuration, empirical measurements, and scientific claims are the author's. AI tools did not execute experiments, generate quantized weights, or validate benchmark measurements. The full disclosure is published in `AI_USAGE_DISCLOSURE.md` in the source repository.
