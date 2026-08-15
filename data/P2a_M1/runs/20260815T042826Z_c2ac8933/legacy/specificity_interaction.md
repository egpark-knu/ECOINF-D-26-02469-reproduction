# Standardized Tau Specificity Interaction

Primary outcome scaling: z-scored log1p outcome within each season-specific estimation sample.
Primary inference: randomization p-value from permuting residence time within year. Secondary intervals are weir wild-bootstrap CIs for single-outcome slopes and weir-clustered CIs for stacked interactions.

## Standardized single-outcome tau slopes

| season_label           | outcome       |   beta_log1p_tau |   secondary_ci_low |   secondary_ci_high | ri_p_right_positive_tau   |   n |
|:-----------------------|:--------------|-----------------:|-------------------:|--------------------:|:--------------------------|----:|
| Annual                 | cyano         |           0.6874 |             0.5016 |              0.8730 | p < 0.001                 | 144 |
| Annual                 | chlorophyll_a |           0.1476 |            -0.2054 |              0.5011 | p=0.003                   | 144 |
| Bloom season (Jun-Oct) | cyano         |           0.6186 |             0.4340 |              0.8091 | p < 0.001                 | 144 |
| Bloom season (Jun-Oct) | chlorophyll_a |           0.3216 |            -0.0260 |              0.6785 | p < 0.001                 | 144 |

## Formal stacked interaction

| season_label           |   interaction_beta_cyano_minus_chla |   cluster_ci_low |   cluster_ci_high | ri_p_right_cyano_gt_chla   |   n_original_weir_years |
|:-----------------------|------------------------------------:|-----------------:|------------------:|:---------------------------|------------------------:|
| Annual                 |                              0.8874 |           0.5053 |            1.2696 | p < 0.001                  |                     144 |
| Bloom season (Jun-Oct) |                              1.0351 |           0.7114 |            1.3588 | p < 0.001                  |                     144 |

## Precommitted interpretation

The annual standardized interaction supports stronger tau sensitivity for harmful cyanobacteria than for chlorophyll-a. Manuscript language can describe this as a scale-valid specificity contrast, while still reporting the bloom-season result separately.

## Robustness note

Cyano-only basin-by-year robustness estimates are included in `standardized_tau_models.csv`; they add basin-year fixed effects in place of common year fixed effects while retaining weir fixed effects.

| season_label           |   beta_log1p_tau |   secondary_ci_low |   secondary_ci_high | ri_p_right_positive_tau   |   n |
|:-----------------------|-----------------:|-------------------:|--------------------:|:--------------------------|----:|
| Annual                 |           0.3732 |            -0.1141 |              0.8497 | p < 0.001                 | 144 |
| Bloom season (Jun-Oct) |           0.4376 |             0.0092 |              0.8502 | p < 0.001                 | 144 |
