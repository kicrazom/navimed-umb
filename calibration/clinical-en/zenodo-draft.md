# Zenodo dataset deposition draft — Clinical-EN SmPC AWQ Calibration Corpus

> Ready-to-review standalone **dataset** record so the English corpus
> `mozarcik/clinical-en-smpc-awq-calibration` can become independently citable
> with its own DOI. The corpus is the **English cross-language counterpart** to
> the Polish corpus `mozarcik/clinical-pl-smpc-awq-calibration` (same medicines,
> English Annex I instead of Polish ChPL).
>
> **Status:** DRAFT for owner review. NO API call, NO deposit, NO publish has
> been made. Zenodo DOIs are permanent — creation/publication is the owner's
> action. Companion JSON payload: `zenodo-draft.json`.
>
> **READ FIRST — combine-or-split decision (§8.A):** the Polish corpus Zenodo
> record is **still an unpublished draft** (Zenodo record 20520407, draft on the
> owner's Desktop). Because neither corpus has a minted DOI yet, PL and EN can
> still be deposited as **one bilingual record** instead of two. Decide this
> before creating either deposit — see §8.A.

---

## 1. Record fields (as they will appear on Zenodo)

| Field | Value |
|---|---|
| **upload_type** | `dataset` |
| **title** | Clinical-EN SmPC AWQ Calibration Corpus: an English-language activation-aware quantization calibration set derived from EMA Summary of Product Characteristics |
| **creators** | Minarowski, Łukasz — ORCID `0000-0002-2536-3508` — Department of Respiratory Physiopathology, Medical University of Białystok, Poland |
| **access_right** | `open` |
| **license** | `other-at` (legacy Zenodo rejects bare `other`; `other-at` = "Other (attribution)" — EMA public-reproduction policy + source-specific reuse terms, see §4) |
| **language** | `eng` (ISO 639-3; corpus text is English) |
| **version** | `1.0.0` |
| **publication_date** | `2026-06-06` (adjust to the actual deposit date) |

### Creators (verbatim from `CITATION.cff`)

- **Name:** Minarowski, Łukasz
- **ORCID:** 0000-0002-2536-3508
- **Affiliation:** Department of Respiratory Physiopathology, Medical University of Białystok, Poland

> Only one person is named on this record. No collaborators, reviewers, or co-authors.

> **License-string note.** The PL draft used `license: "other"`. Legacy Zenodo's
> structured licence vocabulary **rejects bare `other`**; the correct legacy id
> for an attribution-style custom licence is **`other-at`** ("Other (attribution
> required)"), which matches the EMA "always acknowledge the source" requirement.
> The InvenioRDM-based new Zenodo uses SPDX-style ids; if depositing via the new
> UI/API, the equivalent is the custom/`other` right with the full rights text in
> the description. **Both corpora should use the same licence id — reconcile the
> PL draft to `other-at` too** (the PL `.json` currently says `other`).

---

## 2. Description (dataset abstract — paste into the Zenodo Description field)

**Summary.** The *Clinical-EN SmPC AWQ Calibration Corpus* is an English-language,
clinical-domain text corpus assembled to serve as a **calibration set for
activation-aware weight quantization (AWQ / AutoAWQ / GPTQ, W4A16)** of English and
multilingual large language models intended for clinical use. It comprises **412 text
chunks** (~512-token budget; observed window 80–255 words, median 161) of dense,
domain-specific clinical English drawn from the pulmonology and thoracic-oncology
therapeutic areas. The corpus is distributed as a single newline-delimited JSON file
(`corpus.jsonl`) in which every record carries full per-chunk source provenance. It is
the **English cross-language counterpart** to the *Clinical-PL SmPC AWQ Calibration
Corpus* (`mozarcik/clinical-pl-smpc-awq-calibration`): the same 61 EMA medicines, but
the text is the **English** Annex I Summary of Product Characteristics rather than the
Polish *Charakterystyka Produktu Leczniczego*, extracted from the same EMA EPAR
documents. Pairing the two enables the English side of cross-lingual calibration
experiments alongside the `mozarcik/Llama-PLLuM-70B-*-awq` series.

**What it is.** A calibration corpus for post-training quantization (AWQ / AutoAWQ /
GPTQ) of English-language and multilingual clinical LLMs. Activation-aware quantization
requires a representative, dense sample of in-domain text so that per-channel activation
scales are estimated on data resembling the deployment distribution; for the clinical
use case that target distribution is dense clinical English (pulmonology and thoracic
oncology).

**How it was built.** For each of 61 centrally-authorised European Medicines Agency
(EMA) medicines shared with the Polish corpus, the **English** Product Information PDF
(Annex I SmPC) was retrieved from EMA on 2026-06-06 from the documented English PI URL
pattern (`.../product-information/<epar_slug>-epar-product-information_en.pdf`); the
brand → EPAR-slug map (`manifest.json`) is derived directly from the verified Polish
corpus `source_url`s, so no URL is guessed. Extraction (script `extract_corpus.py`,
PyMuPDF — an English-parametrized copy of the Polish extractor) was restricted to Annex I
clinical prose, excluding Annex II/III labelling and leaflet text and the Section 6
pharmaceutical-particulars tail (excipients, shelf-life, marketing-authorisation
boilerplate). Text was chunked at a soft window of ~150 words (hard cap 255, min 80),
sentence-boundary preferred, and sampled per drug proportionally to that drug's
clinical-prose volume with a section weighting biased toward clinical-efficacy
(SmPC §5.1), pharmacokinetics (§5.2), dosing (§4.2) and special-warnings (§4.4) content.
The chunking, sampling and section-weighting logic is byte-for-byte the Polish logic;
only language-bound parsing tokens and the explicit fetch step differ. The extraction
workflow is reproducible and included in the deposit.

**Per-chunk provenance schema** (every record in `corpus.jsonl`):

```json
{
  "text": "… (English SmPC clinical prose, ~512 tokens) …",
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

All 412 released chunks have `source_authority = "EMA"`,
`source_document_type = "SmPC / Product Information"` and `language = "en"`.
`corpus.jsonl` SHA-256: `820b7a4de75f20baddf3d89fa73a3d8f348ae22086f1ed52f0278ec6040aac85`.

**Intended use.** Calibration data for post-training quantization (AWQ / AutoAWQ / GPTQ)
of English-language and multilingual clinical LLMs, and the English side of cross-lingual
calibration experiments paired with the Polish corpus; reuse as a corpus-controlled
calibration set enabling like-for-like quantization-quality comparison across model
scales and languages.

**What it is NOT.** This is **not** a training set and **not** an evaluation / benchmark
set; it is not a question-answering, instruction-tuning, or clinical-decision-support
dataset and must not be used to fine-tune clinical behaviour or to evaluate clinical
accuracy. It contains **no patient data and no protected health information (PHI)**: SmPC
documents describe medicinal products (indications, dosing, adverse reactions,
pharmacokinetics, aggregate clinical-trial data), not individuals. Every chunk's `text`
is verbatim source text (verified: 412/412 chunks are a contiguous span of their source
document after line-cleaning; zero fabricated or paraphrased text) and absence of PHI was
confirmed by automated pattern scan. The corpus is not clinical advice and confers no
clinical authority; the canonical, legally-authoritative product information remains the
EMA-published SmPC.

**Rights and source attribution.** (See §4 — mirrored from the live HuggingFace dataset
card.)

**Context.** Produced for [NaviMed-UMB](https://github.com/kicrazom/navimed-umb), a
local-LLM benchmarking and clinical-decision-support feasibility project at the Medical
University of Białystok. The corpus is published on HuggingFace at
`mozarcik/clinical-en-smpc-awq-calibration`; this deposit makes it independently citable
with its own DOI.

**AI assistance disclosure.** Project documentation was prepared with assistance from
large language models (Claude, Anthropic; GPT, OpenAI; Gemini, Google). All drug
selection, extraction design, provenance assignment and scientific claims are the
author's. See `AI_USAGE_DISCLOSURE.md` in the repository.

---

## 3. Keywords

`calibration corpus`, `AWQ`, `AutoAWQ`, `GPTQ`, `activation-aware weight quantization`,
`W4A16`, `post-training quantization`, `English clinical NLP`, `clinical English`,
`cross-lingual calibration`, `PLLuM`, `large language models`, `pulmonology`,
`thoracic oncology`, `Summary of Product Characteristics`, `SmPC`, `EMA`,
`medical AI infrastructure`, `no PHI`

---

## 4. License decision (CRITICAL — EMA-derived text)

**Decision: `license = "other-at"`** (legacy Zenodo "Other (attribution)"; the PL draft's
bare `other` is rejected by legacy Zenodo's vocabulary — see §1 note). The corpus text is
EMA-derived; it must **not** be relicensed as CC-BY, CC-BY-NC, MIT, Apache-2.0, or any
other open-source software / open-data licence. This is the **same rights basis as the
Polish corpus** and mirrors the live HuggingFace dataset card
(`license: other`, `license_name: ema-public-reproduction-policy-and-source-specific-reuse-terms`).

Because Zenodo's structured `license` field cannot encode the EMA license name, the
rights statement is carried in full inside the Description / Notes:

> ### Source text
> Source text is derived from EMA-published **English** SmPC / Product Information
> documents.
>
> EMA source text: © European Medicines Agency. EMA-published documents are reproduced
> and distributed under EMA's content-reproduction policy, which permits reproduction
> and/or distribution, in whole or in part, for non-commercial and commercial purposes,
> provided that EMA is always acknowledged as the source.
>
> ### Compilation
> Compilation, drug selection, extraction workflow, chunking, dataset structuring and
> metadata: Łukasz Minarowski / navimed-umb.
>
> No claim is made that the underlying SmPC source text is licensed under CC-BY-4.0,
> CC-BY-NC-4.0, MIT, Apache-2.0 or any other open-source software license.

**Compilation vs. source text (state explicitly on the record):** the *compilation* —
drug selection, extraction scripts, chunking logic, dataset structure and per-chunk
metadata — is Łukasz Minarowski's own work (© Łukasz Minarowski / navimed-umb). The
*underlying SmPC source text* is © European Medicines Agency and is reused only under
EMA's reproduction policy with mandatory source acknowledgement. The author's compilation
contribution does **not** relicense the underlying source text. Users must preserve EMA
source attribution and check source-specific restrictions before redistribution or
downstream use.

---

## 5. related_identifiers (with relation types)

Enter these under "Related/alternate identifiers" in the Zenodo UI, or use the
`related_identifiers` array in the JSON payload. Relation vocabulary follows the
Zenodo/DataCite relation types.

| identifier | relation | scheme | resource_type | rationale |
|---|---|---|---|---|
| `https://huggingface.co/datasets/mozarcik/clinical-en-smpc-awq-calibration` | `isIdenticalTo` | url | dataset | The HF dataset is the same artifact (same `corpus.jsonl`, 412 chunks, SHA-256 `820b7a4d…`); the Zenodo deposit is the citable mirror with a DOI. |
| `https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration` | `isVariantFormOf` | url | dataset | The **Polish** sibling corpus — same 61 EMA medicines, parallel language (English Annex I vs Polish ChPL). NOT byte-identical (different language), hence `isVariantFormOf`, not `isIdenticalTo`. *(If the PL corpus gets its own Zenodo DOI, add that DOI here too with the same relation.)* |
| `https://github.com/kicrazom/navimed-umb` | `isSupplementTo` | url | software | The corpus supplements the NaviMed-UMB source repository (extraction script + manifest live in `calibration/clinical-en/`). |
| `10.5281/zenodo.19851346` | `isReferencedBy` | doi | software | NaviMed-UMB **concept** DOI (always resolves to latest version). |
| `10.5281/zenodo.20317011` | `isReferencedBy` | doi | software | NaviMed-UMB **v0.3.0** — release under which the PLLuM AWQ family + PL calibration corpus were first published. |
| `10.5281/zenodo.20364953` | `isReferencedBy` | doi | software | NaviMed-UMB **v0.4.0** — references the shared calibration approach across the 8B / 12B / 70B AWQ checkpoints. |

> **Relation-vocabulary notes.** `isIdenticalTo` is used for the HF mirror because the
> deposited file is byte-for-byte the same corpus (verified SHA-256). `isVariantFormOf`
> is used for the PL corpus because it is the *same compilation in another language*, not
> the same bytes — this is the conservative, accurate DataCite relation for a parallel
> translation/variant. The three navimed software DOIs are referenced exactly as in the
> PL draft (19851346 / 20317011 / 20364953).

---

## 6. Rationale (why a standalone dataset DOI)

- **FAIR / citable research artifact.** Reusable infrastructure (corpus-controlled
  cross-lingual calibration), not a by-product of one model. A standalone DOI lets it be
  cited independently and contributes a discrete data output toward the author's
  habilitation portfolio.
- **Bilingual calibration set.** Together with the PL corpus this forms a controlled
  PL/EN pair over identical medicines — citable as the substrate for cross-lingual
  quantization-quality studies.
- **Correct artifact typing.** A `dataset` upload_type signals to indexers (DataCite,
  OpenAIRE) that this is data, not software.
- **Provenance integrity.** The deposit ships the per-chunk provenance schema and the
  reproducible extraction workflow, so the licensing and EMA-attribution chain travels
  with the citable object.

---

## 7. Reviewer checklist (before clicking Publish)

- [ ] **One creator only** — Łukasz Minarowski; no collaborators/reviewers/co-authors.
- [ ] **ORCID** = `0000-0002-2536-3508`; **affiliation** = "Department of Respiratory Physiopathology, Medical University of Białystok, Poland" (verbatim from `CITATION.cff`).
- [ ] **upload_type = dataset** (not software/publication).
- [ ] **license = "other-at"** — NOT CC-BY / CC-BY-NC / MIT / Apache, and NOT bare `other` (legacy Zenodo rejects it). EMA reproduction-policy framing present in Description (§4).
- [ ] **Compilation-vs-source-text** distinction stated explicitly on the record.
- [ ] **No PHI claim** present and accurate (SmPC = product info, not patients; verified by scan).
- [ ] **NOT a training/eval set** stated explicitly.
- [ ] **Embargo-clean** — NO throughput / latency / tok-s / W-per-token / KV-occupancy / cross-model comparative numbers (METHODOLOGY §11.2 / §11.3). This record is the public corpus only. (Confirmed: none present.)
- [ ] **Chunk count = 412** (matches `corpus.jsonl` line count and SHA-256 `820b7a4d…`).
- [ ] **61 medicines** — all 61 in `manifest.json` are represented in the released chunks (0 missing, 0 extra; verified).
- [ ] **language = eng** (ISO 639-3).
- [ ] **related_identifiers** — 6 entries; HF EN dataset `isIdenticalTo`, HF PL dataset `isVariantFormOf`, navimed repo `isSupplementTo`, three navimed DOIs `isReferencedBy` (19851346 / 20317011 / 20364953).
- [ ] **Files to upload** — at minimum `corpus.jsonl`; recommended bundle: `corpus.jsonl` + `manifest.json` + `extract_corpus.py` + `fetch_pi.py` + `README.md` + `RUNBOOK.md` + `LICENSE` (`calibration/LICENSE`). Do NOT upload `epar_raw/` (third-party EMA source PDFs, ~78 MB; reproducible via the script + `source_url`s), `.venv`, or `fetch_log.json`.
- [ ] **`version`** = `1.0.0` (drafted; keep consistent with the PL corpus versioning choice).
- [ ] **AI-assistance disclosure** present (consistent with `AI_USAGE_DISCLOSURE.md`).
- [ ] **Combine-or-split decided** (§8.A) before any deposit is created.

---

## 8. Ambiguities to resolve before publishing

### 8.A — ONE bilingual record vs TWO separate records (DECIDE FIRST)

**The open design question:** should the PL and EN corpora be **(a) two separate Zenodo
records** (two DOIs, mutually `isVariantFormOf` / sibling-linked), or **(b) one bilingual
record** — "Clinical SmPC AWQ Calibration Corpus (PL + EN)" — with one DOI covering both
`corpus.jsonl` files?

This is still possible because **the PL corpus Zenodo record is an unpublished draft**
(record 20520407 on the owner's Desktop, no minted DOI). Once either is published the DOI
is permanent and merging becomes impractical.

- **(a) Two records — pros:** independent versioning per language; each language citable
  on its own; cleaner `language` metadata (`pol` vs `eng`); each can evolve/refresh
  independently. **Cons:** two DOIs to maintain; the PL/EN relationship lives only in
  `related_identifiers`; slightly more citation-graph bookkeeping.
- **(b) One bilingual record — pros:** a single citable "PL+EN calibration corpus" object
  that directly expresses the controlled bilingual pair (the actual research contribution
  for cross-lingual calibration); one DOI; one rights statement. **Cons:** Zenodo
  `language` becomes multi-valued (`[pol, eng]`); a refresh of one language re-versions
  the whole record; less granular per-language citation.

**Recommendation (Claude, for the owner to decide):** lean **(b) one bilingual record** —
the scientific contribution is precisely the *controlled PL/EN pair over identical
medicines*, and a single bilingual deposit expresses that better than two loosely-linked
records; Zenodo supports multi-valued `language`. Choose **(a)** only if you expect the
two languages to be refreshed/versioned on independent schedules. **This draft is written
for option (a) (separate EN record); if you pick (b), fold this EN abstract + the PL
abstract into one record, set `language = [pol, eng]`, upload both `corpus.jsonl` files
under distinct names (e.g. `corpus.pl.jsonl` / `corpus.en.jsonl`), and drop the mutual
`isVariantFormOf` rows (they become one object).** Owner decides.

### 8.B — other ambiguities

1. **Licence string `other-at` vs `other`.** This draft uses `other-at` (legacy Zenodo
   rejects bare `other`). The PL `.json` currently says `other` — **reconcile both to
   `other-at`** (or to the new-Zenodo custom-licence equivalent) so the sibling records
   match.
2. **HF mirror relation — `isIdenticalTo` vs `isVariantFormOf`.** Drafted `isIdenticalTo`
   for the EN HF dataset (same bytes, verified SHA-256). Conservative alternative
   `isVariantFormOf` if you want to hedge future divergence.
3. **PL-corpus relation identifier.** Drafted as the PL **HF dataset URL** with
   `isVariantFormOf`. If/when the PL corpus gets its own Zenodo DOI (or if you pick the
   one-bilingual-record option), update this row accordingly.
4. **`version` number.** Drafted `1.0.0`; keep aligned with whatever the PL corpus uses.
5. **File bundle scope.** Confirm whether to include scripts + RUNBOOK + manifest +
   LICENSE (recommended for reproducibility) or `corpus.jsonl` alone. `epar_raw/` (EMA
   source PDFs) is excluded by design.
6. **`publication_date`.** Drafted `2026-06-06`; set to the actual deposit date.
7. **Reciprocal links post-mint.** After minting, consider adding `isSupplementedBy`
   (this dataset DOI) on the navimed v0.3.0 / v0.4.0 Zenodo records and on the HF dataset
   card so the citation graph is bidirectional. (Owner action post-mint.)

---

## 9. Exact next step to create the draft

This draft makes **no** API calls and performs **no** uploads or deposits. To create the
Zenodo deposition the owner does one of the following (after deciding §8.A).

### Option A — Zenodo UI (recommended for first review)

1. zenodo.org → **New upload**.
2. Upload files: `corpus.jsonl` (+ recommended bundle from the §7 checklist).
3. Set **Upload type = Dataset**.
4. Paste **Title**, **Creators** (name + ORCID + affiliation), **Description** (§2),
   **Keywords** (§3).
5. **License**: set to **"Other (attribution)" / `other-at`**; paste the §4 rights
   statement into the Description.
6. **Language**: `en` / English (`eng`).
7. **Related/alternate identifiers**: add the six rows from §5 with their relation types.
8. **Save** as draft → run the §7 checklist → **Publish** only after §8 is resolved.

### Option B — REST API (after a personal access token is created)

The companion `zenodo-draft.json` is the `POST /api/deposit/depositions` body. Typical
flow (owner runs this; **NOT executed here**):

```bash
# 1. Create the empty deposition with metadata
curl -s -X POST "https://zenodo.org/api/deposit/depositions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ZENODO_TOKEN" \
  --data @zenodo-draft.json
# → response contains the deposition id and a "bucket" upload URL

# 2. Upload the corpus file to the bucket (repeat per file)
curl -s -X PUT "<bucket_url>/corpus.jsonl" \
  -H "Authorization: Bearer $ZENODO_TOKEN" \
  --upload-file calibration/clinical-en/corpus.jsonl

# 3. Review the draft in the Zenodo UI, then publish:
curl -s -X POST "https://zenodo.org/api/deposit/depositions/<id>/actions/publish" \
  -H "Authorization: Bearer $ZENODO_TOKEN"
```

> The JSON payload wraps everything under a top-level `"metadata"` key (what the
> deposition endpoint expects). `publication_date`, `version`, `language` (`eng`) and
> `related_identifiers` are all included. Sandbox (`sandbox.zenodo.org`) is available for
> a dry run before the real DOI is minted.

---

## 10. Source files this draft was built from (ground truth)

- `/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/calibration/clinical-en/corpus.jsonl` (412 lines; SHA-256 `820b7a4de75f20baddf3d89fa73a3d8f348ae22086f1ed52f0278ec6040aac85`)
- `/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/calibration/clinical-en/manifest.json` (61 medicines, brand → EPAR slug)
- `/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/calibration/clinical-en/README.md` + `RUNBOOK.md` (verified corpus docs)
- `/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/calibration/LICENSE`
- `/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/CITATION.cff` (author / ORCID / affiliation)
- HuggingFace dataset `mozarcik/clinical-en-smpc-awq-calibration` (PUBLIC; uploaded 2026-06-06, commit `a898b946`)
- `~/Pulpit/navimed-zenodo-corpus-draft.{md,json}` (the PL corpus draft this EN draft mirrors)
- `RELEASES.md` (navimed DOI provenance: 19851346 / 20317011 / 20364953)
