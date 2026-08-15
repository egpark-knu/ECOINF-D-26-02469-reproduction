# Outcome Scales and Comparability Check

## Current transformations confirmed

The existing Round 6 in-situ tau regressions use annual and bloom-season weir-year panels from:

`/Users/eungyupark/Dropbox/Manuscripts/0_HAB/revision_1/03_analysis/input/P2a_M1/insitu_annual_analysis_panel__83fcf10f.csv`

The panel contains two season scopes:

| season_scope       |   cyano_log1p_n |   chlorophyll_log1p_n |   tau_n |
|:-------------------|----------------:|----------------------:|--------:|
| annual_all_samples |             144 |                   144 |     144 |
| bloom_season_06_10 |             144 |                   144 |     144 |

| outcome | source raw unit | current analysis column | transformation in current model | cross-outcome magnitude comparable before standardization? |
|---|---:|---|---|---|
| harmful cyanobacteria | data.go.kr field unit `Cells/100mL` in the raw panel | `log1p_harmful_cyanobacteria_total_mean` | `log1p(mean harmful_cyanobacteria_total)` within weir-year-season | No. The coefficient is in log cells per unit log residence time. |
| chlorophyll-a | data.go.kr field unit `mg/m3` in the raw panel | `log1p_chlorophyll_a_mean` | `log1p(mean chlorophyll_a)` within weir-year-season | No. The coefficient is in log chlorophyll-a concentration per unit log residence time. |

## Consequence for the headline comparison

The earlier coefficients, including the large harmful-cyanobacteria coefficient and the much smaller chlorophyll-a coefficient, are both log-outcome estimates but are not on a common outcome scale. They are valid within-outcome tau associations, but their raw magnitudes should not be interpreted as a scale-free specificity contrast.

The hardening analysis therefore uses `z_standardized_log1p_outcome` as the primary comparison: each outcome is z-scored within the exact estimation sample for its season scope. The both-log raw-outcome estimates are retained as a robustness description, not as the primary cross-outcome magnitude comparison.

## Precommitted reading rule

The manuscript language should be upgraded only if the stacked standardized interaction supports harmful cyanobacteria responding more strongly than chlorophyll-a. If the interaction is not positive and statistically supported by the randomization test, the headline should be downgraded to a standardized contrast that is descriptive or not statistically distinguishable, depending on the result.
