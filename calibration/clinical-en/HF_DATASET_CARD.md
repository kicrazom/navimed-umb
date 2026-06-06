---
license: other
license_name: ema-public-reproduction-policy-and-source-specific-reuse-terms
language:
  - en
pretty_name: Clinical-EN SmPC AWQ Calibration Corpus
task_categories:
  - text-generation
size_categories:
  - n<1K
tags:
  - awq
  - autoawq
  - gptq
  - calibration-corpus
  - smpc
  - clinical-nlp
  - medical
  - english
  - pulmonology
  - oncology
  - pllum
  - quantization
---

# Clinical-EN SmPC AWQ Calibration Corpus

An English clinical-domain text corpus used as a **calibration set for AWQ / AutoAWQ /
GPTQ post-training quantization** of English (or multilingual) clinical large language
models. The corpus is dense, domain-specific clinical English (pulmonology + thoracic
oncology), drawn from the **English** Summary of Product Characteristics (SmPC, Annex I
of the EMA Product Information).

This is the **cross-language counterpart** to the Polish corpus
[`mozarcik/clinical-pl-smpc-awq-calibration`](https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration):
**the same medicines**, but the text is the English Annex I instead of the Polish ChPL,
extracted from the *same* EMA EPAR documents. It is intended for English-side and
cross-lingual calibration experiments alongside the `mozarcik/Llama-PLLuM-70B-*-awq`
series.

> **Streszczenie (PL).** Angielski odpowiednik korpusu kalibracyjnego
> [`mozarcik/clinical-pl-smpc-awq-calibration`](https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration).
> Te same leki, ale tekst pochodzi z **angielskiej** ChPL (Annex I Charakterystyki
> Produktu Leczniczego) z tych samych dokumentów EPAR EMA — nie z polskiej wersji.
> **412 fragmentów** (chunków) gęstego klinicznego angielskiego (pulmonologia +
> onkologia klatki piersiowej) z **61 leków EMA**. Identyczny schemat per-chunk jak w
> korpusie PL, z `language: "en"`. Przeznaczenie: dane kalibracyjne do kwantyzacji
> potreningowej (AWQ / AutoAWQ / GPTQ) anglojęzycznych i wielojęzycznych modeli LLM,
> oraz strona angielska eksperymentów kalibracji międzyjęzykowej. **To nie jest** zbiór
> treningowy ani ewaluacyjny.

## Contents / Zawartość

**412 text chunks** (soft window ~150 words, hard cap 255, min 80; ~512-token budget)
extracted from the **English** Annex I SmPC / Product Information of **61 EMA
centrally-authorised medicines** in pulmonology and thoracic oncology. Each record
carries per-chunk source provenance with `language: "en"`:

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

All 412 chunks have `source_authority = "EMA"`,
`source_document_type = "SmPC / Product Information"` and `language = "en"`. The
SmPC sections most represented are §4.2 (posology), §4.8 (undesirable effects), §5.1
(pharmacodynamics / clinical efficacy), §4.1 (indications), §4.6, §4.4 and §5.2 — the
same clinical-efficacy / pharmacology bias as the Polish corpus.

The medicine list is shared with the Polish corpus (61 INNs realized here, brand →
EPAR slug map in `manifest.json`). Files in this dataset repository:

| Path | Description |
|---|---|
| `corpus.jsonl` | 412 chunks, per-chunk provenance schema above, `language: "en"` |
| `manifest.json` | medicine → brand_name → EPAR slug (derived from the verified `clinical-pl` source URLs) |
| `README.md` | this dataset card |

> `corpus.jsonl` SHA-256: `820b7a4de75f20baddf3d89fa73a3d8f348ae22086f1ed52f0278ec6040aac85`

## How it was built / Jak powstał

Structurally identical pipeline to the Polish corpus; only language-bound tokens and an
explicit fetch step differ. For each of the 61 medicines, the **English** Product
Information PDF was fetched from EMA
(`.../product-information/<epar_slug>-epar-product-information_en.pdf`, retrieved
**2026-06-06**), parsing restricted to **Annex I clinical prose** (Annex II/III labelling,
the package leaflet, and the Section 6 pharmaceutical-particulars tail are excluded).
Text was chunked at a soft ~150-word window (sentence-boundary preferred, hard cap 255,
min 80) and sampled per drug proportionally to clinical-prose volume, with a section
weighting biased toward clinical-efficacy (§5.1), pharmacokinetics (§5.2), dosing (§4.2)
and special-warnings (§4.4) content. The extraction is deterministic and reproducible
(script + RUNBOOK live in the [navimed-umb](https://github.com/kicrazom/navimed-umb)
repository under `calibration/clinical-en/`).

Result shape closely matches the Polish corpus: 412 vs 418 chunks; words/chunk
min 80 / median 161 / max 255 (PL median also 161); all 61 medicines covered.

## Intended use / Przeznaczenie

Calibration data for post-training quantization (AWQ / AutoAWQ / GPTQ) of English and
multilingual clinical LLMs, and the English side of cross-lingual calibration
experiments paired with the Polish corpus. Reuse as a corpus-controlled calibration set
enabling like-for-like quantization-quality comparison across model scales and languages.

**This is NOT a training set and NOT an evaluation / benchmark set.** It is not a
question-answering, instruction-tuning, or clinical-decision-support dataset and must
not be used to fine-tune clinical behaviour or to evaluate clinical accuracy.

**No patient data / no PHI.** SmPC documents describe medicinal products (indications,
dosing, adverse reactions, pharmacokinetics, aggregate clinical-trial data), not
individuals. Every chunk's `text` is **verbatim** extracted from a real fetched EMA
English PI PDF — verified programmatically (412/412 chunks are a contiguous span of
their source document after line-cleaning; zero fabricated or paraphrased text), and
absence of PHI was confirmed by automated pattern scan. The corpus is not clinical
advice and confers no clinical authority; the canonical, legally-authoritative product
information remains the EMA-published SmPC.

## License and source attribution

This dataset is a calibration corpus for AWQ / AutoAWQ / GPTQ quantization of clinical
LLMs. It contains text chunks derived from official medicinal product information
documents. The licence is **`other`** (EMA public-reproduction policy and
source-specific reuse terms) — the **same terms as the Polish corpus**.

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
CC-BY-NC-4.0, MIT, Apache-2.0 or any other open-source software license. Users are
responsible for preserving EMA source attribution and for checking source-specific
restrictions before redistribution or downstream use.

## Context

Built for [**navimed-umb**](https://github.com/kicrazom/navimed-umb) — a local-LLM
benchmarking and clinical-decision-support feasibility project (Medical University of
Białystok). Cross-language counterpart to
[`mozarcik/clinical-pl-smpc-awq-calibration`](https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration).
