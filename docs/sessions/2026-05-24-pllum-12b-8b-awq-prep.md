# Session 2026-05-24 — PLLuM-12B + 8B chat-2512 AWQ prep (Run-3)

**Date:** 2026-05-24
**Maintainer:** Łukasz Minarowski (ORCID 0000-0002-2536-3508)
**Status:** prep — scripts ready, MI300X provision + run pending
**Scope:** Rozszerzenie rodziny AWQ vLLM-native z `Llama-PLLuM-70B` (Run-1 + Run-2, 8 modeli, 2026-05-21/22)
na **`PLLuM-12B-chat-2512`** (mistral / apache-2.0) i **`Llama-PLLuM-8B-chat-2512`** (llama / llama3.1).

## 1. Motivation

Run-1 + Run-2 pokryły wyłącznie 70B (8 wariantów). Footprint po AWQ ~37 GB (TP=2 na 2× R9700) —
*prosumer envelope only*. Po obejrzeniu downloads CYFRAGOVPL 2512 family okazało się,
że największy segment użytkowników siedzi w 4B / 12B (639 + 137 dl/mo) — czyli laptop /
single consumer GPU, nie workstation. 70B AWQ adresuje wąską niszę; 12B/8B AWQ adresuje
szeroki rynek consumer.

| CYFRAGOVPL repo | Arch | Downloads/mo | mozarcik AWQ | Decyzja |
|---|---|---|---|---|
| PLLuM-4B-chat-2512 | gemma3 | **639** | brak | Stretch — fragile w llm-compressor (PR #2571 OPEN, eval #2522 OPEN) |
| **PLLuM-12B-chat-2512** | mistral | **137** | brak | **Run-3 primary** — mistral arch sprawdzona |
| **Llama-PLLuM-8B-chat-2512** | llama | 52 | brak | **Run-3 primary** — llama arch sprawdzona (same co 70B) |
| Llama-PLLuM-70B-chat-2512 | llama | 31 | ✅ (60 dl) | Run-2 done |

Gemma3 odpada z primary: GitHub `vllm-project/llm-compressor` ma 2 OPEN issues
(#2571 AWQ input layernorm mapping, #2522 evaluate AWQ/GPTQ for Gemma) sugerujące
fragile pipeline — risk garbage output. 4B przesunięte do stretch goal z latest main.

## 2. Hardware envelope claim — narrative shift

| Family | Footprint AWQ | Audience | Narracja |
|---|---|---|---|
| 70B | ~37 GB total (TP=2) | prosumer workstation 2× 32 GB | "first PLLuM 70B that fits on consumer 2× R9700" |
| **12B** | ~6-7 GB est. | **consumer 12-16 GB GPU** (RTX 3060 12 GB / RTX 4060 Ti / RDNA3 16 GB) | **"democratizes Polish clinical LLM access on prosumer GPU"** |
| **8B** | ~4-5 GB est. | **consumer 8 GB GPU / laptop** (RTX 3060 8 GB / RTX 4060 / mobile) | **"Polish clinical LLM na laptopie"** |

Hook techniczny mocniejszy niż dla 70B: wide consumer reach, edge / laptop deployment.

## 3. Platform

Re-use Run-1 + Run-2 platform pattern.

| Component | Configuration |
|---|---|
| Provider | AMD Developer Cloud (continuing GPU credit, ~30-day validity from grant) |
| Accelerator | 1× AMD Instinct MI300X, 192 GB HBM3 |
| Quantization tool | llm-compressor 0.10.0.2 (compressed-tensors, pack-quantized W4A16) |
| Calibration corpus | `mozarcik/clinical-pl-smpc-awq-calibration` — same as Run-1/2 (418 chunks clinical-PL SmPC) |

Wybór MI300X (vs lokalny R9700): 12B + 8B BF16 oba mieszczą się na single R9700 (32 GB),
ale routing do MI300X utrzymuje lokalny pair wolny + walltime znacznie krótszy (~30 min total
vs ~3-4h na R9700 dla obu). Pipeline identyczny co Run-1/2 — minimal risk.

## 4. Competitive scan (2026-05-24)

HuggingFace search ` PLLuM-12B awq`, `PLLuM-12B compressed-tensors`, `Llama-PLLuM-8B-chat-2512 awq`:
**0 hits** dla AWQ / W4A16 / compressed-tensors / GPTQ na 12B-chat-2512 i 8B-chat-2512.

GGUF alternatywy mradermacher pokrywają część rodziny (i1-GGUF / i-matrix wariantów),
ale **AWQ vLLM-native pozostaje pusta nisza** — claim "first AWQ" defensible.

## 5. Scripts (zaadaptowane)

```
calibration/quantization/run_quant3.sh    — batch 12B + 8B chat-2512 download → quant
calibration/quantization/upload3.sh       — weights upload (private), README + LICENSE separate
```

`quant_llmc.py` bez zmian — generic, przyjmuje (model_path, output_dir, calib_path).
Corpus na MI300X scratch (`/scratch/corpus.jsonl`) z poprzednich runów albo re-upload.

## 6. License compliance — per-base

| Model | Base | License | Required artefacts (HF push) |
|---|---|---|---|
| PLLuM-12B-chat-2512 | Mistral-Nemo-Base-2407 | **apache-2.0** | LICENSE (Apache 2.0). NOTICE / USE_POLICY nie wymagane. |
| Llama-PLLuM-8B-chat-2512 | Llama-3.1-8B | **llama3.1** | LICENSE (Meta), NOTICE (Meta exact wording), USE_POLICY.md (Meta AUP), "Built with Llama" attribution w README. Same compliance co 70B Run-1/2. |

12B = łatwy push (tylko LICENSE). 8B = full Llama 3.1 CL same drill co 70B.

## 7. Release pipeline gates

Reuse `/tmp/pllum-release/` artifacts z Run-2 (commit 8244b6d) z 3-tier review już zrobionym:

| Gate | Artifact | Status |
|---|---|---|
| Gate 0 — competitive scan | §4 above | DONE |
| Gate 1 — sanity envelope | `environment/sanity-tests/2026-05-24-PLLuM-12B-chat-2512-awq.json` + `…-8B-…json` | PENDING (after quant) |
| Gate 2 — coherence probe | `environment/coherence-probes/2026-05-24-PLLuM-12B/8B-coherence-raw.txt` | PENDING (after sanity PASS) |
| Gate 3 — throughput sweep | `benchmarks/results/PLLuM-12B/8B-chat-2512-awq/…` | EMBARGOED §11.2/§11.3 |
| Card review | ChatGPT + Gemini + adversarial red team (per Run-2 §4.2) | PENDING (after card render) |

## 8. Open decisions

1. **MI300X provision**: do you have an active instance from grant, or do we provision fresh? (Critical-path blocker.)
2. **12B AWQ na 2× R9700 — czy TP=2?** AWQ ~6-7 GB mieści się na 1× R9700 z dużym headroom, TP=1 wystarczy. Sanity envelope inny niż 70B (per-GPU vs total).
3. **8B AWQ na 2× R9700**: AWQ ~4-5 GB. TP=1 oczywiste. Też test TP=2 dla porównania scaling? Decyzja: pomijamy, TP=1 only — narrow scope dla Run-3.
4. **Stretch 4B-gemma3 timing**: po sukcesie 12B + 8B, czy odpalamy 4B na separately provisioned instance? Wymaga latest main llm-compressor + cherry-pick PR #2571.

## 9. Next actions (kolejność)

1. Provision MI300X (Łukasz) lub re-attach do istniejącego instancja
2. `scp` `run_quant3.sh`, `upload3.sh`, `quant_llmc.py`, `corpus.jsonl` na `/scratch/` instance
3. `bash /scratch/run_quant3.sh` → ~30 min walltime
4. `scp` AWQ checkpoints z `/scratch/out/` na lokalny R9700 dla Gate 1 + Gate 2
5. Sanity sweep (TP=1) — adapted skrypt `sanity_sweep_pllum_12b_8b_awq.sh` (do napisania)
6. Coherence probe (chain-fire from sanity)
7. Renderuj 2 model cards z templates per license — `generate-readmes-3.sh` (do napisania, fork Run-2 generator)
8. 3-tier review cards (ChatGPT + Gemini + adversarial)
9. Apply review fixes
10. Pilot push (`PLLuM-12B-chat-2512-awq`), visual verify, bulk push (`Llama-PLLuM-8B-chat-2512-awq`)
11. Flip public + LinkedIn announce + Collection update + Discussion drafts na CYFRAGOVPL repo

## 10. Embargo

Identyczna polityka co Run-1/2:
- Footprint / load time / KV / max_concurrency / single-request response time: **PUBLIC §11.1**
- Throughput / latency / scaling-with-N: **EMBARGOED §11.2 + §11.3** (paper-bound)

Coherence probe raw outputs: PUBLIC §11.1.

## 11. Decision log

- **Pivot z 4B-gemma3 do 12B-mistral + 8B-llama**: blokada llm-compressor PR #2571 OPEN + eval #2522 OPEN. Risk garbage output na fragile pipeline. 4B przesunięte do stretch goal z latest main.
- **Cel: 2 modele, nie 6+**: scope-discipline. Pełna rodzina 4B/8B/12B × base/instruct/chat (9 modeli) po sukcesie 12B + 8B chat — Run-4 jeśli demand się potwierdzi.
- **MI300X (cloud) vs R9700 (lokalny)**: cloud uważam wciąż za better routing — lokalny pair wolny dla R9700 paper sweep (Phase 2 v0.3), walltime 4× szybszy.

---

*Plan zaakceptowany 2026-05-24. Następne Twoje uruchomienie: provision MI300X + scp + bash run_quant3.sh.*

## 12. Inter-session handoff

Druga sesja Claude Code (MI300X-side) pracuje przeciwko append-only handoff document:
[`docs/handoff/2026-05-24-pllum-12b-8b-awq-mi300x.md`](../handoff/2026-05-24-pllum-12b-8b-awq-mi300x.md).

Synchronizacja przez git commit/push na `main` (submodule navimed-umb, remote `origin`
= `github.com/kicrazom/navimed-umb`).
