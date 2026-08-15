# M3 — Source-filtered satellite–field matchup analysis

STATUS: COMPLETE_VERIFIED_V4

## What changed from v2

v2 mixed unrelated variables into columns labelled as chlorophyll and cyanobacteria.
v4 instead filters only `chlorophyll_a` / `iemChla` / `mg/m3` and
`harmful_cyanobacteria_total` / `iemBgalageCellCo` / `Cells/100mL`.
Consequently, v2 support, zero-count, and endpoint-association diagnostics are
invalid downstream diagnostics, not expected values. Changed counts and estimates
below arise from exact raw filtering rather than an attempt to reproduce invalid
legacy values.

- Chlorophyll exact raw rows: 6751; duplicate items removed: 3; aggregated weir-dates: 6748.
- Cyanobacteria exact raw rows: 6748; duplicate items removed: 3; aggregated weir-dates: 6745.
- Exact zeros are retained as zero. No assay-threshold interpretation is available.
- V4 primary ±1-day outcome-blind matchup pairs: 756; chlorophyll complete cases: 756; cyanobacteria complete cases: 756; exact cyanobacteria zeros: 234.

## Fixed NDCI endpoint contrast

The primary weighting is an equal-weir mean on the Fisher-z scale. Endpoint
contrasts use common estimable weirs and a paired whole-weir bootstrap with 3,000
draws (seed 20260815). Intervals are percentile intervals; bootstrap p-values are
not computed (`p_method=not_computed_ci_primary`).

| Window | Specification | Weighting | Chl-a r | Cyano r | Delta | Paired 95% CI | Common weirs |
|---|---|---|---:|---:|---:|---:|---:|
| pm1_2017_2025 | raw_within_weir_pearson | equal_per_weir_fisher_z | 0.451 | 0.378 | 0.073 | [-0.025, 0.201] | 13 |
| pm1_2017_2025 | site_by_calendar_month_pearson | equal_per_weir_fisher_z | 0.430 | 0.189 | 0.241 | [0.135, 0.360] | 13 |
| pm1_2017_2025 | within_weir_percentile_midrank | equal_per_weir_fisher_z | 0.471 | 0.423 | 0.047 | [-0.035, 0.150] | 13 |

Global endpoint conclusion: **not_robust**. This is a post-result exploratory
corrective analysis and does not establish point ground validation. FAI is included
in `matchup_statistics_v4.csv` as a secondary association analysis, without an
endpoint-superiority claim.

## Dependence and sensitivity

The machine-readable outputs include ±1-day primary, nested ±2/±3-day windows,
the 2019–2025 ±1-day restriction, three frozen specifications, equal-observation
sensitivity, 3,000 draw-level cluster-bootstrap records per analysis cell, and real
leave-one-weir-out estimates. Calendar-month attenuation is interpreted only as
consistent with shared seasonality.

## Remote-sensing limitations

The source export used Sentinel-2 SR Harmonized, scene cloudiness below 30%, a JRC
surface-water occurrence mask, QA60 opaque/cirrus bits, and 20-m index reduction.
A dedicated cloud-shadow product was absent. QA60 nominal support is 60 m whereas
index reduction used 20 m. A 5-km cross-weir buffer can mix upstream lentic and
downstream lotic water. These limitations remain unquantified.

## Verification execution

- `python -m unittest discover -s tests_v4 -v`: PASS, 13 tests.
- `python v4_build.py --out-dir ../../output/P2c/v4`: PASS; 3,965 matchup rows, 288,000 bootstrap rows, and 1,536 LOO rows.
- `python v4_build.py --out-dir ../../output/P2c/v4_clean_rebuild`: PASS with the same row counts from another empty directory.
- `python v4_finalize.py --primary ../../output/P2c/v4 --rebuild ../../output/P2c/v4_clean_rebuild`: PASS; 17 named gates and 17 byte-identical built artifacts.

