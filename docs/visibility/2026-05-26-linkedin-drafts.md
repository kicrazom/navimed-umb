---
type: linkedin-draft
status: draft
project: navimed-umb
event: run-3-consumer-gpu-pllum-awq-ship
date: 2026-05-26
related_post: https://www.linkedin.com/posts/lukasz-minarowski-73b3233b_navimed-umb-hardware-envelope-studies-for-activity-7464059097575907328
tags: [project/navimed-umb, channel/linkedin, status/draft]
related:
  - "[[90_Meta/wiki/llm/Methods/clinical-pl-smpc-awq-calibration|clinical-pl-smpc-awq-calibration]]"
---

# LinkedIn drafts — Run-3 consumer-GPU PLLuM AWQ ship (2026-05-26)

Cel: ogłosić zamknięcie warstwy konsumenckiej rodziny PLLuM AWQ (8B Llama-PLLuM-chat-2512 + 12B PLLuM-chat-2512) trzy dni po flagowym poście o 70B (23.05, activity `7464059097575907328`). Dwie opcje do wyboru przy posting time.

---

## Option A — standalone post (~800-1200 znaków)

Trzy dni po rodzinie PLLuM-70B AWQ zamykam dolną półkę tego samego pipeline'u — dwa publiczne AWQ W4A16 (vLLM-native) na jednej AMD Radeon AI PRO R9700 (32 GiB, gfx1201):

- `mozarcik/Llama-PLLuM-8B-chat-2512-awq` (Llama 3.1).
- `mozarcik/PLLuM-12B-chat-2512-awq` (Mistral, Apache 2.0).

Koperta (TP=1, vLLM 0.19+rocm721): 8B → 5.53 GiB wag, 22.22 GiB KV przy seq=2048, ~89× max concurrency. 12B → 8.03 GiB, 19.77 GiB KV, ~63×. Sanity 5/5 PASS na pięciu polskich promptach klinicznych. Throughput pod embargiem METHODOLOGY §11.2/§11.3 do paper #1.

Korpus kalibracyjny ten sam co dla 70B: `clinical-pl-smpc-awq-calibration` (418 fragmentów ChPL z EMA, No PHI) — porównywalność jakości kwantyzacji w skali całej rodziny PLLuM.

Post-mortem: `hf_transfer` cicho ucinał shardy sourca 12B (bez błędu, bez `.incomplete`), downstream rzucał mylący `ImportError: protobuf`. Rescue: `curl -4` per shard na `cas-bridge.xethub.hf.co`. Lekcja: `HF_HUB_ENABLE_HF_TRANSFER=0` dla repo tokenizer-heavy.

NaviMed-UMB: suwerenny stack klinicznego AI na europejskim sprzęcie AMD, lokalnie — polski LLM na jednej konsumenckiej karcie.

Zenodo v0.4.0: `10.5281/zenodo.20364953`. Atrybucje: konsorcjum PLLuM (SpeakLeash, OPI-PIB, NASK, PWr) + Ministerstwo Cyfryzacji RP; AMD za R9700. AI disclosure: redakcja PL Bielik-11B lokalnie, dokumentacja Claude/GPT-5.

---

## Option B — comment to 70B activity (~300-500 znaków)

Update: dziś zamykam warstwę konsumencką tego samego pipeline'u. Dwa nowe publiczne AWQ na jedną kartę R9700 (32 GiB): `mozarcik/Llama-PLLuM-8B-chat-2512-awq` (5.53 GiB wag, ~89× max concurrency) i `mozarcik/PLLuM-12B-chat-2512-awq` (8.03 GiB, ~63×). Ten sam korpus kalibracyjny co 70B (418 fragmentów ChPL EMA) — porównywalność jakości w całej rodzinie PLLuM. Sanity 5/5 PASS na PL promptach klinicznych. Throughput pod embargiem do paper #1. Zenodo `10.5281/zenodo.20364953`.

---

## Attribution checklist

Encje, które muszą zostać otagowane / wymienione w finalnym poście (LinkedIn handles do dopięcia przy posting time — zostaw `[FILL: @handle]` jeśli nieznane):

- **Konsorcjum PLLuM** — wymienić wszystkich czterech członków: SpeakLeash, OPI-PIB (Ośrodek Przetwarzania Informacji – Państwowy Instytut Badawczy), NASK (Naukowa i Akademicka Sieć Komputerowa), PWr (Politechnika Wrocławska). LinkedIn tags: `[FILL: @SpeakLeash]`, `[FILL: @OPI-PIB]`, `[FILL: @NASK]`, `[FILL: @PWr]`.
- **Ministerstwo Cyfryzacji RP** — finansowanie programu PLLuM. LinkedIn tag: `[FILL: @MinisterstwoCyfryzacji]`.
- **AMD** — sprzęt (R9700 home stack). **Bez promotional credit** — Run-3 nie jest częścią MI300X-grantu (w przeciwieństwie do 70B z 23.05). LinkedIn tag: `[FILL: @AMD]` opcjonalnie, ale bez framingu „dzięki AMD Developer Cloud" — to było pod 70B.
- **Dataset** — `mozarcik/clinical-pl-smpc-awq-calibration` (HuggingFace link w treści, nie wymaga tagu LinkedIn).
- **HuggingFace** — hosting modeli. LinkedIn tag: `[FILL: @HuggingFace]`.
- **UMB / USK** — afiliacja kliniczna (Zakład Fizjopatologii Oddychania, II Klinika Chorób Płuc). Opcjonalnie wymienić jako kontekst zastosowania klinicznego, jeśli post ma być kierowany do społeczności medycznej. LinkedIn tag: `[FILL: @UMB]`.
- **AI assistance disclosure (obowiązkowy)** — Bielik-11B-v3.0-instruct-AWQ (redakcja PL, lokalnie na R9700) + Claude/GPT-5 (dokumentacja techniczna). LinkedIn tag dla Bielika: `[FILL: @SpeakLeash]` (te same osoby co PLLuM).

**Hashtags (do rozważenia, max 3-5):** `#PLLuM` `#AWQ` `#vLLM` `#ROCm` `#ClinicalAI` `#SovereignAI`.

**Halucynacja-watch przed publikacją:** żadnych liczb downloads/views z poprzedniego posta — wstawić przy posting time jeśli Łukasz zechce. Liczby koperty (5.53 / 22.22 / 88.89× / 8.03 / 19.77 / 63.27×) i 418 fragmentów są źródłowane z `logbook/2026-05-26.md` (PUBLIC §11.1). DOI v0.4.0 `20364953` do zweryfikowania na Zenodo PRZED postem (concept `19851346` resolves to latest niezależnie).
