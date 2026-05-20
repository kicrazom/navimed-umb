---
parent: "[[10_Projekty/navimed-umb/NaviMed_UMB_index|navimed-umb]]"
date: 2026-05-19
test_type: sanity
model: speakleash/Bielik-PL-11B-v3.0-Instruct
tensor_parallel: 2
verdict: PASS
---

# Sanity test — Bielik-PL 11B v3.0 Instruct, TP=2 BF16 (2026-05-19)

Drugi sanity test dla Bielik-PL 11B v3.0 (Polish-focused fine-tune, model suite #11)
— wariant TP=2, sharding na 2× R9700. Realizacja punktu #1 z §9 "Next step
recommendation" lab loga TP=1 (2026-05-18). Para TP=1/TP=2 dla Bielik-PL domyka
envelope odpowiadający parze base 11B TP=1/TP=2 (2026-05-17).

## §1 — Cel

Sprawdzić, że Bielik-PL 11B v3.0 Instruct (BF16) shardowany na 2 GPU (`tensor_parallel_size=2`)
ładuje się poprawnie, że `max_concurrency` rośnie względem TP=1 dzięki uwolnionej
pamięci KV, oraz że `load_time` nie regresuje patologicznie. Sanity = engineering
envelope, nie pomiar wydajnościowy Phase 2.

## §2 — Konfiguracja

| Parametr | Wartość |
|---|---|
| Model | `speakleash/Bielik-PL-11B-v3.0-Instruct` (suite #11) |
| Lokalna ścieżka | `/home/mozarcik/models/bielik-pl-11b-v30-instruct` (5 shards BF16) |
| GPU | 2× AMD Radeon AI PRO R9700 (gfx1201, 32 GiB GDDR6) |
| vLLM | 0.19.0 (pinned 0.19+rocm721) |
| `tensor_parallel_size` | 2 |
| `dtype` | bfloat16 |
| `max_model_len` | 8192 |
| `gpu_memory_utilization` | 0.9 |
| `enforce_eager` | True (suite-wide konserwatywny default, METHODOLOGY §3.2) |
| Port | 8100 |
| Env | `scripts/_env.sh` (ROCR_VISIBLE_DEVICES=0,1, VLLM_ROCM_USE_AITER=0) |

## §3 — Pre-flight

| Check | Wynik |
|---|---|
| vLLM version | 0.19.0 ✓ |
| Model files | config.json + model-0000{1..5}-of-00005.safetensors ✓ |
| GPU count | 3 widoczne (GPU[0]+[1] = R9700 discrete, GPU[2] = iGPU pominięty przez `_env.sh`) ✓ |
| Port 8100 | wolny ✓ |
| GPU baseline | GPU[0]/[1] ~59 MB used (czyste) ✓ |
| Download w tle | `huggingface-cli` Qwen3.6-35B-A3B-FP8 — network/disk I/O, NIE dotyka GPU; brak kolizji ✓ |

## §4 — Launch + metryki

```
vllm serve ~/models/bielik-pl-11b-v30-instruct \
  --tensor-parallel-size 2 --port 8100 \
  --max-model-len 8192 --gpu-memory-utilization 0.9 \
  --enforce-eager --dtype bfloat16 \
  --served-model-name bielik-pl-11b-v30-instruct
```

| Metryka | Wartość | Źródło (raw log) |
|---|---|---|
| `load_weights_sec` | **8.70 s** | `default_loader.py:384` |
| `model_loading_sec` | **8.89 s** | `gpu_model_runner.py:4820` |
| Model footprint (per worker/shard) | **10.46 GiB** | `gpu_model_runner.py:4820` (Worker_TP0) |
| Available KV cache | **17.55 GiB** | `gpu_worker.py:436` |
| GPU KV cache size | **183 968 tokens** | `kv_cache_utils.py:1319` |
| `max_concurrency` (8192-tok req) | **22.46×** | `kv_cache_utils.py:1324` |
| `init engine` (profile+kv+warmup) | **6.75 s** | `core.py:283` |
| Sanity response time (curl e2e) | **8.18 s** dla 128 tokens | `date +%s.%N` wokół curl POST |

Raw log: `environment/sanity-tests/2026-05-19-bielik-pl-11b-v30-vllm-tp2-bf16.log` (92 linie, ze shutdown).

## §5 — Wynik

**Verdict: PASS.** Model załadował się czysto na 2 GPU, OpenAI-compatible endpoint
działał, sanity prompt zwrócił poprawną odpowiedź, clean shutdown. Sanity prompt:
*"Rozwiń skrót PEEP w kontekście wentylacji mechanicznej i wyjaśnij jego rolę."*
(PL, kliniczny, `max_tokens=128`, `temperature=0.7`). Usage: 32 prompt + 128
completion = 160 total tokens.

## §6 — TP=1 → TP=2 regression + capability note

### Regression (engineering envelope, PUBLIC §11.1)

| Metryka | TP=1 (2026-05-18) | TP=2 (2026-05-19) | Zmiana |
|---|---|---|---|
| Model footprint | 20.89 GiB (cały na 1 GPU) | 10.46 GiB / shard | sharded ~½ per card |
| Available KV cache | 7.18 GiB | 17.55 GiB | +144% |
| KV cache tokens | 37 616 | 183 968 | **+389% (~4.9×)** |
| `max_concurrency` (8192 tok) | 4.59× | **22.46×** | **~4.9×** |
| Sanity response (128 tok) | 6.97 s | 8.18 s | +1.21 s (TP=2 single-request overhead) |

TP=2 sharding uwalnia dramatycznie pamięć KV — `max_concurrency` rośnie ~4.9×
(4.59× → 22.46×), bo model footprint jest dzielony między karty, zostawiając
znacznie więcej VRAM na KV cache. Response time pojedynczego requestu rośnie
(+1.21 s) — komunikacja tensor-parallel kosztuje dla single request; spójne z
METHODOLOGY "TP=2 harmful below high N". Korzyść TP=2 jest concurrency-side, nie
single-request-latency-side.

`load_weights` 8.70 s (TP=2) vs `load_time` 20 s wall (TP=1, banner→ready) —
**NIE porównywać wprost**: różne metryki (model-loading-only vs full wall-clock),
plus page cache (te same safetensors ładowane wielokrotnie tej samej sesji).
Cold-cache load nie był mierzony.

### Capability observation (off-protocol, §11 NIE publikować)

[Nota *poza* protokołem pomiarowym — dla [[navimed-arena]] capability tracking:
model rozwinął akronim PEEP poprawnie po angielsku ("**Positive End-Expiratory
Pressure**") + spójny kontekst kliniczny (zapobieganie zapadaniu pęcherzyków).
**ALE** polskie tłumaczenie skonfabulowane: "Dodatnie Ciśnienie **Kościóło**-Wydechowe"
— poprawnie powinno być "końcowo-wydechowe". EN expansion correct, PL translation
błędna.

Cross-model PEEP table (kumulatywnie):

| Model | PEEP (EN) | PEEP (PL translation) | Verdict |
|---|---|---|---|
| Bielik 4.5B v3.0 | "Pressure-Equalized..." | — | CONFABULATED |
| Bielik 11B v3.0 (multilingual base) | "Positive End-Expiratory Pressure" | — | CORRECT |
| Bielik-PL 11B v3.0 TP=1 (2026-05-18) | "Positive End-Expiratory Pressure" | — | CORRECT |
| **Bielik-PL 11B v3.0 TP=2 (2026-05-19)** | **"Positive End-Expiratory Pressure"** | **"Kościóło-Wydechowe"** | **EN OK, PL confab** |

EN expansion stabilna across runs; polskie tłumaczenie akronimu jest niestabilne
nawet w Polish-focused fine-tune. Data point dla §9 capability assessment, **NIE**
zaliczane do envelope claim, **NIE** do publikacji per METHODOLOGY §11.3.]

## §7 — AI assistance disclosure (Kim et al. 2026; METHODOLOGY §9)

| Layer | Use |
|---|---|
| **1. Dataset / data generation** | Not applicable. Sanity prompt human-authored (Łukasz Minarowski). Output to single smoke check, nie wchodzi w eksperymentalny dataset. |
| **2. Experimental pipeline** | Claude Code (Opus 4.7, 1M context) wykonał orkiestrację 2026-05-19: pre-flight (vllm version, model files, port, GPU baseline), launch `vllm serve` TP=2 z env via `scripts/_env.sh`, readiness poll na `/v1/models`, curl POST + JSON parse, targeted kill APIServer PID. Bez modyfikacji benchmark/runner scripts ani kodu navimed-umb poza 3 output files. |
| **3. Reporting** | Claude Code wygenerował JSON record, ten lab log, raw vLLM log copy. Numeryczne claims weryfikowane przeciw raw log (`environment/sanity-tests/2026-05-19-bielik-pl-11b-v30-vllm-tp2-bf16.log`). |

## §8 — Issues encountered

Launch przeszedł bez ostrzeżeń. Port 8100 wolny pre-launch, GPU 0+1 czyste.
Readiness ~5 s od poll-startu (model load + warmup zakończone szybko).

Operacyjna uwaga (konsystentna z §8 TP=1 loga): launcher PID (`nohup ... &`)
≠ APIServer fork PID. Faktyczny APIServer = PID 32968; kill na konkretny PID,
**NIE** `pkill -f` (Debug-watch forbidden pattern). Clean shutdown potwierdzony
w raw log (`Application shutdown complete`, `Finished server process`).

Bash-orchestration gotcha: `LOG=...&& nohup vllm ... &` — operator `&` zbindował
całą AND-listę do subshella, więc zmienna `LOG` nie persystowała do foreground
shell. Workaround: literalna ścieżka logu w kolejnych komendach. Bez wpływu na
test (vLLM pisał do właściwego pliku z subshella).

## §9 — Next step recommendation

1. **AWQ Bielik-PL 11B sanity** — jeśli wariant AWQ Polish-focused dostępny na HF;
   oczekiwane mniejsze footprint, większy KV cache, wyższe `max_concurrency`.
2. **Phase 2 sweep dla bielik-pl-11b-v30** — envelope TP=1/TP=2 kompletny; sweep
   przy `max_concurrency` 4.59× (TP=1) / 22.46× (TP=2), N grid jak dla base 11B;
   cross-model regression (Polish FT vs multilingual base) jako EMBARGO_paper_bound
   per §11.3.
3. **Qwen3.6-35B-A3B-FP8** — po zakończeniu downloadu (§4.6 follow-up, MoE) →
   sanity TP=2 z `--enforce-eager` per `sweep_phase2_v0.3.sh` phase-b.
4. **Capability (off-protocol, §6)** — niestabilność polskiego tłumaczenia
   akronimu PEEP w Polish FT — data point dla [[navimed-arena]], NIE publikować.
5. **kv_cache_size_gb introspection patch** — backlog v0.3 runner (gap konsystentny).

## §10 — Embargo classification

- **PUBLIC engineering (METHODOLOGY §11.1):** load_weights, model footprint per
  worker, available KV cache, KV cache tokens, max_concurrency, sanity response time.
- **NIE PUBLIC:** żadne Phase 2 scaling, latency P50/P95/P99, cross-model comparison
  numbers — to Phase 2 (§11.2, stricter embargo dla Polish models per §11.3).
- **Off-protocol capability note (§6):** flagged local-only, NIE do publicznej
  tabeli przed paper acceptance.

---

Cross-ref: [[2026-05-18-bielik-pl-11b-v30-tp1-sanity]] (para TP=1),
[[2026-05-17-bielik-11b-v30-tp2-sanity]] (base 11B TP=2).
