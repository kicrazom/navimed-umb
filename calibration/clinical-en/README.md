# Clinical-EN SmPC AWQ/GPTQ Calibration Corpus

English-language mirror of the [`clinical-pl/`](../clinical-pl/README.md) calibration
corpus. 412 text chunks (~150 words / ~512-token budget) of dense clinical **English**
— pulmonology and thoracic oncology — extracted from the **English** Summary of Product
Characteristics (SmPC / Annex I of EMA Product Information) for the **same medicines**
as the Polish corpus.

Intended as a calibration / quantization-evaluation corpus for AWQ / AutoAWQ / GPTQ
quantization of English (or multilingual) clinical LLMs, and as the English counterpart
for cross-lingual calibration experiments alongside the `mozarcik/Llama-PLLuM-70B-*-awq`
series.

> **PL summary / streszczenie.** Angielski odpowiednik korpusu `clinical-pl/`. Te same
> leki (81 INN, 9 programów lekowych NFZ — patrz `clinical-pl/drug-catalog-EN.md`), ale
> tekst pochodzi z **angielskiej** ChPL (Annex I) z tych samych dokumentów EPAR EMA.
> 412 fragmentów, identyczny schemat per-chunk z `language: "en"`. Pipeline:
> `fetch_pi.py` (pobranie angielskich PDF-ów PI) → `extract_corpus.py` (ekstrakcja
> Annex I → chunking ~150 słów → `corpus.jsonl`). Każdy fragment to **dosłowny** tekst
> z realnego pobranego dokumentu EMA (zweryfikowane 412/412, 0 fabrykacji).

## Files

| Path | Description |
|---|---|
| `corpus.jsonl` | 412 chunks, per-chunk provenance schema (below), `language: "en"` |
| `extract_corpus.py` | Extraction script (EN PI PDF → chunked corpus) — EN-parametrized copy of the PL script |
| `fetch_pi.py` | Downloads the English Product Information PDFs from EMA into `epar_raw/` |
| `manifest.json` | medicine → brand_name → EPAR slug (derived from the verified `clinical-pl` `source_url`s) |
| `fetch_log.json` | Audit log of what was fetched (URL, bytes, sha256) vs skipped (with reason) |
| `RUNBOOK.md` | Exact commands + URL list to rebuild / refresh the corpus from scratch |
| `epar_raw/` | Source English PI PDFs — **not tracked** (third-party EMA content; see LICENSE) |

The drug list itself is shared with the Polish corpus — see
`../clinical-pl/drug-catalog-EN.md` and `-PL.md` (81 INN, 9 NFZ drug programmes). No
separate drug catalog is duplicated here.

## Per-chunk schema

Identical to `clinical-pl/`, with `language: "en"`:

```json
{
  "text": "4.1 Therapeutic indications TAGRISSO as monotherapy is indicated for: ...",
  "source_authority": "EMA",
  "source_document_type": "SmPC / Product Information",
  "source_url": "https://www.ema.europa.eu/en/documents/product-information/tagrisso-epar-product-information_en.pdf",
  "medicine": "osimertinib",
  "brand_name": "TAGRISSO",
  "language": "en",
  "retrieved_at": "2026-06-06",
  "chunk_id": "EMA_osimertinib_en_0001",
  "license_note": "EMA reproduction policy; source attribution required"
}
```

## How this differs from the Polish pipeline

The EN pipeline is **structurally identical** to `clinical-pl/extract_corpus.py`; only
language-bound tokens and the fetch step differ:

1. **Source documents.** EMA publishes one EPAR per centrally-authorised medicine with
   Product Information in every EU language. The PL corpus used the **Polish** PI; this
   corpus uses the **English** PI PDF of the *same* EPAR
   (`.../product-information/<slug>-epar-product-information_en.pdf`).
2. **Explicit fetch step.** `fetch_pi.py` downloads the English PIs into `epar_raw/`
   (the PL corpus assumed pre-downloaded PDFs in `chpl_raw/`). The brand→EPAR-slug
   `manifest.json` is derived directly from the verified `clinical-pl` `source_url`s,
   so no URL is guessed.
3. **Language-bound parsing tokens** (the only changes inside the extractor):
   - Annex boundary `ANEKS II` → `ANNEX II`
   - Section-6 tail `6. DANE FARMACEUTYCZNE` → `6. PHARMACEUTICAL PARTICULARS`
   - Running-header drop-line `CHARAKTERYSTYKA PRODUKTU LECZNICZEGO` → `SUMMARY OF PRODUCT CHARACTERISTICS`
   - Pharmaceutical-form strip keywords → English (`tablets`, `capsule`, `solution`, …)
   - `language: "en"`, `chunk_id` suffix `_en_` instead of `_pl_`
4. **Unchanged for material equivalence.** Annex I restriction, dropping section 6+
   boilerplate, the ~150-word sentence-boundary chunker (hard cap 255, min 80), the
   per-drug proportional + stratified-by-section sampling, and the `SECTION_WEIGHT`
   bias toward clinical-efficacy/pharmacology are byte-for-byte the PL logic.

Result shape closely matches the PL corpus: 412 vs 418 chunks; words/chunk
min 80 / median 161 / max 255 (PL: median 161); all 61 medicines covered; the
4.2 / 4.8 / 5.1 / 4.1 / 4.6 sections dominate in both.

## Provenance & anti-hallucination

- **Every chunk's `text` is verbatim** extracted from a real fetched EMA English PI PDF
  in `epar_raw/`. Verified programmatically: all **412/412** chunks are a contiguous span
  of their source document after the extractor's own line-cleaning (page numbers and
  running headers removed). Zero fabricated or paraphrased text.
- **Every `source_url` was actually fetched** — see `fetch_log.json` (URL, byte count,
  sha256 per medicine). 61/61 medicines fetched, 0 skipped.
- **Every `brand_name` matches the real document** and the PL corpus (0 brand mismatches
  flagged by the head-vs-manifest cross-check).
- **No patient data / no PHI** — SmPC documents describe drug products (efficacy, dosing,
  adverse reactions, pharmacokinetics, aggregate trial data), not individuals. Verified by
  automated pattern scan (0 hits).

## Rebuild / refresh

See `RUNBOOK.md` for the exact two commands (`fetch_pi.py` then `extract_corpus.py`),
the venv setup (pymupdf), and the full list of EMA URLs. The build is fully
reproducible and auditable.

## License and source attribution

Same terms as `clinical-pl/` — governed by `calibration/LICENSE`, **not** the
repository root licenses.

### Source text

Source text is derived from **EMA-published English** SmPC / Product Information documents.

EMA source text: © European Medicines Agency. EMA-published documents are reproduced and
distributed under EMA's content-reproduction policy, which permits reproduction and/or
distribution, in whole or in part, for non-commercial and commercial purposes, provided
that EMA is always acknowledged as the source.

### Compilation

Compilation, drug selection, extraction workflow, chunking, dataset structuring and
metadata: Łukasz Minarowski / navimed-umb.

No claim is made that the underlying SmPC source text is licensed under CC-BY-4.0,
CC-BY-NC-4.0, MIT, Apache-2.0 or any other open-source license.

> **This directory (`calibration/`) is governed by `calibration/LICENSE`, NOT by the
> repository's root CC-BY-4.0 / MIT licenses.**
