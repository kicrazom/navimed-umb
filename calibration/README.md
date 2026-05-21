# Clinical-PL SmPC AWQ Calibration Corpus

Calibration corpus for AWQ / AutoAWQ quantization of the **Llama-PLLuM-70B** model
family. 418 text chunks (~512 tokens) of dense clinical Polish — pulmonology and
thoracic oncology — extracted from Summary of Product Characteristics (SmPC /
*Charakterystyka Produktu Leczniczego*) documents.

Used to calibrate the `mozarcik/Llama-PLLuM-70B-*-awq` model series (produced on the
AMD Developer Cloud, Instinct MI300X).

## Files

| Path | Description |
|---|---|
| `clinical-pl/corpus.jsonl` | 418 chunks, per-chunk provenance schema (below) |
| `clinical-pl/extract_corpus.py` | Extraction script (PDF → chunked corpus) — reproducible |
| `clinical-pl/drug-catalog-PL.md` / `-EN.md` | Drug index — 81 INN, 9 NFZ drug programmes |
| `clinical-pl/chpl_raw/` | Source SmPC PDFs — **not tracked** (third-party content; see LICENSE) |

## Per-chunk schema

```json
{
  "text": "...",
  "source_authority": "EMA",
  "source_document_type": "SmPC / Product Information",
  "source_url": "https://www.ema.europa.eu/en/medicines/human/EPAR/...",
  "medicine": "aclidinium",
  "brand_name": "Eklira Genuair",
  "language": "pl",
  "retrieved_at": "2026-05-20",
  "chunk_id": "EMA_aclidinium_pl_0001",
  "license_note": "EMA reproduction policy; source attribution required"
}
```

**No patient data / no PHI** — SmPC documents describe drug products (efficacy, dosing,
adverse reactions, pharmacokinetics, aggregate trial data), not individuals. Verified by
automated pattern scan and manual sampling.

## License and source attribution

This dataset is a calibration corpus for AWQ/AutoAWQ quantization of Polish clinical LLMs.
It contains text chunks derived from official medicinal product information documents.

### Source text

Parts of the source text are derived from EMA-published Polish SmPC / Product Information documents.

EMA source text: © European Medicines Agency.
EMA-published documents are reproduced and distributed under EMA's content-reproduction policy, which permits reproduction and/or distribution, in whole or in part, for non-commercial and commercial purposes, provided that EMA is always acknowledged as the source.

Parts of the source text may derive from Polish national medicinal product documentation available via URPL / Polish public-sector sources. Reuse of those parts is subject to the applicable source-specific public-sector information reuse rules and the original document provenance.

### Compilation

Compilation, drug selection, extraction workflow, chunking, dataset structuring and metadata:
Łukasz Minarowski / navimed-umb.

No claim is made that the underlying SmPC/ChPL source text is licensed under CC-BY-4.0, CC-BY-NC-4.0, MIT, Apache-2.0 or any other open-source software license.

> **This directory (`calibration/`) is governed by `calibration/LICENSE`, NOT by the
> repository's root CC-BY-4.0 / MIT licenses.**
