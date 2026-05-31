---
type: visibility-review
target: cross-channel
release: v0.4.0
created: 2026-05-26
status: ready-for-action
reviewer: Claude Opus 4.7 (Vaults-main agent session)
scope: |
  Cross-system consistency review of the NaviMed-UMB v0.4.0 release surface across
  four publication channels: GitHub repo (`kicrazom/navimed-umb`), HuggingFace
  (11 model repos + 1 dataset under `mozarcik/`), Zenodo (v0.3.0 record 20317011 +
  v0.4.0 record 20364953 + concept DOI 19851346), and ResearchGate publication
  405205893. Numbers, dates, license claims, attributions, AI-assistance disclosure,
  embargo discipline (METHODOLOGY §11), three-layer signaling (L1/L2/L3 post-2026-05-24),
  and version chain (Zenodo isNewVersionOf).
sources:
  - /home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/README.md
  - /home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/RELEASES.md
  - /home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/METHODOLOGY.md
  - /home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/.zenodo.json
  - /home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/AI_USAGE_DISCLOSURE.md
  - /home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/paper/paper-1-results-outline.md
  - /home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/logbook/2026-05-23.md
  - /home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/logbook/2026-05-24.md
  - /home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/logbook/2026-05-26.md
  - /home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/docs/sessions/2026-05-23-pllum-awq-release-pipeline.md
  - /home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/eval-rag/README.md
  - HF model cards: mozarcik/Llama-PLLuM-70B-{base,instruct,chat}-{2412,2508,2512}-awq (9 cards)
  - HF model cards: mozarcik/Llama-PLLuM-8B-chat-2512-awq, mozarcik/PLLuM-12B-chat-2512-awq
  - HF dataset card: mozarcik/clinical-pl-smpc-awq-calibration
  - Zenodo records: 20317011 (v0.3.0), 20364953 (v0.4.0), concept 19851346
  - GitHub Releases v0.1.0..v0.4.0 (via `gh release view`)
  - ResearchGate publication 405205893 — BLOCKED (HTTP 403 + Cloudflare 1020) — see Łukasz manual checklist
---

# Cross-channel consistency review — NaviMed-UMB v0.4.0 (2026-05-26)

> **Halucynacja-watch on the reviewer:** every finding below is sourced (file:line for local, URL for HF/Zenodo/GH). Where the source channel could not be retrieved, the row is flagged `[UNVERIFIED]` with the reason. ResearchGate was blocked at both `WebFetch` (HTTP 403) and `curl` (Cloudflare 1020); RG-side findings are derived from the local visibility draft only, NOT from the live RG page, and explicitly flagged.

---

## 0. Channel inventory and snapshot

| Channel | Identifier | Last-touched | State at review time |
|---|---|---|---|
| GitHub releases | `kicrazom/navimed-umb` | v0.4.0 published 2026-05-24 11:01 UTC | tag v0.4.0 latest; README current (v0.4.0 banner); RELEASES.md includes 2026-05-26 between-version Run-3 block |
| GitHub default branch (README.md) | README badge | DOI badge points to **concept DOI 19851346** ✓ | OK |
| HF — 70B family (9 cards) | `mozarcik/Llama-PLLuM-70B-{base,instruct,chat}-{2412,2508,2512}-awq` | all 9 updated 2026-05-23 | model-card text references `navimed-umb/tree/v0.3.0/...` and cites version DOI 20317011 — stale but pre-decision (see Observations §3) |
| HF — Run-3 (2 cards) | `mozarcik/Llama-PLLuM-8B-chat-2512-awq`, `mozarcik/PLLuM-12B-chat-2512-awq` | both updated 2026-05-26 | reference `navimed-umb/tree/v0.4.0/...` and cite concept DOI 19851346 ✓ |
| HF — dataset | `mozarcik/clinical-pl-smpc-awq-calibration` | updated 2026-05-21 | references 70B family only; no mention of Run-3 reuse — see §2.HF-D-1 |
| Zenodo v0.3.0 | DOI `10.5281/zenodo.20317011` | published 2026-05-20 | Description is v0.1-era Qwen 3.6 27B text; does not mention Llama-PLLuM-70B AWQ release (under v0.3.0 as a between-version event) — see §1.CRIT-1 |
| Zenodo v0.4.0 | DOI `10.5281/zenodo.20364953` | published 2026-05-24 | Description is **identical** to v0.3.0 (v0.1-era boilerplate from `.zenodo.json`). NO mention of Run-3, 70B family, 418 fragments, embargo classification, or version-chain link. Manual override draft exists at `docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md` but not yet applied — see §1.CRIT-2 |
| Zenodo concept DOI | `10.5281/zenodo.19851346` | always-latest auto-redirect | OK, used consistently across channels |
| ResearchGate | publication `405205893` | unknown — `[UNVERIFIED]` HTTP 403/1020 | NOT independently fetched; treat all RG-side claims in this review as derived from the visibility draft, not from live RG state |

---

## 1. Critical fixes needed

### CRIT-1 — Zenodo v0.3.0 (20317011) description does not mention the v0.3.0-era PLLuM-70B AWQ release

**Channel:** Zenodo record 20317011 (`https://zenodo.org/records/20317011`)

**Current description (verbatim, fetched 2026-05-26):**
> "An engineering log and reproducible benchmark suite documenting the practical envelope of running modern open-weight large language models on a consumer-grade dual AMD Radeon AI PRO R9700 32 GB workstation (gfx1201, RDNA 4 / Navi 48) under ROCm 7.2 and vLLM 0.19. The repository includes the v0.1 hardware-envelope preprint on Qwen 3.6 27B (FP8 vs BF16, CUDA-graph and FP8-kernel findings), METHODOLOGY.md — a reproducible benchmark protocol — per-model software/hardware environment manifests, and aggregated benchmark summaries. Raw Phase 2 sweep data is under publication embargo; aggregated summaries and methodology are public. Intended audience: …"

**Problem:** `RELEASES.md:116-146` documents that on 2026-05-23 — under v0.3.0 as a between-version event — the 8-variant `Llama-PLLuM-70B-{base,instruct,chat}-{2412,2508,2512}-awq` AWQ release and the `mozarcik/clinical-pl-smpc-awq-calibration` dataset were published with Zenodo DOI `10.5281/zenodo.20317011` cited as the inherited version DOI. The 70B HF model cards (e.g. `mozarcik/Llama-PLLuM-70B-instruct-2512-awq` README citation block) cite this exact DOI as the "this version" DOI. **A reader following the DOI from the model cards therefore lands on a Zenodo record whose description is silent about the artifact they came to verify.**

**Severity:** critical — citation provenance is broken in the most-trafficked direction (HF card → Zenodo → verify "yes, this is the right release").

**Suggested fix:** edit the v0.3.0 record description on `zenodo.org` to add a between-version paragraph describing the 2026-05-23 PLLuM-70B AWQ release inherited under this DOI. Suggested text (paste-ready, retain the existing first paragraph, append a second paragraph):

> Between-version event under v0.3.0 (2026-05-23): public release of the first AWQ W4A16 (vLLM-native compressed-tensors) quantization of the Llama-PLLuM-70B family, to the author's knowledge. Eight model cards on HuggingFace under `mozarcik/` (`base × {2412, 2508}` + `instruct × {2412, 2508, 2512}` + `chat × {2412, 2508, 2512}`), each with Llama 3.1 Community License compliance artifacts (LICENSE, NOTICE with exact Meta wording, USE_POLICY.md), dual-platform vLLM usage snippets (AMD ROCm validated; NVIDIA portable via `awq_marlin`), Gate 1 hardware-envelope evidence and Gate 2 coherence-probe evidence. Reusable calibration corpus published separately as `mozarcik/clinical-pl-smpc-awq-calibration` (418 fragments of Polish SmPC text from EMA, ~512 tokens each, 81 INNs, 9 NFZ drug programmes, No PHI). Engineering envelope on 2× R9700 (gfx1201, TP=2): 37.56 GB total footprint, ~55,000-token KV cache at max_seq_len 8192, max_concurrency 6.7 req, junction peak 92–94 °C with ~16 °C headroom. Per-N throughput, latency, scaling and W/tok numbers remain EMBARGOED under METHODOLOGY §11.2 (stricter §11.3 for Polish models) pending peer-reviewed publication. See `RELEASES.md` 2026-05-23 block in the source repository for the full account.

**Related-identifiers row to add on the v0.3.0 record:**
- `https://huggingface.co/mozarcik` — `isSupplementedBy` — url
- `https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration` — `isReferencedBy` — url

---

### CRIT-2 — Zenodo v0.4.0 (20364953) description is stale auto-publish baseline; manual override prepared but not yet applied

**Channel:** Zenodo record 20364953 (`https://zenodo.org/records/20364953`)

**Current description (verbatim, fetched 2026-05-26):** identical to the v0.3.0 description above — i.e. the v0.1-era Qwen 3.6 27B summary from `.zenodo.json:11`.

**Problem:** The v0.4.0 Zenodo record describes v0.1-era engineering-envelope work on Qwen 3.6 27B. It omits **every** v0.4.0 deliverable: the Llama-PLLuM-70B family release, Run-3 (8B + 12B consumer-GPU AWQ), the 418-fragment SmPC calibration corpus, Gate 1 sanity evidence, Gate 2 human-override extension, `eval-rag/` sub-project, four-paper publication roadmap, three-layer architecture signaling, and the embargo classification line. The auto-publisher fired off `.zenodo.json:11` unchanged because the Łukasz-prepared override at `docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md` was never pasted into the edit form.

**Severity:** critical — the v0.4.0 DOI is the canonical citation pointer for the v0.4.0 release; it currently misrepresents what v0.4.0 contains.

**Suggested fix:** paste the contents of `docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md` (the `paste-ready summary for the "Description" textarea` block, lines 38-56) into the Description field on the v0.4.0 Zenodo edit form, and add the five related-identifier rows from that draft. The draft is already methodologically vetted and embargo-clean (PUBLIC §11.1 only, no leaked throughput numbers).

**Additionally:** also update `.zenodo.json` in the repo so the **next** release (v0.5.0 or any auto-publish) ships with a non-stale baseline. Suggested update — keep the `upload_type`, `creators`, `license`, `keywords`, `access_right` and `language` blocks unchanged; replace the `description` field with the v0.4.0 paste-ready summary minus version-specific phrasing (or accept the deferred-fix and just commit a note in the Zenodo-draft folder reminding to re-edit on every auto-publish).

---

### CRIT-3 — Zenodo v0.3.0 ↔ v0.4.0 version chain (`isNewVersionOf`) appears broken

**Channel:** Zenodo record 20364953 → 20317011

**Evidence:** WebFetch of `zenodo.org/records/20364953` returns no reference to `10.5281/zenodo.20317011` (v0.3.0) under Related identifiers. Only GitHub repo URL is listed. The visibility draft (`docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md:22-34`) explicitly notes "Zenodo's version chain may auto-set this from the concept DOI (`10.5281/zenodo.19851346`). If the v0.3.0 record (`10.5281/zenodo.20317011`) is not already linked, add it manually with the values above."

**Severity:** critical for citation graph integrity — a reader cannot trace the version chain from v0.4.0 back to v0.3.0 or forward from v0.3.0 to v0.4.0.

**Suggested fix:** on the v0.4.0 Zenodo edit form, under "Related identifiers", add:
- `10.5281/zenodo.20317011` — relation `isNewVersionOf` — scheme `doi` — resource type `software`

**Verification step:** after the edit lands, also verify on the v0.3.0 record that the reciprocal `isPreviousVersionOf` entry was created by Zenodo (this is usually automatic on saving the v0.4.0 side). If not, add it manually.

---

### CRIT-4 — `[UNVERIFIED]` ResearchGate publication 405205893 — title and attached version cannot be confirmed automated

**Channel:** ResearchGate publication `405205893`

**Evidence:** Both `WebFetch` (HTTP 403 Forbidden) and `curl` with a browser user-agent (Cloudflare error 1020 access-denied) failed to retrieve the live page. The URL title slug visible in the link is "*NaviMed-UMB hardware envelope studies for local AI deployment on consumer RDNA 4 GPUs*" — which is the v0.1-era title from `.zenodo.json:3`.

**Problem (inferred — needs human verification):** if the RG publication title slug still reads "*hardware envelope studies … on consumer RDNA 4 GPUs*", then the attached version is likely the v0.3.0 record (pre-Run-3) or even earlier. The current state of the project (v0.4.0 + Run-3 closing + four-paper roadmap + three-layer split) is materially broader than the title suggests.

**Severity:** critical-if-confirmed (RG is the audience-facing channel where international peer-reviewers and editorial-board contacts evaluate the project); minor-if-RG-was-already-updated. Cannot determine without manual verification.

**Suggested action (manual):**
1. Open `https://www.researchgate.net/publication/405205893` in a logged-in browser.
2. Confirm title, attached version DOI, abstract, and AI-assistance disclosure.
3. If the title still reads "*hardware envelope studies … on consumer RDNA 4 GPUs*", consider one of:
   - (a) edit the existing publication to use the v0.4.0 extended-abstract text from `docs/visibility/2026-05-26-researchgate-v0.4.0.md:27-37`, OR
   - (b) leave 405205893 as the v0.1/v0.3.0 historical record and create a NEW research-item on RG for v0.4.0 using the same draft. RG generally allows both patterns; the second preserves immutability of citation references already pointing to 405205893.

**Default suggestion:** option (b). Łukasz's draft already specifies five separate research items (Technical Report + 2× Gate 1 sanity Data + Paper #1 outline + calibration corpus link) — the existing 405205893 fits the v0.3.0 / hardware-envelope item naturally, and a new entry can carry the v0.4.0 Technical Report.

---

## 2. Recommended corrections per channel

### 2.GH — GitHub repository

| ID | Location | Current | Suggested | Severity |
|---|---|---|---|---|
| GH-1 | `README.md:46` | "RELEASES.md … per-release notes (v0.1.0 → v0.3.0) and between-version events (the 2026-05-23 public Llama-PLLuM-70B AWQ release lives here)." | "per-release notes (v0.1.0 → v0.4.0) and between-version events (the 2026-05-23 public Llama-PLLuM-70B AWQ release and the 2026-05-26 Run-3 consumer-GPU 8B/12B AWQ release live here)." | minor — version chain in README sentence ends at v0.3.0; rest of README is v0.4.0 |
| GH-2 | `README.md:61` | "Eight HuggingFace model cards — `mozarcik/Llama-PLLuM-70B-{base,instruct,chat}-{2412,2508,2512}-awq` (8 variants total; …)" | Either say "Ten HuggingFace model cards" and add the 8B + 12B Run-3 row, OR add a second bullet listing the Run-3 consumer-GPU variants explicitly. README "Public artifacts" section currently undercounts the live HF surface by 2 cards. | major — README inventory is incomplete vs live HF state |
| GH-3 | `README.md:64` | "One Zenodo deposit — concept DOI 10.5281/zenodo.19851346 (… current version v0.3.0 at 10.5281/zenodo.20317011)." | "… current version **v0.4.0** at **10.5281/zenodo.20364953**." | major — wrong version DOI in README |
| GH-4 | `README.md:97-102` | "AI assistance … Claude Opus 4.7 … GPT-5.5 Deep Thinking … Gemini (web review) … Bielik-11B-v3.0-instruct-AWQ … for Polish-language proofreading of documentation in May 2026." | Same paragraph is good. Consistent with `AI_USAGE_DISCLOSURE.md:14-22`. No action. | OK |
| GH-5 | `AI_USAGE_DISCLOSURE.md:4` | "Document version: 1.2 (released with `navimed-umb` v0.3.0); Last updated: 2026-05-20" | Bump to "Document version: 1.3 (released with `navimed-umb` v0.4.0); Last updated: 2026-05-24" OR "1.4 (2026-05-26)" to cover Run-3 additions. Then add a §5 changelog row for the bump. Specifically — the table at lines 173-175 stops at row 1.2/v0.3.0; v0.4.0 row is missing despite the v0.4.0 release going out 2026-05-24. | major — disclosure document is one release behind |
| GH-6 | `AI_USAGE_DISCLOSURE.md:175` | "1.2 v0.3.0 …" — last row of versioning table | Add new rows: "1.3 v0.4.0 — Added Gemini (web review) and Bielik-11B-v3.0-instruct-AWQ (local, R9700) as documentation-editorial tools per the 2026-05-23 release session. Version DOI 10.5281/zenodo.20364953." and "1.4 between-version 2026-05-26 — Run-3 (consumer-GPU PLLuM AWQ) release; same tool profile as 1.3." | major (paired with GH-5) |
| GH-7 | `AI_USAGE_DISCLOSURE.md:194` (canonical inline disclosure) | "Full disclosure: see `AI_USAGE_DISCLOSURE.md` in the project repository (DOI: 10.5281/zenodo.19851346)." | OK — uses concept DOI which is the right choice for forward-compatibility. No action. | OK |
| GH-8 | `.zenodo.json:11` | description text is v0.1-era Qwen 3.6 27B boilerplate | Replace with the v0.4.0 paste-ready summary (from `docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md:38-56`) — adapted to forward-looking phrasing so the next auto-publish does not re-stage stale text. | major — root cause of CRIT-2 |
| GH-9 | `.zenodo.json:28-34` | `related_identifiers` only contains the GitHub URL | Add the four additional related-identifier rows from the visibility draft (Zenodo v0.3.0 isNewVersionOf, two HF Run-3 isSupplementedBy, dataset isReferencedBy). | major — fix root cause of CRIT-3 for next release |
| GH-10 | `README.md:79-93` (Roadmap table) | Paper #2/#3/#4 rows say "AIntern proposal" | Per memory `project_qaif_aintern_2026` (DROPPED 2026-05-25), the QAIF AIntern path is no longer the scaffolding for these papers. Update status to "habilitation roadmap" or "in scoping" depending on Łukasz's preference. Also the explanatory sentence at README:82 ("tied to the 2026-05 / 2026-06 QAIF AIntern submissions") is stale. | minor — affects credibility for any reader who checks QAIF and finds Łukasz did not submit |
| GH-11 | `paper/paper-1-results-outline.md:62` | "AQLM 2-bit single-card variant scoped for v0.5.0" | Cross-check with `eval-rag/README.md:160-174` which scopes AQLM 2-bit conditional on the 5-model eval result (BLOCKED). The outline says "scoped for v0.5.0" implying scheduled; eval-rag says "conditional". Pick one wording and harmonize. | minor — internal-doc consistency only |
| GH-12 | `RELEASES.md:155-156` | "It adds the Phase 2 v0.3 sweep harness — TP=1 parallel … and the Bielik v3.0 family environment envelope (4.5B, 11B, PL-11B sanity-test PASS, TP=1 and TP=2)." | Consistent with GH v0.3.0 release notes and METHODOLOGY §4.2. OK. | OK |
| GH-13 | GH v0.3.0 release notes (via `gh release view`) | "BF16 (~140 GB) exceeds the 64 GB aggregate VRAM of 2× R9700" | RELEASES.md, METHODOLOGY §4.3 errata, and 70B HF model cards all consistently say **132 GB** not 140 GB. The GH release notes for v0.3.0 are the outlier. | minor — single-channel discrepancy, GH release notes are immutable-ish after publication; flag only |

### 2.HF — HuggingFace cards

| ID | Location | Current | Suggested | Severity |
|---|---|---|---|---|
| HF-70B-1 | All 9 × 70B cards (e.g. `mozarcik/Llama-PLLuM-70B-instruct-2512-awq` README:218) | "DOI (this version, v0.3.0): 10.5281/zenodo.20317011" | This is correct for the version DOI cited *at the time of HF publication* (2026-05-23, when v0.3.0 was current). Since the 70B cards are immutable citation targets and v0.3.0 was the inheriting release at release time, **leave the version DOI as 20317011 but add a footnote**: "Concept DOI 10.5281/zenodo.19851346 always resolves to the latest version; as of 2026-05-24, the latest is v0.4.0 (DOI 10.5281/zenodo.20364953)." | minor — leave version DOI, optionally add concept-resolves-to-latest footnote |
| HF-70B-2 | All 9 × 70B cards link to `navimed-umb/tree/v0.3.0/...` | `tree/v0.3.0/environment`, `tree/v0.3.0/calibration/quantization`, `tree/v0.3.0/environment/coherence-probes` | These are version-pinned links — correct convention. Leave as-is for the 70B cards (released under v0.3.0). | OK |
| HF-70B-3 | All 9 × 70B cards `## AI assistance disclosure` section | "Parts of this documentation (the model card) were locally edited and proofread with the assistance of Bielik-11B-v3.0-instruct served via vLLM on the same hardware." | Mentions Bielik only. **Does NOT mention** that the model card was originally drafted by Claude (Anthropic) and reviewed by ChatGPT/Gemini (per `docs/sessions/2026-05-23-pllum-awq-release-pipeline.md:64-67`). The current README.md root and AI_USAGE_DISCLOSURE.md disclose Claude + GPT + Gemini + Bielik. The 70B HF cards under-disclose. | major — disclosure asymmetry between channels: GH says 4 tools, HF says 1 |
| HF-70B-4 | All 9 × 70B cards Credits/Compute section | "Calibration host: AMD Instinct MI300X via AMD Developer Cloud powered by DigitalOcean" | Consistent across all 9 cards. AMD AI Developer Program credit is implicit via this attribution. ✓ | OK |
| HF-70B-5 | All 9 × 70B cards "(verified via HuggingFace Hub search, 2026-05-23)" | "first public AWQ W4A16 (vLLM-native compressed-tensors) quantization of the Llama-PLLuM-70B family" with verification date 2026-05-23 | Consistent. ✓ | OK |
| HF-8B-1 | `mozarcik/Llama-PLLuM-8B-chat-2512-awq` README — note on parameter display | "The logical base architecture is Llama-PLLuM-8B (8.03B parameters)" | The number "8.03" appears both as "base parameter count" (8B parameters here) AND in the 12B card as the AWQ weight footprint (`8.03 GiB`). Reader-confusion risk because the units are tiny. Suggest disambiguating: "Llama-PLLuM-8B base has 8.03B parameters (note: this is parameter count, not the 8.03 GiB AWQ footprint of the separate 12B variant)" — or just round 8B base to "~8B parameters" to avoid number collision. | minor — reader-confusion potential only; no factual error |
| HF-8B-2 | 8B README AI assistance disclosure | "This model card was drafted by Claude (Anthropic) as part of an interactive engineering session …" | Better-disclosed than the 70B cards (mentions Claude explicitly). But does NOT mention GPT/Gemini reviewers (the 8B card was generated 2026-05-26, may not have gone through the same 3-review pipeline as the 70B). | minor — verify with Łukasz whether the 3-review pipeline was applied to 8B/12B; if yes, add. If 8B/12B used Claude-only with no GPT/Gemini review, the current disclosure is honest. |
| HF-8B-3 | 8B README Credits/Compute | "Calibration host: AMD Radeon AI PRO R9700 (gfx1201, RDNA 4), local workstation" | Correct for Run-3 (Łukasz's R9700, NOT MI300X). Differentiates correctly from the 70B family. ✓ | OK |
| HF-8B-4 | 8B README BibTeX | `doi = {10.5281/zenodo.19851346}` (concept DOI) | Correct choice — concept DOI for forward-compatibility. ✓ | OK |
| HF-8B-5 | 8B README license frontmatter + Built-with-Llama block + NOTICE/LICENSE/USE_POLICY | All Llama 3.1 CL artifacts present per `logbook/2026-05-26.md:12` | Verified via README content. ✓ | OK |
| HF-12B-1 | `mozarcik/PLLuM-12B-chat-2512-awq` license frontmatter | `license: apache-2.0` | Correct — Mistral-Nemo-Base-2407 lineage is Apache 2.0. ✓ | OK |
| HF-12B-2 | 12B README base_model frontmatter | `base_model: CYFRAGOVPL/PLLuM-12B-chat-2512` (Mistral-Nemo lineage), `base_model_relation: quantized` | Correct — Mistral arch declared (HF parsed it as `mistral` per the repo overview tags). ✓ | OK |
| HF-12B-3 | 12B README Gate 2 coherence probe section | "minor: one occurrence of `nawracjącymi` typo and one mild content drift to enzyme katalazy — neither indicates quantization damage" | This is a candid quality observation, NOT an embargoed throughput number. Consistent with §8 vehicle-integrity boundary. ✓ | OK |
| HF-12B-4 | 12B README — first non-Llama PLLuM variant claim | "the first non-Llama PLLuM variant" | Verify against `METHODOLOGY.md:106` which lists `CYFRAGOVPL/PLLuM-12B-chat` (Mistral base) as the only Mistral-based PLLuM in the suite. ✓ Defensible. | OK |
| HF-12B-5 | 12B README AI assistance disclosure | "This model card was drafted by Claude (Anthropic) …" | Same observation as HF-8B-2. | minor |
| HF-D-1 | `mozarcik/clinical-pl-smpc-awq-calibration` README | "Used to calibrate the `mozarcik/Llama-PLLuM-70B-*-awq` model series, produced on the AMD Developer Cloud (Instinct MI300X)." | This was true at dataset publication (2026-05-21) but stale now: the same corpus also calibrated the 8B + 12B Run-3 variants (per `logbook/2026-05-26.md:8` and `METHODOLOGY.md:115` Run-3 addendum). Suggest updating to: "Used to calibrate the `mozarcik/Llama-PLLuM-70B-*-awq` family (70B family quantized on AMD MI300X / AMD Developer Cloud) and the `mozarcik/Llama-PLLuM-8B-chat-2512-awq` + `mozarcik/PLLuM-12B-chat-2512-awq` Run-3 variants (quantized locally on 2× R9700)." | major — dataset card is the canonical "what was I used for" pointer; missing 2 downstream artifacts |
| HF-D-2 | Dataset README — provenance and No-PHI claim | "No patient data / no PHI. SmPC documents describe drug products (efficacy, dosing, adverse reactions, pharmacokinetics, aggregate trial data) — not individuals. Verified by automated pattern scan and manual sampling." | Clean, consistent with `RELEASES.md:43`. ✓ | OK |
| HF-D-3 | Dataset README — license and EMA reproduction policy | `license: other`, license_name `ema-public-reproduction-policy-and-source-specific-reuse-terms`, body explains EMA + URPL provenance | Consistent with `README.md:111-113` ("derived from third-party regulatory documents (EMA-published SmPC); governed by `calibration/LICENSE`, not the root CC-BY-4.0 / MIT licenses."). ✓ | OK |

### 2.Z-V3 — Zenodo v0.3.0 record (20317011)

| ID | Location | Current | Suggested | Severity |
|---|---|---|---|---|
| Z-V3-1 | Description field | v0.1-era Qwen 3.6 27B summary | Append the v0.3.0-between-version paragraph from §1.CRIT-1 | critical |
| Z-V3-2 | Related identifiers | GitHub URL only | Add `mozarcik/` HF user URL (`isSupplementedBy`) and dataset DOI/URL (`isReferencedBy`) | major |
| Z-V3-3 | Version-chain forward | (manual confirm needed) — Zenodo *should* auto-link to v0.4.0 once v0.4.0 has `isNewVersionOf` set to v0.3.0 (§1.CRIT-3 fix) | Verify after CRIT-3 fix | minor |

### 2.Z-V4 — Zenodo v0.4.0 record (20364953)

| ID | Location | Current | Suggested | Severity |
|---|---|---|---|---|
| Z-V4-1 | Description field | v0.1-era Qwen 3.6 27B summary (stale auto-publish) | Replace with paste-ready summary from `docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md:38-56` | critical |
| Z-V4-2 | Related identifiers | GitHub URL only | Add 4 rows from visibility draft: v0.3.0 `isNewVersionOf`, 2× HF Run-3 `isSupplementedBy`, dataset `isReferencedBy` | critical |
| Z-V4-3 | AI assistance disclosure note | "(Claude, Anthropic; GPT, OpenAI). All experimental design … AI tools did not execute experiments." — same boilerplate as v0.3.0 | The paste-ready summary already includes a more complete disclosure paragraph (Bielik mentioned). When pasting per Z-V4-1, the new disclosure paragraph supersedes the field-level "notes" entry. | major — fold into Z-V4-1 |

### 2.RG — ResearchGate publication 405205893

> `[UNVERIFIED]` — automated retrieval blocked (HTTP 403 + Cloudflare 1020). All RG findings below are derived from the visibility-draft text `docs/visibility/2026-05-26-researchgate-v0.4.0.md` and cannot be confirmed against live RG state by this review.

| ID | Suggested | Severity |
|---|---|---|
| RG-1 | Manually open publication 405205893, confirm: title, attached version DOI, abstract, authors, AI-disclosure paragraph. See §1.CRIT-4 for the decision tree (option a: edit existing; option b: create new v0.4.0 item alongside). | critical-if-confirmed |
| RG-2 | If creating a new v0.4.0 RG item (recommended option b in §1.CRIT-4): use `docs/visibility/2026-05-26-researchgate-v0.4.0.md:27-37` (Extended abstract) and `:39-54` (Keywords). Confirm the Zenodo DOI `10.5281/zenodo.20364953` is set as the primary identifier and that the GitHub repo + HF model repos are added as supplementary URLs. | major |
| RG-3 | Project-page summary on RG should use the 150-200 word short abstract (`docs/visibility/2026-05-26-researchgate-v0.4.0.md:23-25`). Confirm the current project page does not still carry v0.1-era hardware-envelope-only summary. | major |
| RG-4 | RG-side AI-disclosure: confirm the paragraph at `docs/visibility/2026-05-26-researchgate-v0.4.0.md:77` is reflected on the v0.4.0 RG item description. The current 405205893 publication may carry only the v0.1-era disclosure ("Claude, Anthropic; GPT, OpenAI") and not mention Bielik / Gemini. | major |

---

## 3. Observations (not bugs)

These are stale-but-pre-decision claims — not contradictions, just artifacts of timeline. Left here for situational awareness, NOT for action unless Łukasz disagrees.

| ID | Observation | Why-not-a-bug |
|---|---|---|
| OBS-1 | The 9 × 70B HF model cards reference `navimed-umb/tree/v0.3.0/...` paths and cite version DOI 20317011 (v0.3.0). These were correct at HF publication time (2026-05-23, when v0.3.0 was current). | Convention: HF model cards version-pin to the release-at-time-of-card-publication. Updating them retroactively breaks immutability of the citation graph. The concept DOI footnote in HF-70B-1 is the recommended bridge. |
| OBS-2 | The 70B HF cards do NOT signal the three-layer architecture (L1/L2/L3) split because they were published 2026-05-23, before the split was formalized on 2026-05-24 (per memory `project_navimed_three_layer_2026-05-24`). | Stale-but-pre-decision. The Run-3 cards (8B/12B, published 2026-05-26) and the Zenodo v0.4.0 paste-ready draft both signal the three-layer architecture explicitly (`README.md:14-16`, `docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md` does not explicitly call it out though — see CONSIDER-1 below). |
| OBS-3 | Zenodo v0.3.0 description does not mention v0.3.0-era PLLuM-70B AWQ release, but neither does the v0.3.0 GitHub release notes — both were written before the 2026-05-23 between-version event. | The GH v0.3.0 release notes (`gh release view v0.3.0`) are *retroactively immutable* in convention but technically editable. The Zenodo v0.3.0 description IS editable and is CRIT-1. The GH-side stale-ness here is acceptable; the Zenodo-side stale-ness is not, because the citation provenance breaks. |
| OBS-4 | The `paper/paper-1-results-outline.md:64` says "MDPI Electronics or IEEE Access target, Q1 2027". The `README.md:86` says "MDPI Electronics / IEEE Access (Q1)" without year. The `eval-rag/README.md:20` mentions ADVMS / PeerJ / Sage TARR / Advances in Respiratory Medicine as alternative venues. | All consistent — the outline locks Paper #1 to a venue band, the README lists the same band, and eval-rag (a separate paper) targets a different venue. No contradiction. |
| OBS-5 | `AI_USAGE_DISCLOSURE.md:43-46` documents two `Co-Authored-By: Claude` commits (`9a02dfe`, `426a712`) intentionally retained pre-v0.1.0 for Zenodo immutability. | This is a positive trust signal (transparency about commit-level AI co-authorship), not a bug. ✓ |
| OBS-6 | GH v0.3.0 release notes say "BF16 (~140 GB)" but RELEASES.md and HF cards say "132 GB". | Single-channel outlier on an immutable GH release note. Flag in GH-13 but do not retroactively edit. |
| OBS-7 | Polish-language model card text uses both "ChPL" (Polish abbreviation) and "SmPC" (international abbreviation) for the same Summary-of-Product-Characteristics documents. | Stylistic dual-naming — explained inline in dataset README. Not a bug. |

---

## 4. Halucynacja-watch summary

**Findings against the artifact set reviewed (all 11 HF cards + 1 dataset + Zenodo records + GH READMEs + local Markdown):**

| # | Channel | Claim audited | Verdict |
|---|---|---|---|
| H-1 | 70B HF cards | "37.56 GB total footprint (TP=2)" / "18.78 GiB per GPU" | Consistent across all 9 cards and the GH v0.4.0 release notes (`gh release view v0.4.0`). PUBLIC §11.1. ✓ no hallucination |
| H-2 | 70B HF cards | "~55,000 token KV cache @ 8192 max_seq_len" / "max_concurrency 6.7 req" | Consistent across all 9 cards, RELEASES.md `:51`, GH v0.4.0 release notes, logbook 2026-05-23. ✓ |
| H-3 | 70B HF cards | "Junction peak 92-94 °C; ~16 °C headroom to gfx1201 throttle limit ~110 °C" | Consistent with `logbook/2026-05-24.md:27` and RELEASES.md `:52`. ✓ |
| H-4 | 70B HF cards | "first public AWQ W4A16 (vLLM-native compressed-tensors) quantization of the Llama-PLLuM-70B family … verified via HuggingFace Hub search, 2026-05-23" | Defensible — qualifier `to the author's knowledge` is explicit. GGUF alternatives by mradermacher are acknowledged. ✓ |
| H-5 | 8B HF card | "5.53 GiB weights / 22.22 GiB KV / 88.89× max-concurrency @ max_seq_len=2048" | Consistent across the 8B HF card, `logbook/2026-05-26.md:32-34`, RELEASES.md `:17`, METHODOLOGY §4.3 Run-3 addendum, Zenodo v0.4.0 paste-ready draft. ✓ |
| H-6 | 12B HF card | "8.03 GiB weights / 19.77 GiB KV / 63.27× max-concurrency @ max_seq_len=2048" | Consistent across the 12B HF card, logbook 2026-05-26, RELEASES.md, METHODOLOGY §4.3 Run-3 addendum, Zenodo v0.4.0 draft. ✓ |
| H-7 | Dataset card | "418 chunks (~512 tokens) … 81 INNs, 9 NFZ drug programmes" | "418 fragments" consistent in dataset README, RELEASES.md `:42-43`, README.md `:62`, paper/paper-1-results-outline.md `:17`, eval-rag/README.md `:45`. "81 INNs / 9 NFZ programmes" consistent in same set. ✓ |
| H-8 | 12B HF card | "Mistral architecture quirks — Tokenizer vocab is 131k (larger than Llama 3.1's 128k)" | Plausible domain claim (Mistral-Nemo-Base-2407 tokenizer is documented at ~131k vocab), but not independently verified by this review. `[UNVERIFIED — but consistent with Mistral-Nemo public docs]` — Łukasz should spot-check before publication if not done already. |
| H-9 | 12B HF card Gate 2 sample | "Warszawa, … Jej populacja wynosi 1,86 mln mieszkańców" | This is model output, not a factual claim by Łukasz. The README explicitly contextualizes it as a coherence-probe sample, not a fact-checked claim. ✓ no hallucination claim — it's reported output, not asserted truth |
| H-10 | Zenodo v0.3.0/v0.4.0 | "v0.1 hardware-envelope preprint on Qwen 3.6 27B (FP8 vs BF16, CUDA-graph and FP8-kernel findings)" | This is the v0.1-era boilerplate that is stale (CRIT-1 + CRIT-2). The claim itself is not a hallucination — it just describes the wrong release. ✓ no hallucination, just wrong-version description |
| H-11 | 70B HF cards | "Llama 3.1 base, full Llama 3.1 Community License compliance: LICENSE, NOTICE with exact Meta wording, USE_POLICY.md" | Verified by inspection of the live HF cards; LICENSE/NOTICE/USE_POLICY sections present in all 9 cards. ✓ |
| H-12 | All Polish-text cards | "konsorcjum PLLuM (SpeakLeash, OPI-PIB, NASK, Politechnika Wrocławska)" | Consistent across all 11 model cards (70B family + 8B + 12B). Matches `RG draft:75`, `linkedin-post.md` per `logbook/2026-05-23.md:39`, and `docs/sessions/2026-05-23-pllum-awq-release-pipeline.md:134`. ✓ |
| H-13 | All channels — Ministerstwo Cyfryzacji RP attribution | "Polish Ministry of Digital Affairs / Ministerstwo Cyfryzacji RP" (HF org CYFRAGOVPL) | Consistent. ✓ |
| H-14 | All channels — Łukasz affiliation | "Department of Respiratory Physiopathology, Medical University of Białystok, Poland" + ORCID 0000-0002-2536-3508 | Consistent across `.zenodo.json:7-8`, Zenodo records 20317011 + 20364953, all 11 HF model cards, AI_USAGE_DISCLOSURE.md, ResearchGate draft. ✓ |
| H-15 | LinkedIn post (per logbook) | "AMD AI Developer Program, DigitalOcean GPU Droplets, PLLuM consortium (SpeakLeash / OPI-PIB / NASK / PWr), Polish Ministry of Digital Affairs / CYFRAGOVPL" | Consistent with HF model card Credits/Compute blocks. ✓ |
| H-16 | Run-3 12B Apache 2.0 license claim | "PLLuM-12B (Mistral-Nemo-Base-2407 derivative, Apache 2.0)" | Apache 2.0 is the correct license for the Mistral-Nemo-Base-2407 lineage. ✓ |
| H-17 | Embargo discipline | NO per-N throughput, latency, W/tok, or KV occupancy numbers leaked to any of: HF cards, Zenodo records, GH README, ResearchGate draft, logbook 2026-05-24 walltime table | Verified by direct read of all sources. Walltimes (~40 min/model) are PUBLIC §11.1 engineering time, NOT throughput numbers. ✓ No §11.2/§11.3 violations found across the four channels. |

**Conclusion of halucynacja-watch:** **No fabricated numbers found.** All envelope numbers cross-check across at least three independent sources. No leakage of §11.2/§11.3 embargoed throughput data on any public channel. The "to the author's knowledge" qualifier is preserved on every first-public claim. The AI-assistance disclosure is **inconsistent across channels** (see CONSIDER-1 below) but not fabricated.

---

## 5. Łukasz's manual action checklist

Paste-ready instructions per channel. Estimated walltime to clear all CRITs: **~45 minutes**.

### 5.1 Zenodo (~20 min) — clears CRIT-1, CRIT-2, CRIT-3

**Step 1 — log in to zenodo.org as the record owner.**

**Step 2 — v0.4.0 record (20364953):**
1. Click "Edit" on `https://zenodo.org/records/20364953`.
2. In the **Description** field, replace the entire text with the contents of `/home/mozarcik/Vaults-main/10_Projekty/0001-navimed-umb/docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md` lines 38-56 (the `<p>...</p>` HTML block). Zenodo accepts HTML in this field.
3. Under **Related identifiers**, add five rows from the table at `docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md:26-32`:
   - `https://github.com/kicrazom/navimed-umb` — `is supplement to` — url
   - `10.5281/zenodo.20317011` — `is new version of` — doi
   - `https://huggingface.co/mozarcik/Llama-PLLuM-8B-chat-2512-awq` — `is supplemented by` — url
   - `https://huggingface.co/mozarcik/PLLuM-12B-chat-2512-awq` — `is supplemented by` — url
   - `https://huggingface.co/mozarcik/clinical-pl-smpc-awq-calibration` — `is referenced by` — url
4. Save. Verify the new description renders, and the version chain banner at the top of the page now shows `v0.3.0 → v0.4.0`.

**Step 3 — v0.3.0 record (20317011):**
1. Click "Edit" on `https://zenodo.org/records/20317011`.
2. In **Description**, *append* (do not replace) the between-version paragraph from §1.CRIT-1 of this review. Keep the original first paragraph for historical continuity — readers expect the v0.3.0 record to still describe v0.3.0-era scope.
3. Under **Related identifiers**, add two rows:
   - `https://huggingface.co/mozarcik` — `is supplemented by` — url
   - `https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration` — `is referenced by` — url
4. Verify the `isPreviousVersionOf` (or `obsoletes` / reverse) link to v0.4.0 was auto-populated by Zenodo once you saved the v0.4.0 side in Step 2. If not, add `10.5281/zenodo.20364953` — `is previous version of` — doi.
5. Save.

### 5.2 GitHub (~15 min) — clears GH-1, GH-2, GH-3, GH-5, GH-6, GH-8, GH-9, GH-10

**README.md:**
- Line 46: change "(v0.1.0 → v0.3.0)" → "(v0.1.0 → v0.4.0)" and append "and the 2026-05-26 Run-3 consumer-GPU 8B/12B AWQ release"
- Line 61: change "Eight HuggingFace model cards" → "Ten HuggingFace model cards" and append a sub-bullet listing the 2 Run-3 variants (Llama-PLLuM-8B-chat-2512-awq + PLLuM-12B-chat-2512-awq)
- Line 64: change "current version v0.3.0 at 10.5281/zenodo.20317011" → "current version v0.4.0 at 10.5281/zenodo.20364953"
- Lines 79-93 Roadmap: replace "AIntern proposal" status entries with "habilitation roadmap" or "in scoping" per memory `project_qaif_aintern_2026` (DROPPED 2026-05-25); also fix the "tied to the 2026-05 / 2026-06 QAIF AIntern submissions" sentence at line 82

**AI_USAGE_DISCLOSURE.md:**
- Line 4: bump version to 1.4, date to 2026-05-26
- Line 175: extend versioning table with rows for 1.3 (v0.4.0) and 1.4 (Run-3 between-version event)

**.zenodo.json:**
- Line 11: replace description with the v0.4.0 paste-ready summary (forward-looking phrasing; same template you used for the visibility draft, but written as the new release baseline rather than a one-off override)
- Lines 28-34: extend `related_identifiers` to include Zenodo previous version, HF cards, dataset (4 additional rows beyond the GitHub URL)

**Commit message suggestion** (per the project's atomic-commit convention):
```
docs(visibility): align README/disclosure/.zenodo.json with v0.4.0 + Run-3 state

- README: bump release pointer v0.3.0→v0.4.0, +Run-3 in Public artifacts,
  retire QAIF-AIntern scaffolding language
- AI_USAGE_DISCLOSURE: bump to v1.4 (2026-05-26), table rows for v0.4.0 + Run-3
- .zenodo.json: replace v0.1-era description with v0.4.0 paste-ready summary
  (prevents stale auto-publish on next release); +4 related_identifier rows
```

### 5.3 HuggingFace (~5-10 min) — clears HF-D-1, optional HF-70B-1

**Dataset card** (`mozarcik/clinical-pl-smpc-awq-calibration`) — REQUIRED:
- Edit the README at `https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration/blob/main/README.md`
- Update the "Used to calibrate ..." sentence per HF-D-1 above to include the 8B + 12B Run-3 variants
- (Optional) Add a short "Versioning" section noting which model series each calibration run produced

**70B HF cards** (9 cards) — OPTIONAL, leave as-is unless you want to:
- Add a footnote at the end of the Credits section: "Concept DOI 10.5281/zenodo.19851346 always resolves to the latest version; as of 2026-05-24, the latest is v0.4.0 (DOI 10.5281/zenodo.20364953)." (HF-70B-1)
- DO NOT change the `tree/v0.3.0/...` paths — those are correctly version-pinned for the v0.3.0-era release.
- DO NOT change the AI assistance disclosure section retroactively — but for the NEXT 70B card update (if any), expand the disclosure to mention Claude + GPT + Gemini + Bielik per the GH-side `AI_USAGE_DISCLOSURE.md`. (HF-70B-3)

**Run-3 cards** (8B + 12B) — OPTIONAL:
- HF-8B-1: optionally clarify "8.03B parameters" vs the unrelated "8.03 GiB AWQ footprint" of the 12B variant
- HF-8B-2 / HF-12B-5: optionally expand AI disclosure to mention any GPT/Gemini review applied to the 8B/12B cards (only if those reviews actually happened — do not fabricate)

### 5.4 ResearchGate (~5 min if option a, ~15 min if option b) — clears CRIT-4, RG-1 to RG-4

**Step 1 — manually open `https://www.researchgate.net/publication/405205893`** (logged in).

**Step 2 — assess current state:**
- What title does the publication carry?
- Which version (DOI) does it list?
- What does the abstract say?
- Does the AI-assistance disclosure mention Bielik / Gemini, or just Claude + GPT?

**Step 3 — decide between option a (edit) or option b (new item):**
- **Option a (faster, ~5 min):** edit publication 405205893 in place — replace title, abstract, DOI link with v0.4.0 content from `docs/visibility/2026-05-26-researchgate-v0.4.0.md:27-37`.
  - Pro: single publication, no duplication.
  - Con: any earlier citation pointing to 405205893 will now resolve to the v0.4.0 abstract, which changes the historical reference.
- **Option b (slower, ~15 min):** leave 405205893 as the v0.1/v0.3.0 historical record. Create a NEW research-item on RG for v0.4.0 using the same draft, with Zenodo DOI `10.5281/zenodo.20364953` set as primary identifier and the GH repo + HF model repos as supplementary URLs. RG generally accepts both versioning patterns.
  - Pro: preserves immutability of any prior 405205893 references.
  - Con: duplicate-artifact noise on Łukasz's RG profile.

**Default recommendation: option b.** The historical 405205893 publication is well-suited as the v0.1/v0.3.0 hardware-envelope record; v0.4.0 deserves its own item to carry the Run-3 + four-paper-roadmap + three-layer-architecture context.

**Step 4 — for either option:** update the project-page summary on RG (separate from the publication item) to use the 150-200-word short abstract at `docs/visibility/2026-05-26-researchgate-v0.4.0.md:23-25`. This is the surface most international peer-reviewers see first.

### 5.5 Cross-channel sanity check after the above (~5 min)

After all edits land:

1. **DOI trace test.** Click each of these and verify the destination matches the channel's claim:
   - HF card `mozarcik/Llama-PLLuM-70B-instruct-2512-awq` → DOI 20317011 → Zenodo v0.3.0 description now mentions the 70B AWQ release ✓
   - GitHub README "current version v0.4.0" → DOI 20364953 → Zenodo v0.4.0 description now mentions Run-3 + 70B family + four-paper roadmap ✓
   - Concept DOI 19851346 → latest version banner now says v0.4.0 (not v0.3.0)
2. **Version-chain test.** On Zenodo v0.4.0 page, confirm the "Versions" sidebar shows v0.3.0 → v0.4.0 chain.
3. **HF dataset back-reference test.** On `mozarcik/clinical-pl-smpc-awq-calibration` page, confirm the "Used by" or "Models trained or fine-tuned on this dataset" panel lists 11 model repos (8 instruct/chat 70B family + 8B + 12B + maybe also `Llama-PLLuM-70B-base-{2412,2508}-awq` for 10 total). HF auto-derives this from the `datasets:` frontmatter; if any of the 11 is missing, the model card frontmatter on the missing one needs `datasets: - mozarcik/clinical-pl-smpc-awq-calibration` added.

---

## 6. Cross-system "consider for future" items

These are not bugs in the v0.4.0 release but trends worth tracking.

| ID | Item | Severity |
|---|---|---|
| CONSIDER-1 | AI-assistance disclosure inconsistency: GH (README + AI_USAGE_DISCLOSURE.md) discloses Claude + GPT + Gemini + Bielik; 70B HF cards disclose Bielik only; Run-3 HF cards disclose Claude only; Zenodo v0.3.0/v0.4.0 disclose Claude + GPT only. Recommend adopting a single canonical inline disclosure (from `AI_USAGE_DISCLOSURE.md:186-194`) and using it identically across every public channel for the next release. | major — disclosure rigor is a Łukasz-stated value (`AI_USAGE_DISCLOSURE.md:11` "Transparency about AI assistance is a default policy") |
| CONSIDER-2 | Three-layer architecture (L1 UMB / L2 RAG / L3 Arena) is signaled in the GH README `:14-16` but not in the Zenodo v0.4.0 paste-ready draft, the 70B HF cards (pre-decision, OBS-2), the Run-3 HF cards, or the ResearchGate draft. Consider adding a sentence to the next Zenodo update and the next HF card refresh: "NaviMed-UMB is the L1 pillar of a three-layer architecture (workstation → retrieval → arena) targeted at sovereign on-premise medical AI." | minor — habilitation framing pillar; worth showing once you commit |
| CONSIDER-3 | The phrase "first public AWQ … to the author's knowledge" is used consistently across channels — good. But the Run-3 8B + 12B cards extend the same claim ("first public AWQ W4A16 (vLLM-native compressed-tensors) quantization of this Llama-PLLuM-8B-chat-2512 / PLLuM-12B-chat-2512 checkpoint, HF Hub check 2026-05-26"). Recommend running a one-line `hf_hub_query` re-check before the v0.5.0 release in case CYFRAGOVPL or a third party publishes an AWQ in the interim. | minor — methodological discipline |
| CONSIDER-4 | `eval-rag/` is `BLOCKED` on reviewer responses from two proposed external reviewers since 2026-05-24. If the 4-week no-response policy fires (2026-06-21), the sub-project should either move to second-tier reviewers or be parked in `paused` status across MOC / project hub. (eval-rag/ is now local-only; identities withheld pending consent.) | minor — calendar follow-up |
| CONSIDER-5 | The 12B HF card Gate 2 sample uses Warsaw's population as a coherence probe ("Jej populacja wynosi 1,86 mln mieszkańców"). This is current within rounding (~1.86 M as of 2024 GUS data). Not a bug. ✓ | OK |

---

## 7. Summary by severity

| Severity | Count | Items |
|---|---|---|
| **Critical** (CRIT) | **4** | CRIT-1 (Zenodo v0.3.0 description stale re: 70B release), CRIT-2 (Zenodo v0.4.0 description is auto-publish baseline), CRIT-3 (Zenodo version chain broken), CRIT-4 (`[UNVERIFIED]` ResearchGate 405205893 — manual verification needed) |
| **Major** | **10** | GH-2, GH-3, GH-5, GH-6, GH-8, GH-9, HF-70B-3, HF-D-1, Z-V3-1, Z-V3-2, Z-V4-3, RG-2, RG-3, RG-4 (counting by-channel; some are sub-items of CRITs) |
| **Minor** | **~12** | GH-1, GH-10, GH-11, GH-13, HF-70B-1, HF-8B-1, HF-8B-2, HF-12B-5, HF-D back-references, OBS-1..7 |

**Total inconsistencies surfaced:** 4 critical + ~10 major + ~12 minor + 7 observations.

**Most urgent fix (top-1):** **CRIT-2 — Zenodo v0.4.0 description.** This is the canonical citation pointer for the v0.4.0 release that you have already publicly DOI-stamped with HF model cards and the README badge. The current description text actively misrepresents what v0.4.0 contains by describing v0.1-era Qwen 3.6 27B work. The fix is paste-ready (just paste `docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md:38-56` into the Description field) and takes ~5 minutes.

---

*End of consistency review. Reviewer is Claude Opus 4.7 acting under the navimed-umb halucynacja-watch + verify-external-state discipline. Every claim above is sourced; ResearchGate findings are explicitly flagged `[UNVERIFIED]` due to automated retrieval block.*
