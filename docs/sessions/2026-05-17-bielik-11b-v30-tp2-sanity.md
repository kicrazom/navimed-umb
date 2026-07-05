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
tags: [navimed-umb, phase1, envelope, bielik, polish-llm, sanity, tp2]
related:
  - "[[2026-05-17-bielik-11b-v30-tp1-sanity]]"
  - "[[2026-05-17-bielik-4.5b-v30-post-refactor-sanity]]"
  - "[[METHODOLOGY]]"
artifacts:
  - "environment/sanity-tests/2026-05-17-bielik-11b-v30-vllm-tp2-bf16.json"
  - "environment/sanity-tests/2026-05-17-bielik-11b-v30-vllm-tp2-bf16.log"
---

# Bielik 11B v3.0 — Phase 1 envelope sanity test (TP=2, BF16, vllm serve)

**Date:** 2026-05-17T20:03:00Z → 2026-05-17T20:04:53Z (UTC)
**Operator:** Łukasz Minarowski <lukasz.minarowski@umb.edu.pl>
**Methodology:** [[METHODOLOGY|METHODOLOGY.md]] v1.0 §3.1, §3.3, §5.1, §8, §9, §11
**Embargo:** **PUBLIC** (Phase 1 envelope, single sanity prompt, OpenAI-compatible transport)
**Related:** [[2026-05-17-bielik-11b-v30-tp1-sanity|TP=1 sibling sanity (same model, same session)]], [[2026-05-17-bielik-4.5b-v30-post-refactor-sanity|4.5B post-refactor sanity]], [[METHODOLOGY]]

## §1 — Methodological humility (Lerchner 2026, METHODOLOGY §8)

> We measure inference *throughput*, *latency*, *thermal envelope*, and *power efficiency* under varying concurrent load. We do not measure model quality, reasoning capability, factual accuracy, or downstream clinical utility. Following Lerchner (2026), these are extrinsic computational properties of the inference vehicle, not constitutive properties of cognition. Our claims terminate at the hardware-software interface.

Tutaj konkretnie: weryfikujemy że stack `vllm 0.19.0+rocm721 / torch 2.10 / ROCm 7.2` ładuje **Bielik 11B v3.0 BF16** z `tensor_parallel_size=2` (model sharded across both R9700) w trybie OpenAI-compatible serve, oraz że pojedyncza inferencja end-to-end przechodzi przez HTTP POST. Wszystkie numeryczne stwierdzenia są **engineering envelope per METHODOLOGY §5.1** — wartości scaling z N>1 są poza zakresem tego sanity (Phase 2 territory, §11.2).

## §2 — Cel testu

Sprawdzić, że Bielik 11B v3.0 (BF16, 21 GiB, 5 safetensors shards) shardujje się równo na 2 R9700 przy `gpu_memory_utilization=0.9`, `max_model_len=8192`, `enforce_eager=True`, oraz dostarczyć **direct A/B comparison vs TP=1 baseline** (z tej samej sesji, ten sam model, ten sam prompt — perfekcyjna kontrola dla envelope claims o efekcie tensor parallelism).

## §3 — Konfiguracja

| Parametr | Wartość |
|---|---|
| Model | `speakleash/Bielik-11B-v3.0-Instruct` |
| Lokalna ścieżka | `/home/mozarcik/models/bielik-11b-v30` (21 GiB, 5 shards BF16) |
| Transport | `vllm serve` + curl POST `/v1/chat/completions` |
| `tensor_parallel_size` | **2** (vs TP=1 baseline) |
| `max_model_len` | 8192 |
| `gpu_memory_utilization` | 0.90 |
| `enforce_eager` | True |
| `dtype` | bfloat16 |
| Port | 8101 (TP=1 użył 8100 — oba zajęte przez tę sesję / agentów) |
| Test prompt | `Wyjaśnij krótko czym jest PEEP w wentylacji mechanicznej.` (identyczny z TP=1) |
| `max_tokens` | 128 |
| `temperature` | 0.7 |

`enforce_eager=True` zachowany jako konserwatywny default dla całego suite (METHODOLOGY §3.2). Bielik (Mistral/Llama-base, dense attention) prawdopodobnie zniesie CUDA graphs, ale przed udokumentowaną walidacją używamy eager — TP=1 i TP=2 identyczna konfiguracja, więc A/B sterylne.

## §4 — Stack (causal closure, METHODOLOGY §3.3)

| Layer | Version |
|---|---|
| ROCm SMI | 4.0.0+fc0010cf6a (ROCM-SMI-LIB 7.8.0) |
| vLLM | 0.19.0+rocm721 |
| PyTorch | 2.10.0+git8514f05 |
| `torch.version.hip` | 7.2.53211 |
| GPU | 2× AMD Radeon AI PRO R9700 (gfx1201, 32 GiB GDDR6) |

Mandatory env vars (§3.1) — wszystkie 5 obecne, źródło `scripts/_env.sh`:

```bash
unset PYTORCH_ALLOC_CONF
export VLLM_ROCM_USE_AITER=0
export AMD_SERIALIZE_KERNEL=1
export HIP_LAUNCH_BLOCKING=1
export ROCR_VISIBLE_DEVICES=0,1
```

Worker config z log: `tensor_parallel_size=2, pipeline_parallel_size=1, data_parallel_size=1, world_size=2, local_world_size=2, disable_custom_all_reduce=True`.

## §5 — Wynik: **PASS** + A/B comparison vs TP=1

### 5.1 Headline A/B table (TP=1 vs TP=2, same session, same model, same prompt)

| Metric | TP=1 | TP=2 | Δ | Interpretation |
|---|---|---|---|---|
| Load time (start→ready, s) | 27 | **24** | −11% | Faster: per-worker shard load is concurrent |
| Weights load per worker (s) | 11.65 | **2.59** | −78% | Each worker loads only its half of safetensors |
| Model footprint per worker (GiB) | 20.9 | **10.46** | −50% | Clean weight split, no duplication overhead |
| VRAM card0 (GiB) | 28.88 | **31.06** | +7.6% | Higher per-card budget (more headroom for KV) |
| VRAM card1 (GiB) | 0.056 | **31.06** | +55,400% | card1 now active (was idle in TP=1) |
| Aggregate VRAM (GiB) | 28.93 | **62.12** | +115% | 2.15× total — pays for KV expansion |
| KV cache available per worker (GiB) | 7.17 | **17.55** | +145% | More memory free after halved weight footprint |
| **KV cache size (tokens)** | 37,584 | **183,968** | **+390%** | **4.90× capacity** |
| **Max concurrency (8192-tok req)** | **4.59×** | **22.46×** | **+390%** | **4.89× capacity** — matches KV ratio exactly |
| Sanity response time end-to-end (s, 128 tok) | 8.66 | **8.55** | −1.4% | Within noise — N=1 unchanged |
| Engine avg generation throughput (tok/s) | 12.8 | **7.3** | **−43%** | **Single-stream cost of TP=2** |
| Engine avg prompt throughput (tok/s) | 3.3 | 3.3 | 0% | Prefill identical (tokenization bound) |

### 5.2 Engineering envelope (TP=2, primary record)

| Metric | Value | Źródło |
|---|---|---|
| `loaded` | True | vllm engine + `/v1/models` 200 OK |
| `load_time_sec` (wall, start→ready) | **24** | banner 22:03:00 → "Application startup complete" 22:03:24; corroborated curl-poll |
| `init engine` (profile + KV + warmup) | 6.06 s | `core.py:283` (vs 2.04 s TP=1 — TP=2 init pays extra for cross-rank coord) |
| `vram_used_gb` per GPU (rocm-smi) | `[31.062, 31.062]` GiB | `rocm-smi --showmeminfo vram --csv` post-load |
| Symmetry Δ across cards | 37 KB | Sub-page noise; sharding clean |
| `kv_cache_size_tokens` | **183 968** | `kv_cache_utils.py:1319` |
| `max_concurrency` (8192-tok req) | **22.46×** | `kv_cache_utils.py:1324` |
| Sanity response time | **8.55 s** dla 128 tokens | `date +%s.%N` wokół curl POST |
| vLLM engine avg generation throughput | [EMBARGOED §11.3] | `loggers.py:259` (window 22:03:44) |
| `finish_reason` | `length` (cap na 128) | API response `choices[0]` |
| `errors` | `[]` | — |

### 5.3 A/B verdict (engineering claim)

**TP=2 quintuples KV-cache capacity and max_concurrency, at the cost of ~43% single-stream generation throughput.** Ratio match is striking: 183968/37584 = 4.90× tokens, 22.46/4.59 = 4.89× concurrency — perfect coupling.

To bezpośrednio replikuje obserwację METHODOLOGY §4 dla Qwen 7B ("TP=2 harmful below high N"). Bielik 11B BF16 pokazuje **ten sam wzorzec przy tym samym progu architekturalnym** (gęsta uwaga Llama/Mistral-base, fp16-class weights). Konsekwencja operacyjna: dla **single-request latency** (CDSS interaktywny, jeden klinicysta) TP=1 wygrywa. Dla **batch / queue** (N > ~3 jednoczesnych żądań, np. wsadowe przetwarzanie serii badań) TP=2 zaczyna wygrywać przez wyższą capacity.

Phase 2 sweep zmierzy *concrete crossover N* (EMBARGOED per §11.2).

## §6 — Sanity response (verbatim, §8 — NO quality commentary)

```
PEEP (ang. Positive End-Expiratory Pressure), czyli dodatnie ciśnienie końcowo-wydechowe,
to technika stosowana w wentylacji mechanicznej, mająca na celu utrzymanie otwartych
pęcherzyków płucnych podczas wydechu. PEEP jest stosowany w celu zapobiegania zapadaniu
się pęcherzyków płucnych (atelektazji) i poprawy wymiany gazowej u pacj
```

**Byte-for-byte identyczna z TP=1.** Truncated mid-word "pacj…" — `finish_reason=length`, max_tokens=128 reached. Pipeline produkuje tokeny w expected JSON format. **Twierdzenia o poprawności medycznej są poza zakresem tej metodologii** (§8). [Off-protocol nota: rozwinięcie akronimu "Positive End-Expiratory Pressure" zgodne z konwencją kliniczną, identyczne z TP=1 — sanity check że TP=2 nie wprowadza output corruption. Halucynacja-watch: PASS (zgodność z [[2026-05-17-bielik-11b-v30-tp1-sanity|TP=1 baseline]]).]

## §7 — AI assistance disclosure (Kim et al. 2026; METHODOLOGY §9)

| Layer | Use |
|---|---|
| **1. Dataset / data generation** | Not applicable. Sanity prompt is human-authored (Łukasz Minarowski) — identyczny z TP=1 dla A/B sterylności. Model output is single smoke check, nie wchodzi w eksperymentalny dataset. |
| **2. Experimental pipeline** | Claude Code (Opus 4.7, 1M context) jako subagent w Łukasz-orchestrated session wykonał: pre-flight checks (rocm-smi GPU 0+1 free, ports 8101/8100/8000 status), launch `vllm serve --tensor-parallel-size 2` z mandatory env via `scripts/_env.sh`, curl POST + JSON parse, kill cleanup (vide §8 issue 1 — wymagało dwóch kroków). Bez modyfikacji benchmark/runner scripts ani kodu navimed-umb poza tymi 3 output files. |
| **3. Reporting** | Claude Code wygenerował JSON record (z embedded `comparison_tp1_baseline` block), ten session log z explicit A/B table, oraz raw log copy. Wszystkie numeryczne claims weryfikowane przeciw raw vLLM log (`environment/sanity-tests/2026-05-17-bielik-11b-v30-vllm-tp2-bf16.log`). |

## §8 — Issues encountered

1. **Kill discipline gotcha — wrapper PID ≠ vllm child PID.** `nohup vllm serve ... &` w bash -c spawnuje vllm jako odłączone dziecko (przez nohup); `$!` zwraca PID bash-wrappera, nie vllm-a. SIGTERM do wrappera nie propagował do APIServer/EngineCore/Worker_TP{0,1}. Workaround: dodatkowy `kill <APIServer_pid>` po identyfikacji przez `pgrep -af "vllm serve"`. Clean shutdown <1s po właściwym kill (Engine + worker shutdown messages w log:84-93). Action item: v0.3 sanity runner musi po launch sondować rzeczywisty vllm pid (`pgrep -f 'vllm serve.*--port 8101'`) i zapisać go w pidfile zamiast `$!`. **NIE używano `pkill -f`** — per Debug-watch collateral kill risk; precyzyjny PID-based kill tylko.
2. **`--disable-log-requests` znów flagged jako deprecated** — task spec nie zawierała tej flagi (wzięta na poprzednim teście). Powtórzenie ostrzeżenia z TP=1 record dla downstream task templates: vllm 0.19 to dropped.
3. **iGPU card2 zajęte przez parallel agent (bge-m3, 1.46 GiB)** — bez wpływu na test (ROCR_VISIBLE_DEVICES=0,1 maskuje); zachowanie zgodne z METHODOLOGY §2 (per-GPU sampling filter by Card Series).

Brak runtime errors, brak HSA_STATUS_*, brak crash CUDA graphs (eager mode aktywny). Brak OOM na TP=2 mimo wyższego per-card footprintu (31 GiB / 32 GiB — 97% utilization, ale w obrębie `gpu_memory_utilization=0.9` budgetu po accounting dla KV).

## §9 — Next step recommendation

1. **AWQ Bielik 11B TP=1 sanity** — `speakleash/Bielik-11B-v3.0-Instruct-AWQ` (METHODOLOGY §4.2 row 10, "downloading" status — sprawdzić czy `/home/mozarcik/models/` already ma). Oczekiwane: ~6 GB footprint, KV cache > 60k tokens, max_concurrency > 8× (vs BF16 TP=1 4.59×, TP=2 22.46×). Bezpośrednie porównanie AWQ-4bit vs BF16 dla tego samego rdzenia.
2. **TP=2 with `enforce_eager=False`** — Bielik (Llama/Mistral base, dense attention) nie ma hybrydowej uwagi z §3.2 (która wymaga eager dla gfx1201). Testowy run z CUDA graphs aktywne — czy single-stream throughput odzyskuje (oczekiwany +20-40% na decode loop)? Jeśli tak, TP=2 + CUDA graphs ≈ TP=1 throughput ale z 5× max_concurrency = jednoznaczna wygrana. Jeśli HSA crash → eager pozostaje default.
3. **Phase 2 sweep dla Bielik 11B v3.0 (TP=1 vs TP=2 crossover)** — przy `max_concurrency=4.59x` (TP=1) i `22.46x` (TP=2) zaplanować N grid `{1, 2, 4, 8, 16, 32, 64, 128}` dla obu konfiguracji. Knee TP=1 oczekiwany ~N=18-20, knee TP=2 ~N=90-100. Crossover (gdzie agregat tok/s TP=2 ≥ TP=1) prawdopodobnie ~N=3-5 (gdy preempcja TP=1 zaczyna boleć). EMBARGOED per §11.2.
4. **`kv_cache_size_gb` introspection patch** (powtórka z TP=1 §9) — vLLM 0.19 nie wystawia `gpu_cache_size_bytes`; v0.3 runner powinien dokomponować z `kv_cache_geometry × num_layers × dtype_bytes`.
5. **Halucynacja-watch confirmation** — TP=2 output byte-identical z TP=1 dla PEEP — żadne TP-parallel corruption / numerical drift w środowisku gfx1201 / dual-R9700. Dla downstream klinicznego inference to istotny sanity (asymmetric risk medical, METHODOLOGY §11.3).

## §10 — Embargo classification

- **PUBLIC engineering:** load_time, VRAM footprint per GPU, KV cache tokens, max_concurrency, sanity response time, A/B ratio claims (4.89× concurrency, −43% single-stream throughput TP=2 vs TP=1). Per METHODOLOGY §11.1 (envelope + workarounds + sanity throughput + knee-position observations).
- **NIE PUBLIC (out of scope tej sesji):** żadne Phase 2 scaling numbers, latency P50/P95/P99, ani concrete crossover N — to §11.2.
- **Stricter embargo dla Polish models (§11.3):** wartości tutaj (TP=1, TP=2 envelope) są PUBLIC bo to engineering envelope, ale wszelkie Phase 2 throughput@N dla Bielika pozostają local-only do paper acceptance.
- **Off-protocol capability note (§6):** byte-identical TP=1↔TP=2 output dla PEEP — flagged dla [[navimed-arena]] capability assessment, nie do publikacji pod METHODOLOGY §11.1.
