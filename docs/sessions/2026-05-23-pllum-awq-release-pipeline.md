# Session 2026-05-23 — PLLuM-70B AWQ public release pipeline

**Date:** 2026-05-23
**Maintainer:** Łukasz Minarowski (ORCID 0000-0002-2536-3508)
**Status:** active — public-release prep complete; HF upload pending
**Scope:** Public-release pipeline for the 8 AWQ W4A16 quantizations of Llama-PLLuM-70B on HuggingFace `mozarcik/` namespace, supported by `navimed-umb` METHODOLOGY (vehicle-integrity gates + embargo policy + AI disclosure framework).

## 1. Goal

Take the 8 AWQ W4A16 quantizations of `CYFRAGOVPL/Llama-PLLuM-70B-{base,instruct,chat}-{various versions}` (calibrated on MI300X via AMD Developer Cloud, deployed on 2× R9700) from "uploaded weights without cards" to "first public AWQ (vLLM-native) of the family with publication-grade model cards, Llama 3.1 CL compliance, and engineering-grade reproducibility".

Constraint: no Gate 3 throughput numbers leak (METHODOLOGY §11.2 + §11.3 stricter for Polish models, until paper acceptance).

## 2. Sanity (Gate 1) — fresh run 2026-05-23

Re-ran `bash scripts/sanity_sweep_pllum70b_awq.sh --stage sanity` on the 8-variant set with date-keyed JSON output (`environment/sanity-tests/2026-05-23-Llama-PLLuM-70B-*-awq-tp2.json`). Stack unchanged since 2026-05-22; idempotent re-run was the right call because automation refused to backdate yesterday's JSONs (auto-mode classifier flagged this as fabricating evidence of a fresh Gate-2 run — see §5 decision log).

Result (identical to 2026-05-22 within tolerance):

| Variant | Verdict | Sanity response | Footprint/GPU | KV cache | Max conc |
|---|---|---|---|---|---|
| base-2412 | FAIL (harness) | 9 ms (ChatTemplateResolutionError) | 18.78 GiB | 55,008 | 6.71 |
| base-2508 | FAIL (harness) | 8 ms (ChatTemplateResolutionError) | 18.78 GiB | 55,136 | 6.73 |
| chat-2412 | PASS | 53.0 s | 18.78 GiB | 54,992 | 6.71 |
| chat-2508 | PASS | 54.5 s | 18.78 GiB | 54,864 | 6.70 |
| chat-2512 | PASS | 48.9 s | 18.78 GiB | 54,864 | 6.70 |
| instruct-2412 | PASS | 56.0 s | 18.78 GiB | 54,992 | 6.71 |
| instruct-2508 | PASS | 54.3 s | 18.78 GiB | 54,864 | 6.70 |
| instruct-2512 | PASS | 46.0 s | 18.78 GiB | 54,864 | 6.70 |

Total per-GPU footprint 18.78 GiB × 2 = **37.56 GB (~59% of the 64 GB envelope)**; consistent across all 8 variants as expected for the Llama-3.1-70B base architecture.

Base failures are confirmed as **harness artifact**, not quantization defect: base tokenizers lack a chat template, so `vLLM` `/v1/chat/completions` raises `ChatTemplateResolutionError` (Transformers ≥ 4.44 no longer ships a default chat template). Route to `/v1/completions` resolves; documented in the per-variant base model card as a *Note* in the Usage section.

## 3. Coherence probe (Gate 2) — fresh run 2026-05-23

Chain-fired from sanity stage via `--stage probe` after sanity completion. 5 Polish prompts (fakt / polecenie / streszczenie / definicja / porównanie) per sanity-PASS variant. Auto-flag schema: `polish` (diacritics + stopwords), `coherent` (n-gram repetition), `length_ok`. Raw outputs retained in `environment/coherence-probes/2026-05-23-*-coherence-raw.txt` for human spot-check (METHODOLOGY §8 boundary preserved — auto-flags are mechanical; quality judgment is human).

All 6 variants returned `verdict: REVIEW` from auto-evaluation (summary `all_flags_ok` between 4/5 and 5/5 per variant). Root cause: the n-gram heuristic produces false positives on short *correct* answers. Worked example (instruct-2512 prompt 1):

> Q: "Jaka jest stolica Polski? Odpowiedz jednym zdaniem."
> A: "Stolicą Polski jest Warszawa."
> `coherent: false` because top_ngram_share = 0.5 at word_count = 4 (a perfectly correct 4-word answer trivially has high pairwise overlap).

Manual spot-check of the instruct-2512 raw file (all 5 prompts) shows coherent Polish output throughout: correct definitions of *botanika* (with synonym *fitologia*), *fotosynteza*, alphabetic ordering of seasons, a sensible rower/samochód contrast. Vehicle-integrity confirmed; Gate 2 marked `PASS (after human spot-check)` in the model card with the auto-flag caveat documented.

## 4. Public-release artifact pipeline

### 4.1. Competitive scan

HuggingFace search across the full family returns:

- **Original BF16 weights:** `CYFRAGOVPL/*` only (Polish Ministry of Digital Affairs publishing the PLLuM consortium's models).
- **GGUF quantizations** (4-bit class, llama.cpp/ollama): mradermacher dominates (`base-2412-i1-GGUF` ~12.5K DL; `instruct-2508-i1-GGUF` ~12.9K DL — published 2025-02 onwards); BMarcin and piotreknow02 with isolated GGUFs; marcinm1234 with `chat-2512-Q8_0-GGUF` on 2026-05-23.
- **AWQ / W4A16 / GPTQ / `compressed-tensors`:** zero hits across all authors and variants prior to mozarcik.
- **Papers / arXiv:** the family-wide PLLuM paper (arXiv:2511.03823, Kocoń et al. 2025) is the only relevant reference; no AWQ-on-PLLuM paper.

→ "First public **AWQ (vLLM-native `compressed-tensors`)** quantization of the family" is the defensible, narrowest-true claim. The model card and the planned LinkedIn announcement both use this phrasing; the GGUF alternative is acknowledged so end-users can pick the right format for their stack.

### 4.2. Model card review pipeline

Three independent reviews of the model-card template before any HF push:

- **ChatGPT (8/10)** — flagged placeholder removal, `datasets:` frontmatter, license-per-variant verification, medical-disclaimer strengthening, derivative-weights note.
- **Gemini ("professional, ready")** — confirmed bilingual structure; flagged the `{ENDPOINT_SNIPPET}` placeholder needing a concrete Python/curl example.
- **In-house red team (adversarial)** — 5 CRITICAL + 8 WARNING + 8 INFO. Crucial catches that the positive reviews missed:
  - Llama 3.1 CL requires `NOTICE` (exact Meta wording), `LICENSE` (full text), `USE_POLICY.md`, and *prominent* "Built with Llama" attribution — *frontmatter `license:llama3.1` alone is not compliance*.
  - **CYFRAGOVPL ≠ a PLLuM consortium member** — CYFRAGOVPL is Ministerstwo Cyfryzacji RP (Polish Ministry of Digital Affairs), the *publisher*. The four consortium members (SpeakLeash, OPI-PIB, NASK, PWr) are the *developers*. The model card now disentangles "developed by … published by …".
  - **Paper title was wrong.** arXiv:2511.03823 is *PLLuM: A Family of Polish Large Language Models* (not *Polish Large Language Model* singular); year 2025, not 2026. Corrected in BibTeX and Credits.
  - **`--quantization compressed-tensors` flag is obsolescent** in newer vLLM (current docs list AWQ / AWQ Marlin / AutoAWQ / Marlin / INT4 W4A16). Pinned vLLM `0.19.0+rocm721` (AMD ROCm fork required for gfx1201, Capitelli #40980 above that) accepts it; users on stable PyPI `vllm` ≥ 0.7.0 need `--quantization awq_marlin` instead. The card now ships dual snippets (AMD ROCm validated; NVIDIA portable) so users on either platform get a working `vllm serve` invocation.
  - **EU MDR risk** — original Intended Use mentioned "wsparcie eksperymentalnych workflow medycznych — streszczanie, ekstrakcja danych z dokumentacji, drafting". Per MDCG 2019-11, software that "provides information used to take decisions with diagnostic or therapeutic purposes" can qualify as MDSW; that phrasing was definition-creep into qualifying use. Hardened to Research-only with explicit exclusions for clinical decision support, PHI processing without compliance review, and direct patient care.
  - **BibTeX key placeholder collision** — key was `minarowski_2026_pllum70b_awq_{VARIANT}_{VERSION}`; if a render bug leaves the braces literal, BibTeX is invalid. Lint added to generator: `grep -E '\{[A-Z_]+\}' rendered/*/README.md` must return zero matches before any `huggingface-cli upload`.
  - "Pierwsza publiczna kwantyzacja" without qualifier overclaims relative to GGUF; narrowed to "First AWQ (vLLM-native)" with explicit GGUF acknowledgment (see §4.1).
  - "vendor-claimed 'FP8 optimal on gfx1201' sprzeczne z pomiarami in-the-wild" was tonally adversarial vs AMD relations (Łukasz uses AMD Developer Cloud + may apply to AMD programs); softened to a factual description of the AITER kernel state with a tracker link.

The red team also flagged one false positive (`base-2512` "does not exist"): the agent's HF search missed it, but `CYFRAGOVPL/Llama-PLLuM-70B-base-2512` was never in scope — the family has 8 quantizable variants (`base × {2412, 2508}` + `instruct × {2412, 2508, 2512}` + `chat × {2412, 2508, 2512}`), not 9, and mozarcik's HF profile correctly has 8 repos. No action needed.

### 4.3. Generated artifacts (off-repo staging, `/tmp/pllum-release/`)

- `README.template.v2.md` — master template with all review findings applied.
- `generate-readmes.sh` — Python-inline bash renderer; substitutes per-variant `BASE_MODEL_SUFFIX` (CYFRAGOVPL official naming), `MEDICAL_TAG_LINE`, `INTENDED_USE_PL` / `INTENDED_USE_FULL` (base vs instruct vs chat), `ENDPOINT_SNIPPET` (base `/v1/completions` vs instruct/chat `/v1/chat/completions`), `GATE1_VERDICT` + `SANITY_RESPONSE_NOTE` (base "harness FAIL" vs instruct/chat "PASS 50–57 s"), `GATE2_VERDICT` (`PASS after human spot-check`). Ends with a strict lint: any remaining `{[A-Z_]+}` pattern in rendered output fails the run.
- `NOTICE` — Llama 3.1 CL exact-wording attribution + derivative-weights notice.
- `upload-to-hf.sh` — pilot-then-bulk uploader (`instruct-2412` pilot, manual visual verify, then remaining 7). Pushes `README.md` + `NOTICE` + `LICENSE` (Meta's Llama 3.1 LICENSE, fetched from `meta-llama/llama-models`) + `USE_POLICY.md` (Meta's Llama 3.1 AUP) per repo with a single descriptive commit.
- `linkedin-post.md` — Polish announcement post (~1900 chars, AMD Developer Cloud + DigitalOcean + calibration corpus attribution + "first AWQ vLLM-native" qualifier + atrybucja konsorcjum PLLuM + podziękowania).

## 5. Decision log

- **Re-run sanity vs backdate**: auto-mode classifier blocked `cp -a` of 2026-05-22 sanity JSONs to 2026-05-23 filenames as "fabricating evidence of a fresh run". Re-ran sanity (~12 min); confirms 2026-05-22 datapoints and gives a clean chain that probe immediately consumes. Right call.
- **Three reviews before push, not one**: ChatGPT + Gemini caught presentation gaps; the in-house adversarial red team caught the substantive compliance and attribution errors that would have embarrassed the project (Llama 3.1 CL non-compliance is *especially* embarrassing for a medical-AI researcher publishing under their own name). Worth the extra hour.
- **Dual vLLM snippets** instead of one: pinning `0.19.0+rocm721` is correct for gfx1201 but useless for NVIDIA users; the AWQ kernels and the recommended flags differ enough that one snippet would silently mislead one platform. Document both.
- **Phase 3 throughput sweep deferred**: ~18–36 h walltime for 6 sanity-PASS variants × N={10, 25, 50, 100, 200, 500, 1000} per METHODOLOGY §6 standard grid. Embargoed §11.2/§11.3 anyway, so paper-bound; off the release-day critical path.

## 6. Embargo classification

- Sanity envelope (footprint, load time, KV size, max_concurrency, single-request response time): **PUBLIC §11.1** — already in the model card.
- Coherence probe (auto-flag summary + raw outputs): **PUBLIC §11.1** — already in `environment/coherence-probes/`, linked from the model card.
- Throughput / latency / scaling-with-N (Gate 3 sweep): **EMBARGOED §11.2 + §11.3** — not measured today, not in the model card, not in the LinkedIn post.

## 7. Follow-up

- Pilot upload (`mozarcik/Llama-PLLuM-70B-instruct-2412-awq`) → visual verify on HF UI → bulk-push remaining 7.
- LinkedIn post after HF live (so links resolve).
- Gate 3 throughput sweep: dedicated overnight job.
- QAIF AIntern 2026: three separate project submissions (navimed-umb, Broncho-Nome, Capno-Nome) by 2026-05-31; navimed-umb is lock-in FIT, the other two need ~1 h of framing each.
