# Cooling B+C settled, hardware page, Pages deploy — 2026-08-23

Operational checkpoint. Everything in this session is public (`bom/`, `site/`, `scripts/`);
no embargoed performance numbers (METHODOLOGY §11.2/§11.3). Commits `91df41d..9f0f4ae`.

## Done

- **Cooling test, runs B and C** (`bom/cooling-test/`). B (`lc142`, 00:35): ΔT load 59.9 K,
  Tctl max 86.4 °C — **invalid**: `CPU_Opt` read 0 RPM in every sample across 61 minutes
  (including 40 minutes of stress-ng); the radiator fans were not turning, so the verdict
  "AIO worse by 3.8 K" was an artefact of absent airflow. C (`lc142-fanC`, 08:33, fans
  running at 2162 RPM): ΔT 56.8 K, max 81.2 °C, 5017 MHz, 25 929 bogo-ops/s — **a tie with
  the air tower** (0.7 K below single-run noise, identical Tctl max). Operational verdict:
  the LC1-42 stays.
- **`bom/cooling-test/report.md` rewritten around three runs** (`91df41d`): B kept as a
  negative control, plus sections on the invalidation, the ≥80 % PWM safety requirement,
  the unresolved `CPU_Opt` fans-or-pump question, and the `NA`-masking-zero debt.
- **`plot_cooling_polars.py`** (`91df41d`) — CSV processing in Polars, PL/EN charts as
  separate PNGs, assertions on the A↔C tie and on B remaining an outlier; B drawn as a
  dashed line, labelled as a negative control.
- **`site/cooling-per-rpm.html`** (`7c165a1`, `15e5440`) — new bilingual page: per-revolution
  normalisation (the tower converts rotation into cooling 2.29× better; the AIO fans are
  3.5× quieter per revolution — the effects cancel, hence the tie), before/after photographs
  with EXIF stripped, and the Polars time series. Fix: the page now always opens in English
  (language restore from `localStorage` removed).
- **`site/hardware.html`** (`ee01293`, `95288bc`) — new bilingual page gathering the hardware:
  bill of materials, PCIe topology (x8/x8 plus the measurement gotcha), power and UPS, and
  cooling with a link to cooling-per-rpm. A Hardware entry was added to the nav across all
  10 pages, and the hardware rows duplicated in `reproduce.html` were merged out (software
  pins stay there). Kernel in `index.html` corrected 6.17 → 7.0.0-30 along the way.
- **`bom/pci-topology.md` — correction** (`0fcd025`): the CPU↔GPU link is **x8/x8 measured at
  the root ports** (00:01.1 / 00:01.3, Gen4 16 GT/s). The previous claim "full x16 bandwidth
  each" was a misreading of the GPU endpoints (03:00.0 / 07:00.0 always report x16 @ 32 GT/s
  — that is the card-internal GPU-to-switch link). Added a root-port table and a warning that
  ASPM under-reports `current_link_width` at idle.
- **`scripts/deploy-site.sh`** (`bc5f218`, `9f0f4ae`) — Pages (legacy build from `gh-pages`,
  no workflow) had been stale from 2026-07-11 to 2026-08-23, six weeks; `hardware.html`
  returned 404. The script creates a worktree on `gh-pages`, runs `rsync --delete` from
  `site/` (excluding `_*` local preview tooling), touches `.nojekyll`, commits with the source
  SHA and pushes; `--dry-run` shows the diff first. Fix: `--no-verify` on `gh-pages`, because
  pre-commit found no config in that worktree and aborted the deploy under `set -e`.

## Lesson

A zero on a channel capable of reporting is a measurement, not missing data — writing `NA`
instead of zero in `snap()` masked the signal and cost one run. Details and the fix are in
report.md § Dług; the hardware-boundary record is in `logbook/2026-08-23.md`.

## Open

- Verifications carried over from report.md: % PWM at ~85 °C in BIOS (≥80 % requirement),
  whether `CPU_Opt` reads fans or pump, room background in dBA, and a repeat of run C in
  ~6 months as a coolant-degradation check (baseline: ΔT load 56.8 K).
