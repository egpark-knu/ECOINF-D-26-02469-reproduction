# P2c v4 implementation report

STATUS: COMPLETE_VERIFIED_V4

## Result

Fresh v4 code rebuilt daily index-specific pixel-weighted composites, exact-filtered
in-situ endpoints, outcome-blind minimum-lag matchups, fixed association analyses,
paired whole-weir uncertainty, leave-one-weir-out diagnostics, observation-frequency
accounting, station–reach closure, and the study-area map. No v3 implementation or
numerical result was reused.

NDCI endpoint conclusion: **not_robust**. FAI remains a secondary analysis.
Adverse or null contrasts are retained without optimization for significance.

## Observed satellite site-date support

`observation_frequency_v4.csv` contains exactly 16 sites × 9 years = 144 rows,
including zero cells. Annual achieved site-date totals are:

- 2017: 60 site-dates
- 2018: 75 site-dates
- 2019: 243 site-dates
- 2020: 261 site-dates
- 2021: 232 site-dates
- 2022: 241 site-dates
- 2023: 200 site-dates
- 2024: 258 site-dates
- 2025: 222 site-dates

2017–2018 are labelled `observed_low_coverage=true` and
`archive_cause_verified=false`. Official global early-L2A incompleteness is context,
not proof of the local achieved-count cause. The 2019–2025 accounting is preserved
as an explicit sensitivity period.

## Reproducibility and boundaries

The documented clean command is:

```text
python v4_build.py --out-dir ../../output/P2c/v4
```

The same command with another empty output directory is used for the clean rebuild.
The final verifier records named scientific, semantic, provenance, map, LOO,
bootstrap, and deterministic-rebuild gates with evidence. Percentile bootstrap
intervals are primary; no bootstrap p-values are computed.

This analysis is post-result exploratory corrective evidence at the weir-reach and
near-coincident-date scale. It is not point ground validation. Dedicated
cloud-shadow masking was absent; QA60 nominal support (60 m) differs from the 20-m
index reduction; and 5-km buffers can mix upstream lentic and downstream lotic
water. These limitations remain unquantified.

## Verification execution

- `python -m unittest discover -s tests_v4 -v`: PASS, 13 tests.
- `python v4_build.py --out-dir ../../output/P2c/v4`: PASS; 3,965 matchup rows, 288,000 bootstrap rows, and 1,536 LOO rows.
- `python v4_build.py --out-dir ../../output/P2c/v4_clean_rebuild`: PASS with the same row counts from another empty directory.
- `python v4_finalize.py --primary ../../output/P2c/v4 --rebuild ../../output/P2c/v4_clean_rebuild`: PASS; 17 named gates and 17 byte-identical built artifacts.

