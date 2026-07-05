# PLAN 2026-06-30 — Precision ablation BF16 vs AWQ (small/mid, RDNA4)

**Cel:** kontrolowana, **same-checkpoint** macierz BF16↔AWQ na małych/średnich modelach,
spanning architektura × rozmiar, na 2× R9700 (gfx1201). De-konfunduje obecny finding
„AWQ kernel slowdown" (dziś oparty wyłącznie na polskich modelach) i dorzuca **energetyczny**
kąt (W/tok). Wyniki → **Paper #1** jako sub-study „Precision ablation".

**Geneza:** pytanie współpracownika (30.06) — „czemu nie wszystkie modele w BF16 i AWQ?".
Odpowiedź envelope (70B BF16 132 GB > 64 GB → AWQ wymuszone; ≤27B → BF16 natywnie) jest
poprawna, ale obnaża lukę: kontrast precyzji żyje tylko w polskich parach (Bielik/PLLuM),
i te nie są same-checkpoint (Bielik #9 base vs #10 instruct). Domykamy.

**Pozycja metodologiczna:** to **ablacja naukowa, NIE punkt envelope** — te modele mieszczą
się w BF16, AWQ nie służy tu pojemności. Oznaczyć jawnie w paperze (inaczej zapraszamy
pytanie „po co AWQ dla 7B").

**Embargo:** envelope (load/VRAM/KV/max_conc) PUBLIC §11.1; per-N throughput/latencja/W/tok
EMBARGOED §11.2 (§11.3 dla modeli polskich — Bielik/PLLuM).

---

## Macierz (6 par same-checkpoint)

| # | Model | Arch | Rozmiar | BF16 | AWQ | Status |
|---|---|---|---|---|---|---|
| 1 | Qwen2.5-7B-Instruct | Qwen | 7B | ✅ `qwen25-7b-instruct` | **do kwant.** | quant only |
| 2 | Bielik-4.5B-v3.0-Instruct | Mistral-PL | 4.5B | ✅ `bielik-4.5b-v30` | **do kwant.** | quant only |
| 3 | Bielik-11B-v3.0-Instruct | Mistral-PL | 11B | ⏳ pobrać BF16-instruct (~22GB) | ✅ `bielik-11b-v30-instruct-awq` | **download BF16, 0 quant** |
| 4 | Mistral-Nemo-Instruct-2407 | Mistral | 12B | ✅ `mistral-nemo-instruct-2407` | **do kwant.** | quant only |
| 5 | Llama-PLLuM-8B-chat-2512 | Llama | 8B | ✅ | ✅ Run-3 (`mozarcik/...-awq`) | **para gotowa** |
| 6 | PLLuM-12B-chat-2512 | Mistral | 12B | ✅ | ✅ Run-3 | **para gotowa** |

Architektury: Qwen, Llama, Mistral, Bielik. Rozmiary: 4.5 → 12B. **4 nowe kwantyzacje**,
2 pary już z Run-3.

**Świadomie poza zakresem:** Qwen3.5-9B (multimodal arch → AutoAWQ-ryzyko, precedens gemma3;
2.5-7B jest rep Qwen), Qwen3.6-27B (ma już kontrast FP8 #5), Bielik-PL-11B (redundantny),
Mixtral-AWQ (broken na gfx1201, §4.4).

---

## Faza 0 — Prep / acquisition (~0.5–2 h, zależnie od pobrań)
- [x] **Inwentarz zweryfikowany 2026-06-30:** Qwen2.5-7B (`qwen25-7b-instruct`)✅, Bielik-4.5B✅, Mistral-Nemo✅ BF16 obecne; PLLuM-8B/12B pary BF16+AWQ✅; Bielik-11B-v3.0-Instruct-AWQ✅. **Jedyny brak: Bielik-11B-v3.0-Instruct BF16** → pobrać (`hf-download-watchdog`, ~22GB). Alt bez pobrania: kwant `bielik-11b-v30` (base) → para base.
- [ ] Potwierdź pary Run-3 (PLLuM-8B/12B BF16 + AWQ) obecne; sprawdź czy mają już sweepy (Run-3 sweep był scoped v0.5.0 — może NIE zrobiony → wtedy też lecą w Faza 3).
- [ ] Korpus kalibracyjny `clinical-pl-smpc-awq-calibration` (418 SmPC) lokalnie — **ten sam dla wszystkich** (kalibracja domenowa CDSS-PL; dla Qwen/Mistral to świadomy wybór, spójny i domain-relevant — udokumentować).
- [ ] Pin wersji do provenance: llm-compressor 0.10.0.2, vLLM/ROCm stack, BIOS 2202/AGESA 1.3.0.1, VBIOS R9700AT-F40.

## Faza 1 — Kwantyzacja (3 nowe AWQ; ~3 × 25 min ≈ 1.3 h)
- [ ] `quant_llmc.py` (wzór Run-3) per model: Qwen2.5-7B, Bielik-4.5B, Mistral-Nemo. (Bielik-11B = download, nie quant.)
- [ ] Provenance: lokalny R9700, korpus, wersje (per [[project_navimed_quant_provenance]] — DISCLOSE wszędzie).
- [ ] Licencje: Qwen (Apache/Qianwen), Mistral-Nemo (Apache 2.0), Bielik (Apache 2.0) — czyste; brak overlay Llama.
- [ ] **Gate-1 sanity 5/5** (5 polskich promptów klinicznych via `/v1/completions`) per nowy AWQ — PRZED sweepem.

## Faza 2 — Envelope (Phase 1 METHODOLOGY) dla nowych AWQ configów (~2 h)
- [ ] Grid `(quant, max_model_len, gpu_mem_util, kv_cache_dtype, TP)` → load success, peak VRAM, KV cap, max_concurrency. PUBLIC §11.1.

## Faza 3 — Sweepy precyzji (rdzeń; główny koszt)
- [ ] **Same-checkpoint BF16 vs AWQ**, Tier A **REPS=10**, **pełna drabina N {1,10,25,50,100,200,500,1000}** (decyzja Łukasza 2026-06-30 — pełna rozdzielczość krzywej, koszt zaakceptowany).
- [ ] Metryki per cell: throughput tok/s, latencja (TTFT + per-tok), **W/tok (energia — metryka
      kluczowa)**, peak VRAM, thermals. Power z raw thermals (NIE results_table — bug zaniża 2×,
      [[project_navimed_power_provenance_bug]]).
- [ ] **Batching po 3** (jak N=1 anchor): no-sleep holder (`systemd-inhibit --what=sleep:idle
      --mode=block`), `rm SWEEP_COMPLETE` przed partią, sentinel per partia, **regen po każdej**.
- [ ] Cells: 6 modeli × 2 precyzje = 12 (minus pary Run-3 jeśli sweepy już są). Szac. **~12–20 h**
      sweepów (pełna drabina 8 pkt) — ≥2 noce, partie po 3.

## Faza 4 — Agregacja + energia + figury (ETL hybryda python→R)
- [ ] Δ(BF16→AWQ) per (model, N) dla throughput / latencja / W/tok.
- [ ] **Headline:** czy AWQ na gfx1201 jest *i wolniejsze, I mniej energooszczędne* (~4.8× W/tok
      penalty) — uogólnione przez Qwen/Llama/Mistral/Bielik, 4.5–12B.
- [ ] Figury: per-model BF16-vs-AWQ throughput-vs-N + W/tok-vs-N; tabela cross-architecture summary.
- [ ] Reużyj wzorca `aggregate_*`+`*_plots.R` z N=1 anchor; nowy `aggregate_precision_ablation.py`.

## Faza 5 — Stats + write-up → Paper #1
- [ ] Stats Tier A (§7.4): descriptive over reps; jeśli hipoteza „AWQ≠BF16 throughput/energy" →
      Holm-Bonferroni (osobna rodzina od knee/CANON_N).
- [ ] **Paper #1 — nowa sekcja „Precision ablation (BF16 vs AWQ) on RDNA4":**
      zasila §5.2 errata (AWQ kernel slowdown) systematycznym, multi-arch dowodem + historią
      energetyczną. De-konfunduje finding od polskich modeli.
- [ ] Methods + results-draft. Embargo §11.2/§11.3.

---

## Mapowanie na Paper #1
- **§5.2 errata** (AWQ slowdown) → z anegdoty robi się systematyczny wynik multi-arch.
- **Nowa figura/tabela**: precision-ablation matrix (throughput + W/tok vs N, per arch/rozmiar).
- **Narracja**: wzmacnia tezę „envelope > single-number" + dorzuca „na RDNA4 kwantyzacja NIE
  jest free lunch — płaci prędkością i energią" (kontra konwencjonalna wiedza).

## Ryzyka / caveats
- Multimodalne archy psują AutoAWQ → trzymamy się dense (Qwen2.5/Mistral/Bielik/Llama).
- Kalibracja PL-clinical dla modeli międzynarodowych = wybór domenowy, udokumentować.
- Efekt AWQ jest N-zależny → NIE raportować jednej liczby.
- Same-checkpoint twardo (inaczej confound rozmiar/wariant).
- No-edit-running-script: commit PRZED launchem partii lub PO sentinelu ([[feedback_no_edit_running_script]]).

## Kolejność wykonania (proponowana)
1. Faza 0 (downloads w tle) ‖ pisanie `aggregate_precision_ablation.py`.
2. Faza 1 (4 kwant.) + Gate-1.
3. Faza 2 (envelope) — szybka.
4. Faza 3 partia 1 (3 modele × 2 prec.) → regen → partia 2 → regen.
5. Faza 4–5 + draft do Paper #1.
> Opcjonalnie wpleść w istniejącą kolejkę N=1 (B5+B6 70B) — albo precyzja-ablacja najpierw
> (szybsza, daje Adamowi dane-z-liczbami prędzej), 70B w drugiej nocy.
