# NaviMed-UMB

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19851346.svg)](https://doi.org/10.5281/zenodo.19851346)
[![Version](https://img.shields.io/badge/version-0.5.2-blue.svg)](https://github.com/kicrazom/navimed-umb/releases/tag/v0.5.2)

**📊 Live dashboard → [NaviMed-UMB](https://kicrazom.github.io/navimed-umb/)** — interactive hardware-envelope table, model cards, and methodology.

Reproducible benchmark suite, model-card releases, and methodology for
deploying Polish clinical large-language-model inference on a consumer-grade
AMD RDNA 4 workstation (2× Radeon AI PRO R9700, gfx1201) — under ROCm 7.2 and
vLLM 0.19.

The project began as a workstation engineering log and has grown into the
infrastructure underlying a series of forthcoming methodology, quantization,
and clinical-AI papers. It is the L1 pillar
of a three-layer architecture (workstation → retrieval → arena) targeted at
sovereign, on-premise medical-AI deployment.

**Operating principle: scientific rigor over time and cost.** Tier-A campaigns use
n = 10 fresh-process repetitions per `(quant, TP, N)` cell, with cooldowns and
median-based descriptive statistics; earlier Tier-0 runs are exploratory
single shots (see [`METHODOLOGY.md`](METHODOLOGY.md) §7.4–7.5). Comparisons use
two-sided Mann–Whitney U tests, Holm–Bonferroni correction, and effect sizes.
The Holm family is the eight-point ladder including N = 1
(`METHODOLOGY.md` 1.9, §7.4).

> **Security note.** This repository documents a workstation build, public
> benchmarks, and external release pipelines. Secrets and patient data must be
> omitted. The repository configures pre-commit `detect-secrets` and requires
> per-artifact embargo classification (`METHODOLOGY.md` §11); these controls
> do not establish that every historical artifact was checked.

## What's inside

| Directory | What it holds |
|---|---|
| [`bom/`](bom/) | Hardware bill of materials, power topology, UPS integration, PCIe map |
| [`environment/`](environment/) | Dated software/system manifests (pip freeze, ROCm, kernel) for reproducibility, plus sanity-test JSONs and coherence-probe outputs per release campaign |
| [`benchmarks/`](benchmarks/) | vLLM / ROCm benchmark harness (Phase 1 envelope + Phase 2 scaling sweep), methodology, plotting scripts, and per-model results (`benchmarks/results/` is gitignored — embargo-protected per §11) |
| [`scripts/`](scripts/) | Orchestration scripts: `sanity_sweep_pllum70b_awq.sh` (three-stage Gate 1/2/3 runner), `kill_port.sh` (process-isolated cleanup), `_env.sh` (gfx1201 env vars) |
| [`calibration/`](calibration/) | Polish clinical SmPC corpus (published on HuggingFace), its English counterpart, and quantization scripts — separately licensed |
| [`ai-workstation-dashboard/`](ai-workstation-dashboard/) | Real-time CPU/GPU monitoring (FastAPI + psutil + rocm-smi) |
| [`docs/sessions/`](docs/sessions/) | Long-form engineering session reports and debugging logs (one per substantive session) |
| [`logbook/`](logbook/) | Short chronological build-diary entries (one per day of substantive activity) |
| `history/` (local only) | Layer 1 raw session logs imported from external assistants (Claude, GPT) — append-only, gitignored |
| `literature/` (local only) | Source-of-truth references for papers and tools cited in the project — gitignored |
| `logs/` (local only) | Per-run sweep logs (gitignored; embargo-protected) |

## Key documents

- [`METHODOLOGY.md`](METHODOLOGY.md) — version 1.9 (2026-10-08): universal Phase 1 envelope + Phase 2 scaling protocol, the §8 vehicle-integrity boundary, and the §11.1/§11.2/§11.3 embargo classification applied across the 21-model suite. Cross-stack work remains deferred to v0.7 (§4.7).
- [Reproduce](site/reproduce.html) — software pins, required environment variables, and kernel parameters.
- [`RELEASES.md`](RELEASES.md) — per-release notes (v0.1.0 → v0.5.2) and between-version events (the 2026-05-23 public Llama-PLLuM-70B AWQ release and the 2026-05-26 Run-3 consumer-GPU 8B/12B AWQ release live here).
- [`CITATION.cff`](CITATION.cff) — canonical citation (or use GitHub's "Cite this repository").
- [`AI_USAGE_DISCLOSURE.md`](AI_USAGE_DISCLOSURE.md) — disclosure of generative-AI assistance, including the locally-served Bielik-11B that proofread documentation in May 2026.

## Platform at a glance

AMD Ryzen 9 9950X3D · 2× GIGABYTE Radeon AI PRO R9700 32 GB (gfx1201, RDNA 4) ·
96 GB DDR5-6000 · Kubuntu 24.04 · ROCm 7.2.0 · vLLM 0.19.0+rocm721 ·
PyTorch 2.10.0+git8514f05 · transformers 5.8.1 (v0.3+ protocol).
CPU↔GPU interconnect:
**PCIe Gen4 x8/x8, measured on the root ports** — see [`bom/pci-topology.md`](bom/pci-topology.md)
for why the endpoint x16 reading is misleading. Benchmark campaigns were collected under
kernel 6.17 (the April manifest records 6.17.0-22-generic); the 2026-08-23
cooling record uses kernel 7.0.0-30 with an NL-LC1-42 AIO (cooler swap
2026-08-23, measured thermally neutral under
sustained all-core load — [`bom/cooling-test/report.md`](bom/cooling-test/report.md)).
Full BOM and power topology: [`bom/readme.md`](bom/readme.md).
Dated software manifests: [`environment/`](environment/) (the full pip freeze is
from 2026-04-26, before the transformers 5.8.1 update).
The documented campaign kernel parameters are `quiet splash`, with
`GRUB_CMDLINE_LINUX` empty (§3.1a). Since 2026-08-30,
`throughput_sweep_v0.3.py` records `kernel_cmdline` per run, redacting
`root=UUID=` and `BOOT_IMAGE=`; this does not backfill earlier records.
See [Reproduce](site/reproduce.html) and [`METHODOLOGY.md`](METHODOLOGY.md) §2.1
for the BIOS 1715 concurrency-ladder / BIOS 2202 single-stream-anchor boundary.

## Public artifacts

Released as part of (or alongside) this repository:

- **Ten HuggingFace model cards** — the Llama-PLLuM-70B family (`mozarcik/Llama-PLLuM-70B-{base,instruct,chat}-{2412,2508,2512}-awq`, 8 variants, 2× R9700 / TP=2 deployment target), plus two Run-3 consumer-GPU variants released 2026-05-26 fitting on a single R9700: `mozarcik/Llama-PLLuM-8B-chat-2512-awq` (Llama 3.1 base) and `mozarcik/PLLuM-12B-chat-2512-awq` (Mistral-Nemo base). To the author's knowledge the first public AWQ W4A16 / vLLM-native quantization of each variant. [`huggingface.co/mozarcik`](https://huggingface.co/mozarcik).
  The corrected [Bielik-11B-v3.0-Instruct-AWQ entry](site/results.html) attributes the checkpoint to the vendor-released SpeakLeash AWQ (revision `0de6dd1`); it was not quantised here.
- **One HuggingFace dataset** — [`mozarcik/clinical-pl-smpc-awq-calibration`](https://huggingface.co/datasets/mozarcik/clinical-pl-smpc-awq-calibration), 418 fragments of Polish *Charakterystyka Produktu Leczniczego* (ChPL / SmPC) text from EMA, ~512 tokens each, covering 61 medicines drawn from a curated catalog of 81 INN across 9 NFZ drug programmes (pulmonology + thoracic oncology focus; No PHI). Reusable as a calibration corpus for other Polish-clinical quantization work.
- **One companion tool** — [`kicrazom/leChatonFat4Navi`](https://github.com/kicrazom/leChatonFat4Navi), an AMD fork of leChatonFat: a local model provider for the Opencode coding agent on 2× R9700, with llama.cpp (ROCm / Vulkan, GGUF), SGLang and vLLM (safetensors) as engines, SearXNG search and MCP tools. Tool calls tested with Bielik-11B-v3.1. Not part of the benchmark envelope; measured figures in its README and on the [Harness page](https://kicrazom.github.io/navimed-umb/lechat.html).
- **One LinkedIn announcement** — [activity 7464059097575907328](https://www.linkedin.com/posts/lukasz-minarowski-73b3233b_navimed-umb-hardware-envelope-studies-for-activity-7464059097575907328).
- **One Zenodo deposit** — concept DOI [10.5281/zenodo.19851346](https://doi.org/10.5281/zenodo.19851346) (auto-resolves to latest version; current version v0.5.2 at [10.5281/zenodo.24206670](https://doi.org/10.5281/zenodo.24206670); v0.5.1 at [10.5281/zenodo.22070559](https://doi.org/10.5281/zenodo.22070559); v0.5.0 at [10.5281/zenodo.21207763](https://doi.org/10.5281/zenodo.21207763); previous v0.4.0 at [10.5281/zenodo.20364953](https://doi.org/10.5281/zenodo.20364953)).

## Status

Current release: **v0.5.2** (2026-11-13) — methodology-and-documentation release:
METHODOLOGY 1.8 and 1.9 (power as the card sum over the generation window, the
eight-point Holm family, Bielik roster correction), per-run kernel-parameter records,
the N = 1 anchor gap-fill, and a companion [Harness](https://kicrazom.github.io/navimed-umb/lechat.html)
page. No new public benchmark results; the §11.2/§11.3 embargo is unchanged.
Previous: **v0.5.1** (2026-08-23) — PCIe topology erratum and CPU-cooling study.
Full release history and per-version highlights: [`RELEASES.md`](RELEASES.md).

The 2026-08-23 release added a CPU-cooling A/B/C study
([`bom/cooling-test/`](bom/cooling-test/)) — air tower vs 420 mm AIO, one run
invalidated as a no-airflow artifact and retained as a negative control, verdict
thermal parity under sustained all-core load; a **PCIe topology erratum**
([`bom/pci-topology.md`](bom/pci-topology.md)) — the CPU↔GPU links are a symmetric
x8/x8 Gen4 measured on the root ports, not the "full x16 each" previously read off
the card-internal endpoints; a bilingual Hardware page and a fan-efficiency page on
the site; and [`scripts/deploy-site.sh`](scripts/deploy-site.sh) for reproducible
GitHub Pages deploys. Per-N throughput/latency/power numbers remain embargoed
§11.2/§11.3 pending paper acceptance; engineering envelope, methodology, and site
documentation are public.

## AI assistance

This project is developed with generative-AI assistance: cloud language models
(Anthropic Claude, OpenAI GPT, Google Gemini) for orchestration, analysis, code,
drafting and review, and open-weight models served locally on the project's own
R9700 hardware for Polish-language proofreading. AI tools do not produce
measurements: every number comes from instrumented runs on the workstation.
All experimental design, hardware configuration, empirical results and scientific
claims are the sole responsibility of the author. Which tools were used, for what
and when is recorded in [`AI_USAGE_DISCLOSURE.md`](AI_USAGE_DISCLOSURE.md);
per-change attribution is in the `Co-Authored-By` trailers of the Git history.

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
