#!/usr/bin/env bash
# Regenerate the N=1..1000 ladder table + plots from current results.
# ETL (python: bench.log/results_table -> n1_anchor_dataset.csv) -> figures (R).
# Cheap, NO GPU. Idempotent. Call after each anchor batch's SWEEP_COMPLETE.
# EMBARGO §11.3 (paper/figures gitignored).
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 benchmarks/scripts/analysis/aggregate_n1_anchor.py
Rscript benchmarks/scripts/analysis/ladder_table_plots.R 2>&1 | grep -vE 'LC_|locale|during startup' || true
