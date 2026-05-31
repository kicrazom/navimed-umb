---
type: session
model: bielik-pl-11b-v30-instruct
phase: 1_envelope
embargo: PUBLIC
parent: "[[METHODOLOGY|METHODOLOGY.md]]"
date: 2026-05-18
operator: Łukasz Minarowski
methodology_version: 1.0
transport: vllm-serve-openai-api
tags: [navimed-umb, phase1, envelope, bielik, polish-llm, sanity]
related:
  - "[[2026-05-17-bielik-4.5b-v30-post-refactor-sanity]]"
  - "[[2026-05-17-bielik-11b-v30-tp1-sanity]]"
  - "[[2026-05-17-bielik-11b-v30-tp2-sanity]]"
  - "[[METHODOLOGY]]"
artifacts:
  - "environment/sanity-tests/2026-05-18-bielik-pl-11b-v30-vllm-tp1-bf16.json"
  - "environment/sanity-tests/2026-05-18-bielik-pl-11b-v30-vllm-tp1-bf16.log"
---

# Bielik-PL 11B v3.0 Instruct — Phase 1 envelope sanity test (TP=1, BF16, vllm serve)

**Date:** 2026-05-18T04:26:51Z → 2026-05-18T04:28:24Z (UTC)
**Operator:** Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>
**Methodology:** [[METHODOLOGY|METHODOLOGY.md]] v1.0 §3.1, §3.3, §4.2, §5.1, §8, §9, §11
**Embargo:** **PUBLIC** (Phase 1 envelope, single sanity prompt, OpenAI-compatible transport)
**Related:** [[2026-05-17-bielik-4.5b-v30-post-refactor-sanity|4.5B v3.0 sanity]], [[2026-05-17-bielik-11b-v30-tp1-sanity|11B v3.0 base TP=1 sanity]], [[2026-05-17-bielik-11b-v30-tp2-sanity|11B v3.0 base TP=2 sanity]], [[navimed-umb]], [[broncho-nome]], [[capno-nome]]

## §1 — Methodological humility (Lerchner 2026, METHODOLOGY §8)

> We measure inference *throughput*, *latency*, *thermal envelope*, and *power efficiency* under varying concurrent load. We do not measure model quality, reasoning capability, factual accuracy, or downstream clinical utility. Following Lerchner (2026), these are extrinsic computational properties of the inference vehicle, not constitutive properties of cognition. Our claims terminate at the hardware-software interface.

Tutaj konkretnie: weryfikujemy że stack `vllm 0.19.0+rocm721 / torch 2.10 / ROCm 7.2` ładuje **Bielik-PL 11B v3.0 Instruct BF16** (Polish-focused fine-tune, distinct from multilingual base) w trybie OpenAI-compatible serve, oraz że pojedyncza inferencja end-to-end przechodzi przez HTTP POST. Treść odpowiedzi modelu jest **smoke testem pipeline'u**, NIE oceną poprawności klinicznej (§8 — *throughput is not capability*).

## §2 — Cel testu

Sprawdzić, że Bielik-PL 11B v3.0 Instruct (BF16, 21 GiB, 5 safetensors shards) ładuje się na pojedynczym R9700 przy `gpu_memory_utilization=0.9`, `max_model_len=8192`, `enforce_eager=True`, oraz że `vllm serve` udostępnia działający OpenAI-compatible endpoint. Wprowadzenie tego wariantu do portfolio uzupełnia parę "polish-focused vs multilingual-base" przy tej samej skali (11B) — istotne dla późniejszej Phase 2 cross-model analizy.

## §3 — Konfiguracja

| Parametr | Wartość |
|---|---|
| Model | `speakleash/Bielik-PL-11B-v3.0-Instruct` |
| Lokalna ścieżka | `/home/mozarcik/models/bielik-pl-11b-v30-instruct` (21 GiB, 5 shards BF16) |
| Wariant | Polish-focused fine-tune (vs base `speakleash/Bielik-11B-v3.0`, multilingual ~32 lang) |
| Transport | `vllm serve` + curl POST `/v1/chat/completions` |
| `tensor_parallel_size` | 1 |
| `max_model_len` | 8192 |
| `gpu_memory_utilization` | 0.90 |
| `enforce_eager` | True |
| `dtype` | bfloat16 |
| Port | 8100 (port 8000 dalej zajęty przez ai-dashboard) |
| Test prompt | `Wyjaśnij krótko czym jest PEEP w wentylacji mechanicznej.` |
| `max_tokens` | 128 |
| `temperature` | 0.7 |

`enforce_eager=True` jako konserwatywny default dla całego suite NaviMed-UMB na gfx1201 (METHODOLOGY §3.2). Architektura identyczna jak base 11B (LlamaForCausalLM resolution per vLLM, dense attention) — KV geometry oczekiwana zgodna z base.

## §4 — Stack (causal closure, METHODOLOGY §3.3)

| Layer | Version |
|---|---|
| ROCm SMI | 4.0.0+fc0010cf6a (ROCM-SMI-LIB 7.8.0) |
| vLLM | 0.19.0+rocm721 |
| PyTorch | 2.10.0+git8514f05 |
| `torch.version.hip` | 7.2.53211 |
| GPU | 2× AMD Radeon AI PRO R9700 (gfx1201, 32 GiB GDDR6) |

Mandatory env vars (§3.1) — wszystkie 5 obecne w JSON record:

```bash
unset PYTORCH_ALLOC_CONF
export VLLM_ROCM_USE_AITER=0
export AMD_SERIALIZE_KERNEL=1
export HIP_LAUNCH_BLOCKING=1
export ROCR_VISIBLE_DEVICES=0,1
```

Załadowane przez `scripts/_env.sh` (single source of truth post-2026-05-17 refactor).

## §5 — Wynik: **PASS**

| Metric | Value | Źródło |
|---|---|---|
| `loaded` | True | vllm engine + `/v1/models` 200 OK |
| `load_time_sec` (wall, start→ready) | **20** | banner timestamp 06:26:57 → "Application startup complete" 06:27:17 (CEST/+0200; UTC 04:26:57Z → 04:27:17Z) |
| Weights load (worker report) | 10.81 s (safetensors) / 10.955 s total | `default_loader.py:384`, `gpu_model_runner.py:4820` |
| Model footprint (worker report) | **20.89 GiB** | `gpu_model_runner.py:4820` |
| `vram_used_gb` per GPU (rocm-smi) | `[28.69, 0.056]` GiB | `rocm-smi --showmeminfo vram --csv` post-load |
| KV cache available | 7.18 GiB | `gpu_worker.py:436` |
| `kv_cache_size_tokens` | **37 616** | `kv_cache_utils.py:1319` |
| `max_concurrency` (8192-tok req) | **4.59×** | `kv_cache_utils.py:1324` |
| `init engine` (profile + KV + warmup) | 1.95 s | `core.py:283` |
| Sanity response time (curl end-to-end) | **6.97 s** dla 128 tokens | `date +%s.%N` wokół curl POST |
| vLLM engine avg generation throughput | [EMBARGOED §11.3] | `loggers.py:259` (window 06:27:57) |
| vLLM engine avg prompt throughput | [EMBARGOED §11.3] | tamże |
| `finish_reason` | `length` (cap na 128) | API response `choices[0]` |
| `errors` | `[]` | — |

`gpu_cache_size_bytes` nadal nie wystawione przez introspection path vLLM 0.19 (jak w prior records) — token-level metric wystarcza dla envelope characterization.

VRAM card1 = 0.056 GiB potwierdza, że TP=1 trzyma cały model na card0; sharding TP=2 dla Bielik-PL 11B do osobnego sanity (zalecane jako follow-up).

**Cross-model comparison (TP=1, BF16, identical config, identical prompt):**

| Model | Load time | VRAM (GPU0) | Model footprint | KV tokens | Max conc. | Sanity response time (128 tok) | Engine avg gen |
|---|---|---|---|---|---|---|---|
| bielik-4.5b-v30 | (4.5B prior) | — | smaller | larger | 5.65× | — | — |
| bielik-11b-v30 (base, multilingual) | 27 s | 28.88 GiB | 20.90 GiB | 37 584 | 4.59× | 8.66 s | [EMBARGOED §11.3] |
| **bielik-pl-11b-v30 (Polish FT)** | **20 s** | **28.69 GiB** | **20.89 GiB** | **37 616** | **4.59×** | **6.97 s** | **[EMBARGOED §11.3]** |

KV geometry praktycznie identyczna (37 584 vs 37 616 tokens, różnica < 0.1%) — potwierdza że Polish-focused fine-tune zachowuje architekturę i config tokenizera w sposób transparentny dla envelope. Load time 20 s vs 27 s — różnica prawdopodobnie wynika z page cache (drugie ładowanie tych samych safetensors po 11B base w tej samej sesji), NIE z różnic wagowych — NIE klasyfikować jako "Bielik-PL jest szybszy w loading" bez powtórzonego pomiaru cold-cache.

## §6 — Sanity response (verbatim, §8 — NO commentary on quality)

```
PEEP (ang. Positive End-Expiratory Pressure) to dodatnie ciśnienie w drogach
oddechowych podczas wydechu, stosowane w wentylacji mechanicznej. Jego głównym
celem jest zapobieganie zapadaniu się pęcherzyków płucnych (atelektazom) podczas
wydechu, co jest szczególnie ważne u pacjentów z chorobami płuc, takimi jak ARDS
(ostra niewydolność oddechowa) czy po operacjach.

PEEP pomaga utrzymać pęcherzyki płucne otwarte, co poprawia wymianę gazową
i zwiększa efektywność wentylacji. Wartość PEEP jest dostosowywana
indywidualnie dla każdego
```

Truncated mid-word "każdego" pełnym tokenem przed `finish_reason=length`, max_tokens=128 reached.

Pipeline produkuje tokeny w expected JSON format przez OpenAI-compatible endpoint. **Twierdzenia o poprawności medycznej są poza zakresem tej metodologii** (§8).

[Nota epistemiczna *poza* protokołem pomiarowym, dla NaviMed Arena tracking: model rozwinął akronim poprawnie ("Positive End-Expiratory Pressure") + dodał klinicznie spójny kontekst (ARDS, atelektaza, wymiana gazowa). Cross-model PEEP capability table:

| Model | PEEP expansion | Verdict |
|---|---|---|
| Bielik 4.5B v3.0 | "Pressure-Equalized Pathologically Elastic Alveoli" | CONFABULATED |
| Bielik 11B v3.0 (multilingual base) | "Positive End-Expiratory Pressure" | CORRECT |
| **Bielik-PL 11B v3.0 (Polish FT)** | **"Positive End-Expiratory Pressure"** | **CORRECT** |

Polish-focused fine-tune **NIE regresuje** medycznej poprawności względem multilingual base na tym pojedynczym promptcie. Obserwacja zarchiwizowana dla §9 capability assessment, **nie** zaliczana do envelope claim, **nie** do publikacji pod METHODOLOGY §11.1/§11.3 (Polish models stricter embargo).]

## §7 — AI assistance disclosure (Kim et al. 2026; METHODOLOGY §9)

| Layer | Use |
|---|---|
| **1. Dataset / data generation** | Not applicable. Sanity prompt is human-authored (Łukasz Minarowski). Model output is single smoke check, nie wchodzi w eksperymentalny dataset. |
| **2. Experimental pipeline** | Claude Code (Opus 4.7, 1M context) wykonał orkiestrację sanity testu 2026-05-18: pre-flight checks (vllm pip version, model files, port availability), launch `vllm serve` z mandatory env via `scripts/_env.sh`, curl POST + JSON parse, kill cleanup via PID. Bez modyfikacji benchmark/runner scripts ani kodu navimed-umb poza tymi 3 output files. |
| **3. Reporting** | Claude Code wygenerował JSON record, ten session log, oraz raw log copy. Wszystkie numeryczne claims weryfikowane przeciw raw vLLM log (`environment/sanity-tests/2026-05-18-bielik-pl-11b-v30-vllm-tp1-bf16.log`). |

## §8 — Issues encountered

Brak. Launch przeszedł bez ostrzeżeń. Port 8100 wolny po Phase 2 sweep z prior session (zakończony 01:16 z notification). GPU 0+1 wolne pre-launch (bge-m3 DOWN).

Jedyna operacyjna uwaga: launcher PID (`nohup ... &`) zwraca PID procesu shellowego, podczas gdy faktyczny `APIServer` process forku ma inny PID (335974 zamiast 335967). Kill na launcher PID nie zabija APIServer — wymagane `pgrep -af "vllm serve.*8100"` i kill na APIServer PID. **NIE** użyto `pkill -f` (Debug-watch forbidden pattern). Clean shutdown w ~4 s, port released.

Action item dla v0.3 runner: helper `_launch_vllm_serve.sh` powinien capturować APIServer PID (np. polling `pgrep -P <launcher_pid>` lub przez `/v1/models` 200 OK + `lsof -i:<port>`).

## §9 — Next step recommendation

1. **TP=2 envelope** dla Bielik-PL 11B BF16 — sharding na 2 GPU; sprawdzić czy `max_concurrency` rośnie i czy load_time nie regresuje (równolegle do paru bazowego 11B TP=1/TP=2).
2. **AWQ Bielik-PL 11B sanity** — jeśli wariant AWQ Polish-focused jest dostępny na HF, oczekiwane ~6 GiB footprint, większy KV cache, wyższe `max_concurrency`.
3. **Phase 2 sweep dla bielik-pl-11b-v30** — przy `max_concurrency=4.59x` i `kv_cache=37 616 tok` analogiczny N grid `{5, 10, 20, 40, 80}` jak dla base 11B; cross-model regression (Polish FT vs base) jako EMBARGO_paper_bound per §11.3.
4. **Capability observation (off-protocol, §6)** — Polish FT nie regresuje PEEP poprawności względem base 11B; data point dla [[navimed-arena]] capability assessment, **nie** publikować.
5. **kv_cache_size_gb introspection patch** — przeniesione do v0.3 runner backlog (gap konsystentny we wszystkich 4 sanity records).

## §10 — Embargo classification

- **PUBLIC engineering:** load_time, VRAM footprint, KV cache tokens, max_concurrency, sanity response time (METHODOLOGY §11.1).
- **NIE PUBLIC (out of scope tej sesji):** żadne scaling, latency P50/P95/P99, ani Phase 2 cross-model comparison numbers — to Phase 2 (§11.2, stricter embargo dla Polish models per §11.3).
- **Off-protocol capability note (§6, §9 pt 4):** flagged local-only, nie wchodzi do żadnej publicznej tabeli przed paper acceptance.
