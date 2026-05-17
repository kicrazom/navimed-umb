---
type: plan
status: active
domain: [navimed-umb, ai-stack, benchmarking]
created: 2026-05-17
related_projects: [[navimed-umb]], [[broncho-nome]], [[ego-architecture-ai]]
---

# Sweep Phase 2 v0.3 — Plan

## Cel

Rozszerzyć Phase 2 inference sweep o (A) odświeżone wersje obecnych modeli,
(B) nowych pretendentów (Kimi-Dev-72B, Kimi-Linear, Qwen3.6-35B-A3B),
(C) multimodal probe (Kimi-VL, Llama-4-Scout) pod kątem Broncho-Nome.

## Embargo

| Faza | Embargo | Publikacja |
|---|---|---|
| **A** (refresh) | TAK — bieżący Phase 2 paper | nie publikować throughput numbers przed akceptacją |
| **B** (nowi pretendenci) | osobne, follow-up paper | numbery wewnętrznie do navimed-umb decision; manuscript drugi |
| **C** (multimodal) | osobne, ten sam follow-up paper jak B | tag "VL" w datasecie benchmarków |

## Modele

### Faza A — refresh (do bieżącego papera)

| Lokalny katalog | HF repo | Zastępuje |
|---|---|---|
| `bielik-pl-11b-v30-instruct` | `speakleash/Bielik-PL-11B-v3.0-Instruct` (2026-04-14) | `bielik-11b-v23` |
| `bielik-11b-v30-instruct-awq` | `speakleash/Bielik-11B-v3.0-Instruct-awq` (2025-12-31) | `bielik-11b-v23-awq` |
| `llama-pllum-70b-base-250801` | `CYFRAGOVPL/Llama-PLLuM-70B-base-250801` | `llama-pllum-70b-base` |
| `llama-pllum-70b-chat-250801` | `CYFRAGOVPL/Llama-PLLuM-70B-chat-250801` | `llama-pllum-70b-chat` |
| `qwen3.5-9b` | `Qwen/Qwen3.5-9B` (2026-02-27) | `qwen25-7b-instruct` |

⚠️ **`llama-pllum-70b-instruct-250801` nie istnieje** na HF — refresh jest tylko dla base i chat. Linia instruct zostaje na oryginale.

### Faza B — nowi pretendenci (follow-up paper)

| Lokalny katalog | HF repo | Po co |
|---|---|---|
| `kimi-dev-72b` | `moonshotai/Kimi-Dev-72B` (2025-06-16, Qwen2.5-72B base, SWE-bench SoTA) | head-to-head vs `qwen25-72b-awq` |
| `kimi-linear-48b-a3b-instruct` | `moonshotai/Kimi-Linear-48B-A3B-Instruct` (2025-10-30) | long-context CDSS, linear attention test |
| `qwen3.6-35b-a3b-fp8` | `Qwen/Qwen3.6-35B-A3B-FP8` (2026-04-21) | MoE A3B na gfx1201, scaling vs Qwen3.6-27B |

### Faza C — multimodal probe (follow-up paper)

| Lokalny katalog | HF repo | Po co |
|---|---|---|
| `kimi-vl-a3b-thinking-2506` | `moonshotai/Kimi-VL-A3B-Thinking-2506` | bronchoskopia obrazy, RTG, krzywe |
| `llama-4-scout-17b-16e-instruct` | `meta-llama/Llama-4-Scout-17B-16E-Instruct` | natywny multimodal, alternatywa VL |

## Modele POMIJANE

- **Kimi-K2 / K2.5 / K2.6 / K2-Thinking / K2-Instruct-0905** — MoE 1 TB params,
  wymagają 300-700 GB VRAM (fp8/fp16). Niedostępne lokalnie. Tylko cloud API.
- **Qwen3.5-397B-A17B** — MoE 397B, ~200 GB Q4, nie zmieści w 64 GB VRAM.
- **Llama-3.1-405B** — dense, nie ma szans bez DGX.
- **Mistral-Nemo / Mixtral 8x7B** — linia martwa, Mistral porzucił Mixtral.

## Hardware constraints (do uwzględnienia w sweepie)

| Issue | Workaround | Koszt |
|---|---|---|
| **TP=2 deadlock gfx1201** (vLLM #40980) dla Qwen3.x i Kimi-Linear | `--enforce-eager` | −15-25% throughput |
| **FP8 wolniejszy od BF16 ~75%** na R9700 (brak AITER) | testuj **obie** wersje (FP8 + BF16) | więcej runs |
| **Kimi-Dev-72B brak AWQ na HF** | quantize lokalnie AutoAWQ + `--quantization awq_marlin` | ~4-6h preprocessing |
| **Linear attention kernel** w Kimi-Linear | `--no-enable-prefix-caching` na start | utrata cache benefits — przetestować z/bez |

## Plan wykonania

```
# Day 1
./sweep_phase2_v0.3.sh download-all     # ~2-3h download (zależnie od BW)

# Day 1-2
./sweep_phase2_v0.3.sh serve-a          # integrate z hvezda.py harness dla N-points
# update METHODOLOGY.md z nowymi baseline numbers

# Day 3-5
./sweep_phase2_v0.3.sh serve-b
# Kimi-Dev-72B quantize step:
# python -m awq.entry --model_path ~/models/kimi-dev-72b --quant_path ~/models/kimi-dev-72b-awq

# Day 6-7
./sweep_phase2_v0.3.sh serve-c
# tag dataset "VL" — osobne metryki (image tokens/s, latency per request)
```

## Otwarte pytania

1. **AutoAWQ + ROCm 7.2.1** — czy autoawq buduje się bezbłędnie? Backup plan: GPTQ via vLLM serve config.
2. **Linear attention vs prefix cache** — testuj oba; może być policy decision dla navimed-umb.
3. **Llama-4 vLLM support** — sprawdź release notes 0.19.0 czy Scout/Maverick są w pełni wspierane na ROCm (na CUDA tak od 0.18).
4. **MLOps tracking** — nadal brak. Sugestia: **MLflow lokalnie** (Docker) dla Phase 2 v0.3, żeby nie tracić runów do `METHODOLOGY.md` ad-hoc.

## Powiązania

- Główne repo navimed-umb: `[[navimed-umb]]`
- Kontekst multimodal: `[[broncho-nome]]` (Faza C)
- AI Stack MOC: `[[90_Meta/MOC-AI-Stack]]`
