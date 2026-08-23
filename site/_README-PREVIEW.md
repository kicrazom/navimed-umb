# NaviMed-UMB project site — preview & deploy notes

This `site/` directory is a **self-contained static site** (plain semantic HTML + one
CSS file, no JavaScript, no build step). It is **prepared but NOT deployed** — the
owner reviews and approves before anything goes live.

```
site/
├── index.html          # Overview
├── models.html         # Models (released HF artifacts + licenses)
├── methodology.html    # Methodology (public design + references)
├── results.html        # Results (public envelope only)
├── reproduce.html      # Pinned stack + gfx1201 env-var floor
├── cite.html           # DOIs, CITATION, BibTeX, AI-usage disclosure
├── assets/
│   └── style.css       # shared stylesheet
├── .nojekyll           # tell GitHub Pages to serve raw files (skip Jekyll)
└── README-PREVIEW.md   # this file
```

---

## 1. Local preview

No dependencies. From the **repository root**:

```bash
python3 -m http.server -d site 8000
```

Then open <http://localhost:8000/> . Stop with `Ctrl-C`.

(Equivalent: `cd site && python3 -m http.server 8000`.)

---

## 2. Deploy steps — RUN ONLY AFTER OWNER APPROVAL

The site is designed to be published with **GitHub Pages**. Two supported options; pick one.

### Option A — Pages from a `/site` (or `/docs`) folder on `main` (simplest)

GitHub Pages can serve from `/ (root)` or `/docs` on a branch. To use `/docs`,
rename or copy this directory:

```bash
# from repo root, after approval
git checkout -b site-pages          # do NOT work on main directly
git mv site docs                    # Pages "folder" source only accepts / or /docs
git add docs
git commit -m "docs(site): public project site (PUBLIC §11.1 only)"
git push -u origin site-pages
```

Then in **GitHub → Settings → Pages**: Source = *Deploy from a branch*,
Branch = `site-pages` (or `main` after merge) + folder `/docs`. Save.

### Option B — Dedicated `gh-pages` branch (keeps `main` clean)

```bash
# from repo root, after approval — publishes the contents of site/ to gh-pages root
git subtree push --prefix site origin gh-pages
```

Then **GitHub → Settings → Pages**: Source = *Deploy from a branch*,
Branch = `gh-pages` + folder `/ (root)`. Save.

> The `.nojekyll` file is included so GitHub Pages serves the raw HTML/CSS without
> running Jekyll (avoids any `_`-prefixed-path surprises). Keep it in whichever
> directory becomes the Pages source.

### After enabling

- Pages publishes at `https://kicrazom.github.io/navimed-umb/` (project site) within ~1 minute.
- All internal links are **relative** (`models.html`, `assets/style.css`), so the site works
  unchanged under the `/navimed-umb/` path prefix — no `baseurl` config needed.
- Update the README badge / repo "About → Website" field to the Pages URL if desired.

### Rollback

Disable in **Settings → Pages** (Source = *None*), or delete the `gh-pages` branch /
revert the `docs/` commit. No other repo state is touched.

---

## 3. EMBARGO CHECKLIST (METHODOLOGY §11) — re-verify before deploy

This site was built to surface **PUBLIC §11.1 content only**. Confirm each line before
making it public:

- [x] **No per-N throughput** (tok/s) anywhere. The only throughput mentioned is the
      §11.1 "single-prompt sanity / memory-bandwidth baseline" *category name* — no value.
- [x] **No latency numbers** (P50/P95/P99 or any ms/s figure per request).
- [x] **No scaling tables** (throughput@N for N ∈ {10…1000}).
- [x] **No energy-per-token / W-per-token** figures.
- [x] **No KV-cache *occupancy* curves.** (The *static KV-cache budget* in GiB and the
      load-time *max-concurrency envelope* ARE §11.1-public — these are the exact figures
      in the Zenodo v0.4.0 description and the HF model cards; they are NOT a runtime
      occupancy curve.)
- [x] **No cross-model numeric comparisons** and no quantization-vs-quantization
      scaling-law numbers.
- [x] **No box-whisker / scaling-band PLOTS embedded or linked.** Results page explicitly
      explains why they are withheld.
- [x] **AWQ-slower-than-BF16** stated **qualitatively only** — magnitude marked embargoed.
- [x] **`enforce_eager` / chat-template / `/v1/completions`** notes are qualitative
      engineering findings (§11.1), no numbers.
- [x] **Engineering envelope figures present are exactly the published §11.1 set:**
      8B = 5.53 GiB / 22.22 GiB KV / 88.89×; 12B = 8.03 GiB / 19.77 GiB KV / 63.27×
      (sourced verbatim from `docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md`, which is
      the §11.1-clean public envelope).
- [x] **No person's name except the author, Łukasz Minarowski.** No reviewer, collaborator,
      co-author, mentor, or committee-member names anywhere. (The base-model org
      `CYFRAGOVPL` and tool vendors are organisations, not persons.)
- [x] **No paper drafts or outlines** on the site.
- [x] **Nothing sourced from** `benchmarks/results/`, `eval-rag/`, or `paper/` (all
      gitignored / embargoed and never read).
- [x] **No Qwen plateau numbers** from the pre-policy v0.1 `RELEASES.md`.
- [x] Every "missing" number is replaced by the standard phrase: *"embargoed pending
      peer-reviewed publication (METHODOLOGY §11.2/§11.3)."*

**Sources used (all §11.1-clean):** `README.md`, `METHODOLOGY.md` (§1, §7.4, §7.5, §11, §3.1/§3.2),
`CITATION.cff`, `AI_USAGE_DISCLOSURE.md`, `docs/visibility/2026-05-26-zenodo-v0.4.0-draft.md`.
HF artifact list + licenses cross-checked live via the HuggingFace MCP (`hub_repo_details`)
against the `mozarcik/` namespace.

If any box cannot be checked after a content change, **do not deploy** — fix first.
