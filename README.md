# NaviMed-UMB

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19851346.svg)](https://doi.org/10.5281/zenodo.19851346)
[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](https://github.com/kicrazom/navimed-umb/releases/tag/v0.3.0)

Reproducible benchmark suite, model-card releases, and methodology for
deploying Polish clinical large-language-model inference on a consumer-grade
AMD RDNA 4 workstation (2× Radeon AI PRO R9700, gfx1201) — under ROCm 7.2 and
vLLM 0.19.

The project began as a workstation engineering log and has grown into the
infrastructure underlying a series of forthcoming methodology, quantization,
and clinical-AI papers (see [Roadmap](#roadmap) below). It is the L1 pillar
of a three-layer architecture (workstation → retrieval → arena) targeted at
sovereign, on-premise medical-AI deployment.

> **Security note.** This repository documents a workstation build, public
> benchmarks, and external release pipelines. Operational details — hostnames,
> domains, network addresses, secrets, patient data — are deliberately
> omitted; every artifact in this repo passes through pre-commit
> `detect-secrets` and a per-artifact embargo classification
> (`METHODOLOGY.md` §11).

## What's inside

| Directory | What it holds |
|---|---|
| [`bom/`](bom/) | Hardware bill of materials, power topology, UPS integration, PCIe map |
| [`environment/`](environment/) | Dated software/system manifests (pip freeze, ROCm, kernel) for reproducibility, plus sanity-test JSONs and coherence-probe outputs per release campaign |
| [`benchmarks/`](benchmarks/) | vLLM / ROCm benchmark harness (Phase 1 envelope + Phase 2 scaling sweep), methodology, plotting scripts, and per-model results (`benchmarks/results/` is gitignored — embargo-protected per §11) |
| [`scripts/`](scripts/) | Orchestration scripts: `sanity_sweep_pllum70b_awq.sh` (three-stage Gate 1/2/3 runner), `kill_port.sh` (process-isolated cleanup), `_env.sh` (gfx1201 env vars) |
| [`calibration/`](calibration/) | Polish clinical SmPC corpus for AWQ quantization (separately licensed; published on HuggingFace as a reusable artifact) + quantization scripts |
| [`eval-rag/`](eval-rag/) | Design and outreach drafts for a 5-model RAG evaluation of Polish vs multilingual LLMs on the SmPC corpus (sub-project, BLOCKED on reviewer responses) |
| [`paper/`](paper/) | Preprints in preparation — see [Roadmap](#roadmap) for the four-paper plan |
| [`ai-workstation-dashboard/`](ai-workstation-dashboard/) | Real-time CPU/GPU monitoring (FastAPI + psutil + rocm-smi) |
| [`docs/sessions/`](docs/sessions/) | Long-form engineering session reports and debugging logs (one per substantive session) |
| [`logbook/`](logbook/) | Short chronological build-diary entries (one per day of substantive activity) |
| [`history/`](history/) | Layer 1 raw session logs imported from external assistants (Claude, GPT) — append-only |
| [`literature/`](literature/) | Source-of-truth references for papers and tools cited in the project |
| [`logs/`](logs/) | Per-run sweep logs (gitignored; embargo-protected) |

## Key documents

- [`METHODOLOGY.md`](METHODOLOGY.md) — universal Phase 1 envelope + Phase 2 scaling protocol, the §8 vehicle-integrity boundary, and the §11.1/§11.2/§11.3 embargo classification applied across the 21-model suite.
- [`RELEASES.md`](RELEASES.md) — per-release notes (v0.1.0 → v0.3.0) and between-version events (the 2026-05-23 public Llama-PLLuM-70B AWQ release lives here).
- [`CITATION.cff`](CITATION.cff) — canonical citation (or use GitHub's "Cite this repository").
- [`AI_USAGE_DISCLOSURE.md`](AI_USAGE_DISCLOSURE.md) — disclosure of generative-AI assistance, including the locally-served Bielik-11B that proofread documentation in May 2026.

## Platform at a glance

AMD Ryzen 9 9950X3D · 2× GIGABYTE Radeon AI PRO R9700 32 GB (gfx1201, RDNA 4) ·
96 GB DDR5-6000 · Kubuntu 24.04, kernel 6.17, ROCm 7.2.1 · vLLM 0.19.0.
Full BOM and power topology: [`bom/readme.md`](bom/readme.md).
Exact software manifests: [`environment/`](environment/).

## Public artifacts

Released as part of (or alongside) this repository:

- **Eight HuggingFace model cards** — `mozarcik/Llama-PLLuM-70B-{base,instruct,chat}-{2412,2508,2512}-awq` (8 variants total; to the author's knowledge the first public AWQ W4A16 / vLLM-native quantization of the Llama-PLLuM-70B family). [`huggingface.co/mozarcik`](https://huggingface.co/mozarcik).
- **One HuggingFace dataset** — [`mozarcik/clinical-pl-smpc-awq-calibration`](https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration), 418 fragments of Polish *Charakterystyka Produktu Leczniczego* (ChPL / SmPC) text from EMA, ~512 tokens each, covering 81 INNs and 9 NFZ drug programmes (pulmonology + thoracic oncology focus; No PHI). Reusable as a calibration corpus for other Polish-clinical quantization work.
- **One LinkedIn announcement** — [activity 7464059097575907328](https://www.linkedin.com/posts/lukasz-minarowski-73b3233b_navimed-umb-hardware-envelope-studies-for-activity-7464059097575907328).
- **One Zenodo deposit** — concept DOI [10.5281/zenodo.19851346](https://doi.org/10.5281/zenodo.19851346) (auto-resolves to latest version; current version v0.3.0 at [10.5281/zenodo.20317011](https://doi.org/10.5281/zenodo.20317011)).

## Status

Current release: **v0.3.0** — Phase 2 v0.3 sweep harness + 21-model suite.
Full release history and per-version highlights: [`RELEASES.md`](RELEASES.md).

Most recent activity (2026-05-24): Phase 2 throughput sweep completed on all
six sanity-PASS variants of the Llama-PLLuM-70B AWQ family on the standard
METHODOLOGY §6 N grid `{10, 25, 50, 100, 200, 500, 1000}`. Results are
embargoed §11.2/§11.3 pending paper acceptance; engineering envelope and
walltime are public ([`logbook/2026-05-24.md`](logbook/2026-05-24.md)).

## Roadmap

The repository feeds a coordinated multi-paper publication track tied to the
2026-05 / 2026-06 QAIF AIntern submissions:

| # | Paper (working title) | Venue (target) | Status |
|---|---|---|---|
| 1 | Quantization Trade-offs for Polish Clinical LLMs on AMD RDNA 4 | MDPI Electronics / IEEE Access (Q1) | data complete, draft pending |
| 2 | Polish Bronchoscopy Reports → HL7 v2.3 / ICD-9 / JGP via Local LLMs (`Broncho-Nome`) | JBI / JAMIA Open (Q1) | AIntern proposal |
| 3 | Pattern Burden in tcPCO₂: Persistent Homology of Hypercapnic Episodes (`Capno-Nome`) | Respiratory Medicine / Sensors | AIntern proposal |
| 4a / 4b | NaviMed L2 RAG architecture / L3 Arena methodology (`navimed-rag`) | IEEE Access / JBI / JAMIA Open (Q1) | AIntern proposal |
| ★ | NaviMed: Three-Layer Architecture for Sovereign Clinical Knowledge Management (synthesis) | Patterns (Cell Press, Q1) / NPJ Digital Medicine | habilitation centerpiece |

The synthesis paper (★) is the third pillar of the author's habilitation
plan; papers #1–#4 are its supporting evidence track.

## AI assistance

Developed with generative AI tools — Claude Opus 4.7 (web and Claude Code
CLI), GPT-5.5 Deep Thinking (web), Gemini (web review), and a locally-served
Bielik-11B-v3.0-instruct-AWQ (via vLLM on one R9700, used for Polish-language
proofreading of documentation in May 2026). All experimental design,
hardware configuration, empirical measurements, and scientific claims are
the sole responsibility of the author. Full table: [`AI_USAGE_DISCLOSURE.md`](AI_USAGE_DISCLOSURE.md).

## License

This repository uses **dual licensing**:

- **Code** — [MIT License](LICENSE-CODE).
- **Documentation, methodology, lab logs, benchmark findings** —
  [CC BY 4.0](LICENSE).
- **The `calibration/` dataset** — derived from third-party regulatory
  documents (EMA-published SmPC); governed by [`calibration/LICENSE`](calibration/LICENSE),
  **not** the root CC-BY-4.0 / MIT licenses.

## Author

**Łukasz Minarowski, MD, PhD**
Department of Respiratory Physiopathology
Medical University of Białystok, Poland
ORCID: [0000-0002-2536-3508](https://orcid.org/0000-0002-2536-3508)
Email: lukasz.minarowski@umb.edu.pl

---

*Reproducibility ethic: every piece of work here aims to either pass a
pre-commit gate, leave an audit trail in `logbook/` and `docs/sessions/`,
or be flagged with an explicit embargo classification. For a non-serious
take on the LLM benchmarking landscape, see
[`benchmarks/assets/battle_of_LLM_models_gemini.png`](benchmarks/assets/battle_of_LLM_models_gemini.png).*
