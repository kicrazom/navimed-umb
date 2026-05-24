# eval-rag — RAG benchmark of Polish vs multilingual LLMs on clinical SmPC text

**Status:** design — awaiting reviewer responses (proposed: Adam Białas, Jakub Radliński). No measurements yet.
**Opened:** 2026-05-24
**Lead:** Łukasz Minarowski (UMB, ORCID 0000-0002-2536-3508)
**Embargo:** §11.1 (this design doc) PUBLIC; future generation outputs + per-question scores will be classified per artifact when they exist (faithfulness/safety scores ≠ throughput numbers, but reviewer-attributed scores may carry attribution + IRB considerations).

---

## 1. Scope and rationale

Phase 2 throughput sweep (Gate 3, EMBARGOED §11.2/§11.3) measures **inference-stack envelope** — how many tok/s, what KV cache, what thermals. By METHODOLOGY §8 it deliberately does **not** measure **model quality**: faithfulness to source text, hallucination rate, correctness of clinical content. That boundary is intentional.

But the same release that just put `mozarcik/Llama-PLLuM-70B-{base,instruct,chat}-{2412,2508,2512}-awq` on HuggingFace (cf. `RELEASES.md` 2026-05-23) raises a different, practical question that **is** within the project's scope but **outside** §8:

> *Given that PLLuM-70B AWQ fits on consumer 2× R9700 — does it actually answer Polish clinical-regulatory questions (SmPC / ChPL) better than the smaller PL-native Bielik, or the larger multilingual Mistral / Qwen? And by how much, on which categories of question?*

This is a **model-quality evaluation**, not an inference-stack benchmark. It needs different methodology, different metrics, different gates. This folder holds the design.

If we publish, the natural venues are the ones where Łukasz already has standing — *Advances in Medical Sciences* (ADVMS, editor/reviewer), *PeerJ* (reviewer), *Therapeutic Advances in Respiratory Research* (Sage, associate editor). PTChP guideline channel (*Advances in Respiratory Medicine*) is also a natural fit given the SmPC + pulmonology domain.

---

## 2. Models under test (5)

| Model | Quant | Footprint | TP on 2× R9700 |
|---|---|---|---|
| `bielik-11b-v30-instruct-awq` | AWQ W4A16 | ~6 GB | 1 (GPU0) |
| `bielik-45b-v30` | BF16 | ~25 GB | 1 or 2 |
| `Llama-PLLuM-70B-instruct-2512-awq` | AWQ W4A16 | ~38 GB | 2 (mandatory) |
| `mistral-nemo-instruct-2407` | BF16 | ~24 GB | 1 or 2 |
| `qwen36-27b-fp8` | FP8 | ~27 GB | 1 |

This spans:
- **2 Polish-trained sizes** (Bielik 11B, Bielik 45B) — PL-native, smaller
- **1 Polish-trained large** (PLLuM 70B AWQ) — PL-native, large, this is what we just released
- **2 multilingual references** (Mistral-Nemo 12B, Qwen3.6 27B FP8) — best-in-class multilingual at comparable footprints

Choosing AWQ for two of the five (Bielik 11B and PLLuM 70B) keeps the comparison anchored in the **actual deployable configuration** for the target hardware (2× R9700, gfx1201, METHODOLOGY §4).

---

## 3. Corpus

[`mozarcik/clinical-pl-smpc-awq-calibration`](https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration) — 418 fragments of Polish *Charakterystyka Produktu Leczniczego* (ChPL / SmPC) text from EMA, mean ~512 tokens per fragment, covering 81 INNs and 9 NFZ drug programmes (pulmonology + thoracic oncology focus). Per-fragment provenance schema (`source_url`, `medicine`, `brand_name`, `chunk_id`, `license_note`). No PHI.

Already published as part of the 2026-05-23 release; reusable as the retrieval corpus for this evaluation without any additional data work.

---

## 4. Question set (50)

Designed to span the categories that matter most in a clinical decision-support context, weighted toward the questions where **getting it wrong is unsafe** (dosing, interactions, contraindications):

| Category | N | Example shape |
|---|---|---|
| Dosing and dose modifications (renal, hepatic, elderly) | 10 | "How is tiotropium dosed in a patient with GFR < 30?" |
| Drug-drug interactions | 10 | "Is concurrent omalizumab and X contraindicated?" |
| Contraindications | 8 | "What are the absolute contraindications to nintedanib?" |
| Adverse drug reactions (frequency, severity, management) | 8 | "Common vs serious ADRs of aclidinium?" |
| Mechanism of action (short definition) | 6 | "Mechanism of pembrolizumab in NSCLC?" |
| Monitoring requirements and safety parameters | 5 | "What to monitor when starting ozetekimab?" |
| Reimbursement eligibility (NFZ programmes) | 3 | "Eligibility criteria for programme B.31?" |

Composition designed with Białas (PTChP guideline author — overlap with our corpus on inhaled ICS/LABA/LAMA + antifibrotics in IPAF). The 5–7 questions touching on lung-function testing and PSG-adjacent monitoring are the natural reviewer subset for Radliński (IGiChP Rabka-Zdrój — spirometry methodology).

---

## 5. Retrieval

**Hybrid BM25 + dense-embedding with Reciprocal Rank Fusion (RRF), k=3 chunks per question.**

- BM25 — `rank_bm25` over the 418 fragments tokenized with a Polish-aware tokenizer (preserve diacritics, lowercase, light stopwords). Deterministic, fast, lexical baseline that captures INN names and named entities cleanly.
- Dense — `intfloat/multilingual-e5-large` (Polish-capable, well-validated) served via `sentence-transformers` on GPU0 as a side process; chunk embeddings precomputed once and cached as `.npy`.
- Fusion — standard RRF (`k=60` constant) over the two rankings, take top 3.

This is the 2026 state-of-the-art baseline for clinical RAG; not novel but defensible.

---

## 6. Generation

Each model is served sequentially via vLLM with the navimed `_env.sh` stack:

- `--temperature 0.2`, `--max-tokens 512`
- Prompt template (Polish): system message defines role ("Jesteś polskim ekspertem klinicznym — odpowiadasz wyłącznie na podstawie dostarczonych fragmentów ChPL. Jeśli odpowiedź nie wynika z fragmentów, napisz „Brak informacji w dostarczonym materiale"."), user message injects retrieved chunks then the question.
- For base / non-chat-template variants (none in this set, but checked) — fall back to `/v1/completions` per the harness lesson from Gate 1.
- Output: `answers/<model>/q<id>.json` with `question`, `retrieved_chunks`, `answer`, `latency_ms`, `prompt_tokens`, `completion_tokens`.

**Embargo on generation artifacts:** the answer text itself is not throughput-sensitive (§11.2 covers tok/s, not generated content) — but **reviewer-attributed scores** carry attribution and possibly IRB-relevant considerations, so the scored CSV will be embargoed by default until publication.

---

## 7. Evaluation — 5-pt manual review across 4 axes, 3 reviewers

Per `(question, model_answer, reviewer)`:

| Axis | 1 | 5 |
|---|---|---|
| **Faithfulness** | Full hallucination, not in context | Exact citation of context |
| **Completeness** | Misses key information | Covers all required points |
| **Safety / clinical correctness** | Dangerous error (e.g. wrong dose, missed interaction) | Safe and correct |
| **Polish medical style** | Broken Polish or English calques | Natural medical Polish |

Reviewers (proposed):
- **Łukasz Minarowski** (UMB pulmonology, ORCID 0000-0002-2536-3508) — full 50 × 5 = 250 answers
- **Adam Białas** (UM Łódź, dr hab., 66+ PubMed, PTChP guideline first-author, ORCID 0000-0002-3501-167X) — full 50 × 5 = 250 answers; **also** co-design of the 50-question set
- **Jakub Radliński** (IGiChP Rabka-Zdrój, dr n. tech., spirometry/PSG, ORCID 0000-0001-7087-393X) — **subset** of ~10–15 questions × 5 models = ~50–75 answers, focused on the lung-function / monitoring axis where his expertise is differential

Cohen's κ between reviewer pairs on the overlap; full 3-way agreement on the questions all three review (15 × 5 = 75 paired observations).

---

## 8. Pre-flight

Before any generation:

- **B3 sweep must complete** (frees GPU). In progress, ETA ~08:30 today.
- **Reviewer commitment** from Białas (essential — co-design of Q set) and Radliński (subset reviewer). See `outreach/`.
- **Corpus embeddings precomputed** — one-off ~10 min on R9700.
- **Hybrid retriever validated** on a sanity question with known-good chunk — sanity check before bulk generation.
- **Pre-registered analysis plan** committed to this folder before any reviewer sees any answer (avoid HARKing per METHODOLOGY §6 spirit).

---

## 9. Status today

Locked design decisions (2026-05-24 morning, with Łukasz):

| Decision | Value |
|---|---|
| Number of models | 5 |
| Retrieval | Hybrid BM25 + e5-multilingual + RRF |
| Metric | 5-pt × 4 axes × 3 reviewers |
| Goal | Hybrid: internal sanity, then paper |
| Embargo | This design doc PUBLIC §11.1; future generated answers + scored CSV embargoed by default until publication |
| Folder | `10_Projekty/0001-navimed-umb/eval-rag/` (sub-project under navimed v0.3.0; no separate DOI for now) |

Blocked on:

| Block | Action | ETA |
|---|---|---|
| Białas response | Łukasz to send outreach email (draft in `outreach/email-bialas-pl.md`) | reviewer-bound |
| Radliński response | Łukasz to send outreach email (draft in `outreach/email-radlinski-pl.md`) | reviewer-bound |
| Q set | Co-design with Białas; if Białas declines, fallback to LLM-assisted + Łukasz review (internal-only, no paper) | post-response |

Fallback policy: 4 weeks no-response → second-tier reviewers (Piotrowski WJ as Białas's mentor at UM Łódź; Kupczyk M).

---

## 10. Related artifacts

- `mozarcik/clinical-pl-smpc-awq-calibration` — the corpus (HuggingFace dataset, published 2026-05-21)
- `mozarcik/Llama-PLLuM-70B-instruct-2512-awq` — one of the models under test (HuggingFace, published 2026-05-23)
- `navimed-umb` repository — METHODOLOGY for the inference-stack benchmark this evaluation is methodologically distinct from but practically built on top of
- `logbook/2026-05-23.md`, `logbook/2026-05-24.md` — release + Phase 2 sweep narrative
- `docs/sessions/2026-05-23-pllum-awq-release-pipeline.md` — full release session log
- Memory: `~/.claude/projects/-home-mozarcik-Vaults-main/memory/project_pllum_rag_eval_open.md`
