---
type: action-checklist
target: cross-channel
release: v0.4.0
created: 2026-05-27
status: ready-to-execute
parent_review: docs/visibility/2026-05-26-consistency-review.md
estimated_walltime: ~35 min (Zenodo ~20 min + RG ~10 min + HF dataset ~5 min)
operator: Łukasz Minarowski (manual — Claude cannot auth Zenodo/RG/HF UI)
---

# CRIT action checklist — manual edits (Łukasz, ~35 min)

> Paste-ready, no further preparation needed. GH-side fixes are already
> committed (66d5a85 README, 2178b69 disclosure, da9b45b zenodo.json) —
> this checklist covers only the four external channels.

---

## 1. Zenodo v0.4.0 record 20364953 (~10 min) — clears CRIT-2 + CRIT-3

**URL:** https://zenodo.org/records/20364953 → click **Edit**

### 1.1 Description field — REPLACE entire content

Paste the HTML block from `docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md` lines 38–56
(starts `<p>NaviMed-UMB v0.4.0 widens…`, ends `…in the repository.</p>`).

Verify after save: description now mentions Run-3 (8B + 12B AWQ), 70B family, 418-fragment
calibration corpus, embargo §11.1/§11.2/§11.3 split, four-paper roadmap.

### 1.2 Related identifiers — ADD these five rows

(Currently only the GitHub URL is listed.)

| identifier | relation | scheme |
|---|---|---|
| `https://github.com/kicrazom/navimed-umb` | is supplement to | url |
| `10.5281/zenodo.20317011` | **is new version of** | doi |
| `https://huggingface.co/mozarcik/Llama-PLLuM-8B-chat-2512-awq` | is supplemented by | url |
| `https://huggingface.co/mozarcik/PLLuM-12B-chat-2512-awq` | is supplemented by | url |
| `https://huggingface.co/mozarcik/clinical-pl-smpc-awq-calibration` | is referenced by | url |

The `isNewVersionOf` row (DOI 20317011) is the **CRIT-3 fix** — it restores the version
chain. Zenodo should auto-create the reciprocal `isPreviousVersionOf` on the v0.3.0
side once you save here.

### 1.3 Save and verify

- "Versions" sidebar now shows v0.3.0 → v0.4.0 chain ✓
- Description renders the new content (not the v0.1-era Qwen boilerplate) ✓
- All 5 related-identifier rows visible ✓

---

## 2. Zenodo v0.3.0 record 20317011 (~10 min) — clears CRIT-1

**URL:** https://zenodo.org/records/20317011 → click **Edit**

### 2.1 Description — APPEND (do not replace) this paragraph

Keep the original first paragraph for historical continuity. Append at the end:

```
Between-version event under v0.3.0 (2026-05-23): public release of the first AWQ W4A16
(vLLM-native compressed-tensors) quantization of the Llama-PLLuM-70B family, to the
author's knowledge. Eight model cards on HuggingFace under mozarcik/
(base × {2412, 2508} + instruct × {2412, 2508, 2512} + chat × {2412, 2508, 2512}),
each with Llama 3.1 Community License compliance artifacts (LICENSE, NOTICE with exact
Meta wording, USE_POLICY.md), dual-platform vLLM usage snippets (AMD ROCm validated;
NVIDIA portable via awq_marlin), Gate 1 hardware-envelope evidence and Gate 2
coherence-probe evidence. Reusable calibration corpus published separately as
mozarcik/clinical-pl-smpc-awq-calibration (418 fragments of Polish SmPC text from EMA,
~512 tokens each, 81 INNs, 9 NFZ drug programmes, No PHI). Engineering envelope on
2× R9700 (gfx1201, TP=2): 37.56 GB total footprint, ~55,000-token KV cache at
max_seq_len 8192, max_concurrency 6.7 req, junction peak 92–94 °C with ~16 °C headroom.
Per-N throughput, latency, scaling and W/tok numbers remain EMBARGOED under
METHODOLOGY §11.2 (stricter §11.3 for Polish models) pending peer-reviewed publication.
See RELEASES.md 2026-05-23 block in the source repository for the full account.
```

### 2.2 Related identifiers — ADD these two rows

| identifier | relation | scheme |
|---|---|---|
| `https://huggingface.co/mozarcik` | is supplemented by | url |
| `https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration` | is referenced by | url |

### 2.3 Verify the reciprocal version-chain link

After saving step 1.2 on the v0.4.0 record, Zenodo should have auto-populated
`isPreviousVersionOf 10.5281/zenodo.20364953` on this record. If NOT present, add it
manually here.

---

## 3. ResearchGate publication 405205893 (~10 min) — clears CRIT-4

**URL:** https://www.researchgate.net/publication/405205893 (logged in)

### 3.1 Assess current state

- What is the publication title? (slug suggests v0.1-era "hardware envelope studies … RDNA 4 GPUs")
- Which Zenodo DOI is attached?
- Does the AI-assistance disclosure mention Bielik / Gemini, or only Claude + GPT?

### 3.2 Pick option a or b

**Default recommendation: option b** (preserves immutability of any prior citations
pointing to 405205893).

#### Option a — edit in place (faster, ~5 min)

Replace title + abstract + DOI on 405205893 with v0.4.0 content from
`docs/visibility/2026-05-26-researchgate-v0.4.0.md` lines 27–37 (Extended abstract).
Set Zenodo DOI to `10.5281/zenodo.20364953`.

#### Option b — leave 405205893 + create new v0.4.0 item (~10 min, recommended)

1. Leave 405205893 as the v0.1/v0.3.0 historical record.
2. Create a NEW research-item on RG:
   - Title: *NaviMed-UMB v0.4.0 — Technical Report*
   - Item type: Technical Report
   - Description: paste from `docs/visibility/2026-05-26-researchgate-v0.4.0.md` lines 27–37
   - Primary identifier: Zenodo DOI `10.5281/zenodo.20364953`
   - Supplementary URLs: `https://github.com/kicrazom/navimed-umb`, plus the 11 HF model repos
   - AI-disclosure paragraph: paste from `docs/visibility/2026-05-26-researchgate-v0.4.0.md` line 77

### 3.3 Update project-page summary (separate from the publication item)

Update the RG project-page short summary using the 150–200-word abstract at
`docs/visibility/2026-05-26-researchgate-v0.4.0.md` lines 23–25. This is the surface
international peer-reviewers see first.

---

## 4. HuggingFace dataset card (~5 min) — clears HF-D-1 (major, not critical)

**URL:** https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration/edit/main/README.md

### 4.1 Find the line (currently around line 20)

```
Used to calibrate the `mozarcik/Llama-PLLuM-70B-*-awq` model series, produced on the
AMD Developer Cloud (Instinct MI300X).
```

### 4.2 Replace with

```
Used to calibrate the `mozarcik/Llama-PLLuM-70B-*-awq` family (8 variants, AMD
Developer Cloud / Instinct MI300X, 2026-05-23) and the
`mozarcik/Llama-PLLuM-8B-chat-2512-awq` + `mozarcik/PLLuM-12B-chat-2512-awq` Run-3
consumer-GPU variants (local 2× R9700, 2026-05-26).
```

Commit message on HF: `docs: extend calibration usage to include Run-3 consumer-GPU variants`

---

## 5. Cross-channel sanity check (~3 min) after all edits land

1. **DOI trace test.** Open each, verify destination matches the channel's claim:
   - HF card `mozarcik/Llama-PLLuM-70B-instruct-2512-awq` → DOI 20317011 → Zenodo v0.3.0 description now mentions the 70B AWQ release ✓
   - GitHub README "current version v0.4.0" → DOI 20364953 → Zenodo v0.4.0 description now mentions Run-3 + 70B family + four-paper roadmap ✓
   - Concept DOI 19851346 → latest-version banner says **v0.4.0** (not v0.3.0)
2. **Version-chain test.** On Zenodo v0.4.0 page, "Versions" sidebar shows v0.3.0 → v0.4.0 chain.
3. **HF dataset back-reference test.** On `mozarcik/clinical-pl-smpc-awq-calibration` page, the "Models trained or fine-tuned on this dataset" panel lists ≥10 model repos. If any are missing, the corresponding model card frontmatter needs `datasets: - mozarcik/clinical-pl-smpc-awq-calibration` added.

---

## Done state — when all five blocks tick green

CRIT-1 ✓ (v0.3.0 description includes 70B between-version paragraph)
CRIT-2 ✓ (v0.4.0 description matches the v0.4.0 release content)
CRIT-3 ✓ (v0.3.0 ↔ v0.4.0 version chain restored)
CRIT-4 ✓ (RG carries a v0.4.0 surface, not just v0.1-era)
HF-D-1 ✓ (dataset card reflects both Run-2 and Run-3 downstream use)

Update `docs/visibility/2026-05-26-consistency-review.md` Section 7 "Summary by severity"
table to reflect 0 CRIT open after this pass. Or simpler: add a "## 8. Resolution"
section at the bottom of the review.
