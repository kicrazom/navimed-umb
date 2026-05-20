---
parent: "[[10_Projekty/navimed-umb/NaviMed_UMB_index|navimed-umb]]"
date: 2026-05-20
type: recovery-plan
status: active
---

# Recovery Plan — batch sanity v0.3 + transformers/stack naprawa (2026-05-20)

## Kontekst

Batch sanity v0.3 (14 modeli, 2026-05-20 01:05) wykonał się autonomicznie
(exit 0) — **3 PASS / 11 FAIL**. Diagnoza wykazała że FAIL-e mają rozłączne
przyczyny: 5× fizyczny OOM, 1× model nie pobrany, 1× false-fail, 2× model/
tokenizer issue, 1× anomalia katalogu. To NIE awaria autonomii — batch
zadziałał; ujawnił błędy planu suite + limity sprzętowe + niezgodności stacku.

### Wyniki batcha

| Model | Wynik | Przyczyna |
|---|---|---|
| bielik-11b-v23-awq | PASS | load 6.1s, KV 110 880, maxc 13.5× |
| llama-pllum-8b-instruct | PASS | load 9.8s, KV 104 256, maxc 12.7× |
| pllum-12b-chat | PASS | load 13.2s, KV 31 824, maxc 3.9× |
| llama-pllum-70b ×5 | FAIL | HIP OOM — ~132 GB BF16 > 64 GB VRAM |
| kimi-dev-72b | FAIL | model nie pobrany (2.4 MB) + wymaga AWQ quant |
| mixtral-8x7b-awq | FALSE-FAIL | model OK (ready, KV 266k, maxc 43×), sanity-parse bug |
| qwen3.5-9b | FAIL | vLLM szuka `preprocessor_config.json` (qwen3_5 jako multimodal) |
| bielik-11b-v30-instruct-awq | FAIL | tokenizer instantiation fail |
| mistral-nemo-instruct-2407 | FAIL | katalog 46 GB (anomalia dla 12B), log pusty |

## Decyzja: transformers 5.8.1 (stack v0.3+)

transformers 4.57.x **nie zawiera** architektury `qwen3_5` (Qwen3.5 + 3.6).
`qwen3_5` jest dopiero w transformers 5.x. vLLM 0.19 akceptuje `<5,>=4.56`,
ale empirycznie działa z 5.8.1 (zwalidowane: bielik-4.5b sanity PASS + 3
modele PASS w batchu). **transformers 5.8.1 zostaje jako stack v0.3+.**

### Wpływ na dotychczasowe wyniki (NIE re-test wydajności)

- **Sweepy (throughput/knee/plateau)** — domena vLLM engine, niezależna od
  transformers. **NIE powtarzać.**
- **Sanity envelope** — VRAM/KV/max_concurrency to vLLM; `load_time` minimalnie
  zależy. Wystarczy **smoke-recheck** (ładuje się / nie) — patrz Faza 1.
- **Caveat:** `compressed-tensors 0.14.0.1` wymaga `transformers<5.0.0`
  (dependency conflict) — FP8 path zagrożony, wymaga weryfikacji (Faza 1).
- **METHODOLOGY §3:** odnotować transformers 5.8.1 jako stack v0.3+, smoke-recheck
  jako audyt ciągłości.

## Fazy

### Faza 0 — dokończ download (~5 min)
- Qwen3.6-35B-A3B-FP8 — leci (~30/35 GB). Dokończy się.

### Faza 1 — weryfikacja stacku transformers 5.8.1 (~45 min)
- Smoke-recheck: czy już-testowane modele ładują się na 5.8.1 — qwen25-7b,
  bielik-11b-v23, bielik-11b-v30, bielik-4.5b-v30, bielik-pl-11b-v30.
- **compressed-tensors / FP8 test:** załadować qwen36-27b-fp8 — czy FP8 path
  działa mimo `compressed-tensors<5` conflict. Krytyczne dla §4.6 (35B-A3B-FP8).
- Wynik → ewentualna errata METHODOLOGY §3.

### Faza 2 — szybkie naprawy FAIL (~1 h)
- **mixtral-8x7b-awq** — re-sanity (false-fail, model działa)
- **qwen3.5-9b** — fix image-processor: `preprocessor_config.json` lub vLLM
  flag wyłączający multimodal-loading dla qwen3_5
- **bielik-11b-v30-instruct-awq** — diagnoza tokenizera (transformers 5.8.1?
  pliki tokenizer modelu?)
- **mistral-nemo** — inspekcja katalogu 46 GB (12B ≈ 24 GB; sprawdzić
  duplikaty / `.cache/` / niekompletny download)

### Faza 3 — kwantyzacja AWQ dużych modeli (ZAPLANOWANE — godziny GPU)

Per METHODOLOGY #21 wzorzec (Kimi-Dev "BF16→AWQ-marlin, local quant w/ AutoAWQ").

**Modele do kwantyzacji (6):**
| Model | Stan wejściowy | Docelowo |
|---|---|---|
| kimi-dev-72b | NIE pobrany — najpierw download (~142 GB BF16) | AWQ ~40 GB |
| llama-pllum-70b-base | BF16 132 GB na dysku | AWQ ~40 GB |
| llama-pllum-70b-instruct | BF16 132 GB | AWQ ~40 GB |
| llama-pllum-70b-chat | BF16 132 GB | AWQ ~40 GB |
| llama-pllum-70b-base-250801 | BF16 132 GB | AWQ ~40 GB |
| llama-pllum-70b-chat-250801 | BF16 132 GB | AWQ ~40 GB |

**Wymagania techniczne:**
- `AutoAWQ` zainstalowany w venv vllm (`pip install autoawq` — verify)
- **Krytyczne:** 70B BF16 (132 GB) NIE mieści się w 64 GB VRAM → kwantyzacja
  musi być **layer-wise / sequential** (AutoAWQ ładuje warstwa-po-warstwie)
  lub z CPU offload. Wolniejsze ale wykonalne.
- Calibration dataset — domyślny (pileval/c4 sample) lub — rozważyć
  domain-specific (kliniczny PL) dla wierności PLLuM. Decyzja Łukasza.
- Serve po quant: `--quantization awq_marlin --enforce-eager`

**ETA Fazy 3:** kwantyzacja 70B ≈ 2-4 h/model (layer-wise, GPU-heavy).
6 modeli → **~12-24 h GPU**. To wąskie gardło recovery. Sekwencyjnie.
Download kimi-dev (~142 GB) doliczyć (~30-60 min).

**Output:** `~/models/<model>-awq/` per model. Disk: 6× ~40 GB = ~240 GB
(wolne ~2.5 TB — OK).

### Faza 4 — sanity skwantowanych (~2 h)
- sanity TP=2 dla 6 modeli AWQ (kimi-dev + 5× PLLuM-70B-AWQ)
- `--quantization awq_marlin --enforce-eager`, port 8100, lab log + JSON

### Faza 5 — METHODOLOGY §4 korekta
- #14-18 PLLuM-70B: "BF16 TP2" → "BF16 niewykonalne na 2×R9700 (132 GB >
  64 GB); **AWQ-marlin required**" + nowe wpisy dla wariantów AWQ
- #21 kimi-dev-72b: faktyczny status (był nie pobrany; po Fazie 3 → AWQ)
- #3 qwen3.5-9b: dependency na transformers 5.8.1 + status image-processor fix
- §3: transformers 5.8.1 jako stack v0.3+

### Faza 6 — sweepy
- Phase 2 sweep dla modeli z sanity PASS (envelope kompletny)
- EMBARGO_paper_bound §11.2

## Ścieżka krytyczna

Faza 3 (kwantyzacja AWQ, ~12-24 h GPU) to wąskie gardło. Fazy 0-2 (~2 h)
i 5 (~15 min) szybkie. Faza 4 zależy od 3. Faza 6 po 4.

## Stan envelope po batchu (PASS)

bielik-4.5b-v30, bielik-11b-v23-awq, bielik-11b-v30, bielik-pl-11b-v30,
llama-pllum-8b-instruct, pllum-12b-chat — ~6 modeli z czystym sanity.
Po Fazach 2+4 cel: +mixtral, +qwen3.5/3.6 (jeśli fix), +6 AWQ = ~15+.

## Realizacja

Fazy 0-2 — autonomicznie (download + weryfikacja + szybkie naprawy).
Faza 3 (AWQ) — zaplanowana; uruchomienie po decyzji Łukasza (calibration
dataset choice + potwierdzenie ~12-24 h GPU okna).
