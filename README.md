# NaviMed-UMB

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19851346.svg)](https://doi.org/10.5281/zenodo.19851346)
[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](https://github.com/kicrazom/navimed-umb/releases/tag/v0.3.0)

Engineering log of a local AI / LLM workstation build — hardware, power
infrastructure, ROCm environment, and reproducible benchmarks for modern
open-weight models on consumer-grade AMD RDNA 4 GPUs (2× Radeon AI PRO
R9700, gfx1201).

> **Security note:** This repository documents a workstation build and
> experiments. Operational details such as hostnames, domains, network
> addresses, and secrets are intentionally omitted.

## What's inside

| Directory | What it holds |
|---|---|
| [`bom/`](bom/) | Hardware bill of materials, power topology, UPS integration, PCIe map |
| [`environment/`](environment/) | Dated software/system manifests (pip freeze, ROCm, kernel) for reproducibility |
| [`benchmarks/`](benchmarks/) | vLLM / ROCm benchmark harness, methodology, and per-model results |
| [`calibration/`](calibration/) | Clinical-PL SmPC corpus for AWQ quantization of Polish LLMs — separately licensed |
| [`ai-workstation-dashboard/`](ai-workstation-dashboard/) | Real-time CPU/GPU monitoring (FastAPI + psutil + rocm-smi) |
| [`docs/sessions/`](docs/sessions/) | Long-form engineering session reports and debugging logs |
| [`logbook/`](logbook/) | Short chronological build-diary entries |
| [`paper/`](paper/) | Preprint in preparation extracting the empirical envelope findings |

## Key documents

- [`METHODOLOGY.md`](METHODOLOGY.md) — universal Phase 1 envelope + Phase 2 scaling protocol, applied across the 21-model suite.
- [`RELEASES.md`](RELEASES.md) — per-release notes (v0.1.0 → v0.3.0): scope, headline findings, scaling results.
- [`CITATION.cff`](CITATION.cff) — canonical citation (or use GitHub's "Cite this repository").
- [`AI_USAGE_DISCLOSURE.md`](AI_USAGE_DISCLOSURE.md) — disclosure of generative-AI assistance.

## Platform at a glance

AMD Ryzen 9 9950X3D · 2× GIGABYTE Radeon AI PRO R9700 32 GB (gfx1201, RDNA 4) ·
96 GB DDR5-6000 · Kubuntu 24.04, kernel 6.17, ROCm 7.2.1 · vLLM 0.19.0.
Full BOM and power topology: [`bom/readme.md`](bom/readme.md).
Exact software manifests: [`environment/`](environment/).

## Status

Current release: **v0.3.0** — Phase 2 v0.3 sweep harness + 21-model suite.
Full release history and per-version highlights: [`RELEASES.md`](RELEASES.md).

## AI assistance

This work was developed with assistance from generative AI tools (Claude
Opus 4.7 web and Claude Code CLI; GPT-5.5 Deep Thinking web) used as research
assistants for documentation, debugging dialogue, and sounding-board
discussion. All experimental design, hardware configuration, empirical
measurements, and scientific claims are the sole responsibility of the
author. Full disclosure: [`AI_USAGE_DISCLOSURE.md`](AI_USAGE_DISCLOSURE.md).

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

*This is the engineering log of an academic build with all the seriousness
that implies, and a little less. For a non-serious take on the LLM
benchmarking landscape, see
[`benchmarks/assets/battle_of_LLM_models_gemini.png`](benchmarks/assets/battle_of_LLM_models_gemini.png).*
