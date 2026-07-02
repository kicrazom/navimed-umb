#!/usr/bin/env Rscript
# =============================================================================
# power_efficiency_plots.R
#
# Within-study energy-efficiency figures (PAPER-grade: all measured, no
# cross-hardware speculation): perf-per-watt (tok/J) and watt-per-token (J/tok)
# per model at its best operating point. Reads power_efficiency_dataset.csv
# (from aggregate_power_efficiency.py). Cleveland dot plot on log-x (80x spread).
# EMBARGO §11.3. Run from repo root.
# =============================================================================
suppressMessages({library(dplyr); library(tidyr); library(ggplot2); library(scales)})

fig <- "paper/figures"
out <- file.path(fig, "R"); dir.create(out, showWarnings = FALSE, recursive = TRUE)
d <- read.csv(file.path(fig, "power_efficiency_dataset.csv"), stringsAsFactors = FALSE)

# best operating point per model = max tok/J (== min J/tok)
best <- d %>%
  group_by(model, family, tier, quant) %>%
  slice_max(tok_per_J_med, n = 1, with_ties = FALSE) %>%
  ungroup() %>%
  mutate(label = sprintf("%s [%s TP%s @N%d]", model, quant, TP, N))
best$label <- factor(best$label, levels = best$label[order(best$tok_per_J_med)])

long <- best %>%
  select(label, family,
         `perf/W (tok/J, higher better)` = tok_per_J_med,
         `energy (J/tok, lower better)`  = J_per_tok_med) %>%
  pivot_longer(-c(label, family), names_to = "metric", values_to = "value")

p <- ggplot(long, aes(value, label, colour = family)) +
  geom_point(size = 2.4) +
  facet_wrap(~ metric, scales = "free_x") +
  scale_x_log10(labels = label_number()) +
  labs(x = NULL, y = NULL, colour = NULL,
       title = "NaviMed R9700 - energy efficiency at best operating point (per model)",
       subtitle = "perf/W = tok_s_out / power_mean_w (median over reps); energy = reciprocal. Mean wall power.") +
  theme_bw(base_size = 9) +
  theme(legend.position = "bottom")
ggsave(file.path(out, "energy_efficiency.png"), p, width = 11, height = 6, dpi = 150)
ggsave(file.path(out, "energy_efficiency.pdf"), p, width = 11, height = 6)

write.csv(best %>% select(family, tier, model, quant, TP, N,
                          tok_per_J_med, J_per_tok_med, power_w_med, tok_s_med),
          file.path(out, "energy_efficiency_best.csv"), row.names = FALSE)
message("wrote energy_efficiency.{png,pdf} + energy_efficiency_best.csv")
