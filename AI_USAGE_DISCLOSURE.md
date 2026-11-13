# AI Usage Disclosure

> **Document version**: 1.6 (follows `navimed-umb` v0.5.2)
> **Author**: Łukasz Minarowski, MD, PhD
> **Last updated**: 2026-11-13

This document discloses the AI tools used during the development of
this repository and the associated preprint, the roles those tools
played, and the boundaries within which their output was used.
Transparency about AI assistance is a default policy for this project.

---

## 1. Tools used

| Tool | Provider | Version / Model | Interface | Period of use |
|---|---|---|---|---|
| Claude Opus 4.7 | Anthropic | `claude-opus-4-7` | claude.ai web app | Apr 2026 |
| Claude Code (Opus 4.7) | Anthropic | `claude-opus-4-7` | command-line interface, Kubuntu 24.04 LTS | Apr 2026 – May 2026 |
| Claude Opus 4.8 | Anthropic | `claude-opus-4-8` | claude.ai web app + Claude Code CLI | May 2026 – Jul 2026 |
| Claude Fable 5 | Anthropic | `claude-fable-5` | Claude Code subagents (CLI) | Jun 2026 – Jul 2026 |
| Claude Opus 5 | Anthropic | `claude-opus-5` | Claude Code CLI | Aug 2026 – Nov 2026 |
| Claude Opus 5.5 | Anthropic | `claude-opus-5-5` | Claude Code CLI | Oct 2026 – present |
| GPT-5.5 Deep Thinking | OpenAI | GPT-5.5 with extended reasoning | OpenAI web app | Apr 2026 |
| Gemini | Google | (web review) | gemini web app | May 2026 |
| Bielik-11B-v3.0-instruct (AWQ W4A16) | SpeakLeash / consortium | `bielik-11b-v30-instruct-awq` (local) | vLLM 0.19.0+rocm721 on 1× AMD Radeon AI PRO R9700 (gfx1201, TP=1) | May 2026 |

The web apps (claude.ai, OpenAI, Gemini) were used in human-initiated
chat sessions. **Claude Code is different: it is an agentic command-line
tool that runs on the measurement workstation itself.** Within a session it
reads and edits files, runs shell commands, starts scripts and containers,
and commits to Git; from June 2026 it also delegated sub-tasks to subagents.
Every session is started and supervised by the author. Long or
hard-to-reverse actions (benchmark campaigns, releases, pushes to public
repositories, deletions) run only after the author's explicit approval.
Earlier versions of this document (1.0–1.5) stated that no autonomous
agents were used and that AI tools did not access the workstation; for
Claude Code that wording was inaccurate and is corrected here.

A relevant technical detail about Claude Opus 4.7: its knowledge cutoff
is January 2026. The primary empirical finding documented in this
release — the working envelope of Qwen 3.6 27B (released 2026-04-22)
on AMD Radeon AI PRO R9700 GPUs — is therefore strictly post-cutoff
for that model. The model could not have generated those measurements
from training data; it could only react to logs and outputs provided
by the author from local experiments.

### Commit attribution transparency

Two commits in early project history carry explicit `Co-Authored-By: Claude
Opus 4.7` trailers in their commit messages, identifying AI co-authorship at
the commit level per modern git/GitHub disclosure conventions:

- `9a02dfe` (2026-04-25): *docs(benchmarks): add 13-model overview, methodology,
  and Qwen 72B AWQ writeup*
- `426a712` (2026-04-25): *chore(benchmarks): reorganize into scripts/,
  results/<model>/, methodology/, assets/*

Both predate the v0.1.0 release tag and are intentionally retained —
removing them would require rewriting the SHA values archived in Zenodo DOI
10.5281/zenodo.19851347 (v0.1.0) and the v0.2.0 DOI, breaking immutability
guarantees expected of citation records.

From May 2026 onward, commits made in Claude Code sessions carry a
`Co-Authored-By` trailer naming the model as a matter of routine. Count from
the Git history on 2026-11-13 (commits with a trailer, by month):

| Month | Model (trailer) | Commits |
|---|---|---|
| 2026-04 | Claude Opus 4.7 | 2 |
| 2026-05 | Claude Opus 4.7 / Opus 4.8 | 59 / 5 |
| 2026-06 | Claude Opus 4.8 / Fable 5 | 32 / 4 |
| 2026-07 | Claude Opus 4.8 / Fable 5 | 7 / 9 |
| 2026-08 | Claude Opus 5 | 17 |
| 2026-10 | Claude Opus 5.5 | 1 |
| 2026-11 | Claude Opus 5 / Opus 5.5 | 3 / 8 |

The trailers are the per-change record; this document is the summary.
Earlier versions stated that all commits from v0.1.0 onward were attributed
solely to the author; that stopped being true in May 2026.

This is the position consistent with COPE/ICMJE: AI is *not* an author
(Section 3 below), but commit-level acknowledgement of AI assistance during
specific code/documentation operations is appropriate and is preserved here
for the historical record.

---

## 2. Roles

The tools were used for the following classes of tasks:

### Conceptualisation and architectural discussion
- *Tools*: Claude Opus 4.7 (web), GPT-5.5 Deep Thinking (web)
- Sounding-board for repository structure decisions, project framing,
  and methodology trade-offs.
- Iterative refinement of the public-release scope (what to publish
  now vs. what to keep in private notes).
- Strategic review of long-term roadmap.

### Documentation prose
- *Tools*: Claude Opus 4.7 (web), Claude Code (CLI)
- Drafting and editing of `README.md`, `docs/sessions/*.md`,
  `benchmarks/methodology/*.md`, this disclosure, and the v0.1
  preprint.
- Reformulating empirical findings (provided by the author from
  experimental output) into structured narrative.

### Local code and repository operations
- *Tool*: Claude Code (CLI)
- Multi-file edits, `git mv` reorganisation of `benchmarks/`,
  cross-reference updates after directory renames, drafting of
  per-directory `README.md` files based on author-provided structure.

### Debugging dialogue
- *Tool*: Claude Opus 4.7 (web)
- Reading vLLM/ROCm tracebacks pasted by the author, suggesting
  hypotheses about failure modes (memory pressure, kernel
  incompatibility, environment variable mismatch), proposing follow-up
  tests.
- The author executed every test locally and reported the actual
  outcome; the tool never executed code on the workstation.

### Agentic execution on the workstation
- *Tools*: Claude Code (Opus 4.7 → 5.5), with Fable 5 subagents in Jun–Jul 2026
- Running shell commands, launching author-defined or author-approved
  scripts and containers (including some benchmark and sanity runs),
  collecting their raw logs, editing code and documentation, committing.
- The model never supplies a number itself: every figure comes from an
  instrument (benchmark harness, sampler, server timings) whose raw output
  is kept in the repository or its session logs.

### Second-opinion review
- *Tool*: GPT-5.5 Deep Thinking (web)
- Independent review of repository structure proposals and benchmark
  strategy outlines drafted by the author.

---

## 3. Boundaries — what AI did *not* do

The following are entirely the author's responsibility and were not
delegated to any AI tool:

- **Hardware procurement, assembly, and configuration** of the dual
  R9700 workstation, including PCIe topology, power delivery, thermal
  setup, and BIOS tuning.
- **Experimental design**: selection of models, choice of
  configurations to test, definition of pass/fail criteria.
- **Empirical measurements**: every benchmark figure, latency, memory
  footprint, throughput value, and stability outcome was obtained from
  instrumented runs on the author's workstation. Some runs were launched
  by Claude Code at the author's request, executing scripts the author
  defined or approved; the figures are taken from those instruments' raw
  logs. No measurement was generated, estimated, or interpolated by an AI
  tool.
- **Interpretation of results**: claims about what the measurements
  mean (e.g., "BF16 outpaces FP8 by ~75% on R9700 due to missing FP8
  kernel configurations") are author conclusions formed from the data,
  not assertions sourced from AI tools.
- **Final decisions about repository structure, licensing, citation
  format, and what to include or exclude from the public release.**
- **All decisions about scientific scope** of the v0.1 preprint —
  specifically the choice to limit it to the empirical envelope and to
  defer broader strategic claims to future releases.
- **Authorship**: this work has a single author. AI tools are
  documented as research aids, not co-authors. This boundary is
  consistent with current authorship guidelines from the Committee on
  Publication Ethics (COPE) and the International Committee of Medical
  Journal Editors (ICMJE), which exclude AI tools from authorship
  eligibility on the grounds that AI cannot take accountability for
  the work nor consent to authorship.

---

## 4. Verification practice

For every artefact produced with AI assistance, the following
verification steps were applied before commit or release:

1. **Code**: read the diff manually before `git add`. Any commands
   were executed and observed by the author; AI suggestions were never
   committed unverified.
2. **Documentation prose**: every paragraph was read end-to-end and
   edited for accuracy against the author's own knowledge of the
   subject. Any statement that the author could not personally vouch
   for was either rewritten or removed.
3. **Numerical values**: every measurement, version number, and
   technical specification was either taken directly from local logs
   or cross-checked against authoritative sources (vendor
   documentation, official release notes, model cards).
4. **Agent-executed runs**: the author reviews the command or script
   before a long run starts and checks the raw log afterwards; reported
   figures are read from the log, not from the agent's summary of it.
5. **External claims**: cross-references to other work (e.g., the
   Digital Spaceport CUDA benchmark mentioned in the preprint) were
   verified by the author against the original source.

The author takes full responsibility for the final content of this
repository and the preprint. AI assistance does not transfer
responsibility.

---

## 5. Versioning and updates

This disclosure document will be updated for each tagged release. If
the tooling profile changes (different models, new tools, removed
tools), a new version will be issued with a changelog entry. Past
versions remain in git history.

| Document version | Repository version | Changes |
|---|---|---|
| 1.0 | v0.1.0 | Initial disclosure: Claude Opus 4.7 (web + CLI), GPT-5.5 Deep Thinking (web). |
| 1.1 | v0.2.0 | Replaced PENDING DOI placeholder with assigned concept DOI (10.5281/zenodo.19851346). Added §1 "Commit attribution transparency" documenting two pre-v0.1.0 `Co-Authored-By: Claude` commits intentionally retained for Zenodo immutability. |
| 1.2 | v0.3.0 | No tooling-profile change: same models (Claude Opus 4.7 web + CLI, GPT-5.5 Deep Thinking web). Version bump to track the v0.3.0 release (version DOI 10.5281/zenodo.20317011). |
| 1.3 | v0.4.0 | Added Gemini (Google, web review) and Bielik-11B-v3.0-instruct-AWQ (local, vLLM 0.19.0+rocm721 on 1× R9700) to the tooling profile, both used during the 2026-05-23 PLLuM-70B AWQ release session for cross-model documentation review and Polish-language editorial. Version DOI 10.5281/zenodo.20364953. |
| 1.4 | v0.4.0 (Run-3 between-version) | No tooling-profile change vs 1.3: same four-tool stack (Claude + GPT + Gemini + Bielik). Version bump to track the 2026-05-26 Run-3 consumer-GPU PLLuM AWQ release (8B Llama base + 12B Mistral-Nemo base). Inherits v0.4.0 version DOI 10.5281/zenodo.20364953. |
| 1.6 | v0.5.2 (follows) | Corrected two statements that had become inaccurate: (1) Claude Code is an agentic CLI running on the workstation (shell, scripts, containers, commits), not a passive assistant; earlier "no autonomous agents / no workstation access" wording is withdrawn; (2) commits since May 2026 routinely carry `Co-Authored-By` trailers, with a per-month count from Git. Added Claude Opus 5 (Aug–Nov 2026) and Opus 5.5 (Oct 2026 –), the "Agentic execution" role, and an agent-run verification step. Inline disclosure (§6) made version-independent. |
| 1.5 | v0.5.0 | Added Claude Opus 4.8 and Claude Fable 5 (Anthropic) to the tooling profile, used from June 2026: Opus 4.8 for orchestration and analysis (claude.ai web + Claude Code CLI), Fable 5 for Claude Code subagent tasks — the RAG-architecture and evidence-percolation site pages, the site redesign, adversarial pre-release review, compute-results table extraction and benchmark-figure generation, repository-consistency auditing, and RAG backend-abstraction code — in every case operating on the author's own measured data and decisions, never generating measurements, statistics, or scientific claims. Version DOI assigned on v0.5.0 release. |

---

## 6. Inline disclosure for citing this work

The following short paragraph is the canonical inline disclosure for
papers, posters, and external presentations citing this repository.
Authors may copy it verbatim or paraphrase, with attribution to this
document for full detail:

> *"This work used generative-AI assistants (Anthropic Claude via claude.ai
> and the Claude Code agentic command-line tool; OpenAI GPT and Google
> Gemini via web apps) for documentation, code, analysis, debugging and
> review. Claude Code operated on the measurement workstation under the
> author's supervision and, in some sessions, launched author-approved
> scripts and benchmark runs; it did not generate any measurement. All
> experimental design, hardware configuration, empirical results and
> scientific claims are the sole responsibility of the author. Full
> disclosure: AI_USAGE_DISCLOSURE.md in the project repository
> (DOI: 10.5281/zenodo.19851346)."*

---

## 7. Contact

Questions about AI usage in this project, requests for further
specificity about any particular section of the work, or concerns
about the boundaries described above:

**Łukasz Minarowski**
Department of Respiratory Physiopathology
Medical University of Białystok, Poland
ORCID: [0000-0002-2536-3508](https://orcid.org/0000-0002-2536-3508)

---

*This disclosure is licensed under CC-BY-4.0, identical to the rest of
the documentation in this repository. It may be reused as a template
for similar disclosure in other AI-assisted scientific projects, with
attribution.*
