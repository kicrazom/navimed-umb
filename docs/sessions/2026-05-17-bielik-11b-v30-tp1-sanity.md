---
type: session
model: bielik-11b-v30
phase: 1_envelope
embargo: PUBLIC
parent: "[[METHODOLOGY|METHODOLOGY.md]]"
date: 2026-05-17
operator: Łukasz Minarowski
methodology_version: 1.0
transport: vllm-serve-openai-api
tags: [navimed-umb, phase1, envelope, bielik, polish-llm, sanity]
related:
  - "[[2026-05-17-bielik-4.5b-v30-post-refactor-sanity]]"
  - "[[METHODOLOGY]]"
artifacts:
  - "environment/sanity-tests/2026-05-17-bielik-11b-v30-vllm-tp1-bf16.json"
  - "environment/sanity-tests/2026-05-17-bielik-11b-v30-vllm-tp1-bf16.log"
---

# Bielik 11B v3.0 — Phase 1 envelope sanity test (TP=1, BF16, vllm serve)

**Date:** 2026-05-17T19:53:52Z → 2026-05-17T19:55:18Z (UTC)
**Operator:** Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>
**Methodology:** [[METHODOLOGY|METHODOLOGY.md]] v1.0 §3.1, §3.3, §5.1, §8, §9, §11
**Embargo:** **PUBLIC** (Phase 1 envelope, single sanity prompt, OpenAI-compatible transport)
**Related:** [[2026-05-17-bielik-4.5b-v30-post-refactor-sanity|4.5B sibling sanity (same session, lighter model)]], [[navimed-umb]], [[broncho-nome]], [[capno-nome]]

## §1 — Methodological humility (Lerchner 2026, METHODOLOGY §8)

> We measure inference *throughput*, *latency*, *thermal envelope*, and *power efficiency* under varying concurrent load. We do not measure model quality, reasoning capability, factual accuracy, or downstream clinical utility. Following Lerchner (2026), these are extrinsic computational properties of the inference vehicle, not constitutive properties of cognition. Our claims terminate at the hardware-software interface.

Tutaj konkretnie: weryfikujemy że stack `vllm 0.19.0+rocm721 / torch 2.10 / ROCm 7.2` ładuje **Bielik 11B v3.0 BF16** w trybie OpenAI-compatible serve, oraz że pojedyncza inferencja end-to-end przechodzi przez HTTP POST. Treść odpowiedzi modelu jest **smoke testem pipeline'u**, NIE oceną poprawności klinicznej (§8 — *throughput is not capability*).

## §2 — Cel testu

Sprawdzić, że Bielik 11B v3.0 (BF16, 21 GB, 5 safetensors shards) ładuje się na pojedynczym R9700 przy `gpu_memory_utilization=0.9`, `max_model_len=8192`, `enforce_eager=True`, oraz że `vllm serve` udostępnia działający OpenAI-compatible endpoint dla chat completions.

## §3 — Konfiguracja

| Parametr | Wartość |
|---|---|
| Model | `speakleash/Bielik-11B-v3.0-Instruct` |
| Lokalna ścieżka | `/home/mozarcik/models/bielik-11b-v30` (21 GiB, 5 shards BF16) |
| Transport | `vllm serve` + curl POST `/v1/chat/completions` |
| `tensor_parallel_size` | 1 |
| `max_model_len` | 8192 |
| `gpu_memory_utilization` | 0.90 |
| `enforce_eager` | True |
| `dtype` | bfloat16 |
| Port | 8100 (vide §8 — port 8000 zajęty przez ai-dashboard) |
| Test prompt | `Wyjaśnij krótko czym jest PEEP w wentylacji mechanicznej.` |
| `max_tokens` | 128 |
| `temperature` | 0.7 |

`enforce_eager=True` jako konserwatywny default dla całego suite NaviMed-UMB na gfx1201 (METHODOLOGY §3.2) — Bielik (Mistral-base, dense attention) prawdopodobnie zniesie CUDA graphs, ale przed udokumentowaną walidacją używamy eager.

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
| `load_time_sec` (wall, start→ready) | **27** | banner timestamp 21:53:58 → "Application startup complete" 21:54:25; potwierdzone curl-poll |
| Weights load (worker report) | 11.65 s (safetensors) / 11.81 s total | `default_loader.py:384`, `gpu_model_runner.py:4820` |
| Model footprint (worker report) | **20.9 GiB** | `gpu_model_runner.py:4820` |
| `vram_used_gb` per GPU (rocm-smi) | `[28.877, 0.056]` GiB | `rocm-smi --showmeminfo vram --csv` post-load |
| KV cache available | 7.17 GiB | `gpu_worker.py:436` |
| `kv_cache_size_tokens` | **37 584** | `kv_cache_utils.py:1319` |
| `max_concurrency` (8192-tok req) | **4.59×** | `kv_cache_utils.py:1324` |
| `init engine` (profile + KV + warmup) | 2.04 s | `core.py:283` |
| Sanity response time (curl end-to-end) | **8.66 s** dla 128 tokens | `date +%s.%N` wokół curl POST |
| vLLM engine avg generation throughput | [EMBARGOED §11.3] | `loggers.py:259` (window 21:54:45) |
| vLLM engine avg prompt throughput | [EMBARGOED §11.3] | tamże |
| `finish_reason` | `length` (cap na 128) | API response `choices[0]` |
| `errors` | `[]` | — |

`gpu_cache_size_bytes` nadal nie wystawione przez introspection path vLLM 0.19 (analogicznie do 4.5B record) — token-level metric (37 584) wystarcza dla envelope characterization, GB-level do uzupełnienia w v0.3 runner.

VRAM card1 = 0.056 GiB potwierdza, że TP=1 trzyma cały model na card0; sharding TP=2 dla 11B testowany osobno (nie tym sanity).

## §6 — Sanity response (verbatim, §8 — NO commentary on quality)

```
PEEP (ang. Positive End-Expiratory Pressure), czyli dodatnie ciśnienie końcowo-wydechowe,
to technika stosowana w wentylacji mechanicznej, mająca na celu utrzymanie otwartych
pęcherzyków płucnych podczas wydechu. PEEP jest stosowany w celu zapobiegania zapadaniu
się pęcherzyków płucnych (atelektazji) i poprawy wymiany gazowej u pacj
```

Truncated mid-word "pacj…" — `finish_reason=length`, max_tokens=128 reached.

Pipeline produkuje tokeny w expected JSON format przez OpenAI-compatible endpoint. **Twierdzenia o poprawności medycznej są poza zakresem tej metodologii** (§8). [Nota epistemiczna *poza* protokołem pomiarowym — model rozwinął akronim spójnie z konwencją kliniczną; 4.5B w siostrzanym teście rozwinął błędnie ("Pressure-Equalized Pathologically Elastic Alveoli"). Obserwacja zarchiwizowana dla §9 capability assessment, **nie** zaliczana do envelope claim.]

## §7 — AI assistance disclosure (Kim et al. 2026; METHODOLOGY §9)

| Layer | Use |
|---|---|
| **1. Dataset / data generation** | Not applicable. Sanity prompt is human-authored (Łukasz Minarowski). Model output is single smoke check, nie wchodzi w eksperymentalny dataset. |
| **2. Experimental pipeline** | Claude Code (Opus 4.7, 1M context) wykonał orkiestrację sanity testu 2026-05-17: pre-flight checks (rocm-smi, vllm pip version, port availability), launch `vllm serve` z mandatory env via `scripts/_env.sh`, curl POST + JSON parse, kill cleanup via PID file. Bez modyfikacji benchmark/runner scripts ani kodu navimed-umb poza tymi 3 output files. |
| **3. Reporting** | Claude Code wygenerował JSON record, ten session log, oraz raw log copy. Wszystkie numeryczne claims weryfikowane przeciw raw vLLM log (`environment/sanity-tests/2026-05-17-bielik-11b-v30-vllm-tp1-bf16.log`). |

## §8 — Issues encountered

1. **Flag `--disable-log-requests` zdropped w vllm 0.19** — pierwsza próba launch zwróciła `vllm: error: unrecognized arguments: --disable-log-requests`. Retry bez flagi przeszedł. Action item: usunąć tę flagę z dokumentacji / task templates dla v0.3 sweep.
2. **Port :8000 occupied** — długo działający `ai-dashboard` server Łukasza (pid 2554, ~9h uptime) trzymał port. Test relocated na port `:8100`, dashboard nie tknięty. Operacyjne: jeśli planujemy regularne sanity runs, należy ustalić dedykowany port lub mieć skrypt sondujący wolny port przed launch.
3. **Kill discipline** — użyto wyłącznie `kill <PID>` z pidfile `/tmp/bielik-11b-v30.pid`, **NIE** `pkill -f` (per Debug-watch finding o collateral kill risk). Clean SIGTERM exit w 2 s, bez SIGKILL.

Brak runtime errors, brak HSA_STATUS_*, brak crash CUDA graphs (eager mode aktywny).

## §9 — Next step recommendation

1. **TP=2 envelope** dla Bielik 11B BF16 — sharding na 2 GPU; sprawdzić czy `max_concurrency` rośnie i czy load_time nie regresuje (TP=2 jest harmful below high N per METHODOLOGY §4 footnote dla Qwen 7B; trzeba zmierzyć dla Bielika).
2. **AWQ Bielik 11B sanity** — `speakleash/Bielik-11B-v3.0-Instruct-AWQ` (jeśli dostępny lokalnie po background download z 4.5B sesji) — TP=1, oczekiwane ~6 GB footprint, większy KV cache, wyższe `max_concurrency`.
3. **kv_cache_size_gb introspection patch** — w v0.3 runner dodać kompozycję `kv_cache_geometry × num_layers × dtype_bytes` skoro vLLM 0.19 nie wystawia `gpu_cache_size_bytes` przez `loggers`.
4. **Capability observation (off-protocol)** — Bielik 11B rozwinął PEEP poprawnie, 4.5B z błędem. To **nie** envelope claim, ale dane do późniejszego [[navimed-arena]] capability assessment — flagged for tracking, nie do publikacji pod METHODOLOGY §11.1.
5. **Phase 2 sweep dla bielik-11b-v30** — przy `max_concurrency=4.59x` i `kv_cache=37 584 tok` można zaplanować N grid `{5, 10, 20, 40, 80}` (knee oczekiwany przy N≈18-20 = 4.59 × max_num_seqs ratio); zakres > 80 będzie głównie preemption regime.

## §10 — Embargo classification

- **PUBLIC engineering:** load_time, VRAM footprint, KV cache tokens, max_concurrency, sanity response time (METHODOLOGY §11.1).
- **NIE PUBLIC (out of scope tej sesji):** żadne scaling, latency P50/P95/P99, ani cross-model comparison numbers — to Phase 2 (§11.2, stricter embargo dla Polish models per §11.3).
- **Off-protocol capability note (§9 pt 4):** flagged local-only, nie wchodzi do żadnej publicznej tabeli przed paper acceptance.
