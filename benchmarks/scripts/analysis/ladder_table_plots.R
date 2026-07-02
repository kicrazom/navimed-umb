#!/usr/bin/env Rscript
# =============================================================================
# ladder_table_plots.R
#
# N-ladder results table + throughput curves for the NaviMed concurrency study.
# Reads canonical_dataset.csv (N in {10..1000}) and, when present, the N=1
# single-stream anchor aggregate (n1_anchor_dataset.csv) -> joins both into one
# N in {1..1000} ladder. Emits:
#   - paper/figures/R/ladder_median_wide.csv   (rows: model/quant/TP, cols: N1..N1000)
#   - paper/figures/R/throughput_vs_N.{png,pdf} (tok/s vs N, log-log, facet by family)
#
# Pure base read.csv + dplyr/tidyr/ggplot2/scales (no readr dependency).
# EMBARGO §11.3: paper/figures/ is gitignored; numbers are paper-bound.
# Run from repo root:  Rscript benchmarks/scripts/analysis/ladder_table_plots.R
# =============================================================================
suppressMessages({library(dplyr); library(tidyr); library(ggplot2); library(scales)})

fig    <- "paper/figures"
outdir <- file.path(fig, "R")
dir.create(outdir, showWarnings = FALSE, recursive = TRUE)

d <- read.csv(file.path(fig, "canonical_dataset.csv"), stringsAsFactors = FALSE)

n1f <- file.path(fig, "n1_anchor_dataset.csv")
if (file.exists(n1f)) {
  d1 <- read.csv(n1f, stringsAsFactors = FALSE)
  d  <- bind_rows(d, d1[, intersect(names(d), names(d1)), drop = FALSE])
  message("N=1 anchor merged: ", nrow(d1), " rows")
} else {
  message("n1_anchor_dataset.csv not present yet -> ladder starts at N=10")
}

d$N      <- as.integer(d$N)
d$config <- paste0(d$model, " [", d$quant, " TP", d$TP, "]")

# --- wide median table (rows = model/quant/TP, cols = N) ---------------------
wide <- d %>%
  select(family, tier, model, quant, TP, N, tok_s_out_median) %>%
  arrange(family, tier, model, TP, N) %>%
  pivot_wider(names_from = N, values_from = tok_s_out_median, names_prefix = "N")
write.csv(wide, file.path(outdir, "ladder_median_wide.csv"), row.names = FALSE)

# --- throughput vs concurrency curves ----------------------------------------
p <- ggplot(d, aes(N, tok_s_out_median, colour = config, group = config)) +
  geom_line(linewidth = 0.5) +
  geom_point(size = 0.9) +
  scale_x_log10(breaks = sort(unique(d$N))) +
  scale_y_log10(labels = comma) +
  facet_wrap(~ family, scales = "free_y") +
  labs(x = "Concurrency N (requests in flight)",
       y = "Output throughput (tok/s, median n=10)",
       title = "NaviMed R9700 - throughput envelope across concurrency",
       colour = NULL) +
  theme_bw(base_size = 9) +
  theme(legend.position = "bottom", legend.text = element_text(size = 6))
ggsave(file.path(outdir, "throughput_vs_N.png"), p, width = 11, height = 7, dpi = 150)
ggsave(file.path(outdir, "throughput_vs_N.pdf"), p, width = 11, height = 7)

message("wrote: ", outdir, "/{ladder_median_wide.csv, throughput_vs_N.png, throughput_vs_N.pdf}")
