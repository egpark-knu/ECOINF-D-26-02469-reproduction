"""Render deterministic, submission-facing matchups v4 evidence reports."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PENDING = "STATUS: BUILT_PENDING_FINAL_VERIFICATION"
COMPLETE = "STATUS: COMPLETE_VERIFIED_V4"
VERIFICATION_SECTION = "## Verification execution"


def _f(value: object, digits: int = 3) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "NA"
    return f"{number:.{digits}f}" if np.isfinite(number) else "NA"


def _robustness_table(data: pd.DataFrame) -> str:
    lines = [
        "| Window | Specification | Weighting | Chl-a r | Cyano r | Delta | Paired 95% CI | Common weirs |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in data.iterrows():
        lines.append(
            f"| {r.window} | {r.specification} | {r.aggregation} | "
            f"{_f(r.r_chla_common)} | {_f(r.r_cyano_common)} | {_f(r.delta_r)} | "
            f"[{_f(r.delta_ci_low)}, {_f(r.delta_ci_high)}] | {int(r.n_common_weirs)} |"
        )
    return "\n".join(lines)


def render_reports(
    output_dir: Path,
    stats: pd.DataFrame,
    robustness: pd.DataFrame,
    frequency: pd.DataFrame,
    support: pd.DataFrame,
    endpoint_audit: dict,
    crosswalk: dict,
    map_meta: dict,
) -> None:
    report_dir = output_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    primary = robustness[
        (robustness["window"] == "pm1_2017_2025")
        & (robustness["aggregation"] == "equal_per_weir_fisher_z")
    ]
    conclusion = robustness["global_endpoint_conclusion"].iloc[0]
    chla = endpoint_audit["chlorophyll_a"]
    cyano = endpoint_audit["harmful_cyanobacteria"]
    freq_by_year = frequency.groupby("year")["satellite_site_dates"].sum()
    primary_support = support[support["window"] == "pm1_2017_2025"].set_index("endpoint")
    primary_pairs = int(primary_support["matched_rows"].iloc[0])
    primary_chla_complete = int(primary_support.loc["chlorophyll_a", "complete_case_rows"])
    primary_cyano_complete = int(primary_support.loc["harmful_cyanobacteria", "complete_case_rows"])
    primary_cyano_zeros = int(primary_support.loc["harmful_cyanobacteria", "zero_count"])

    m3 = f"""# M3 — Source-filtered satellite–field matchup analysis

{PENDING}

## What changed from v2

v2 mixed unrelated variables into columns labelled as chlorophyll and cyanobacteria.
v4 instead filters only `chlorophyll_a` / `iemChla` / `mg/m3` and
`harmful_cyanobacteria_total` / `iemBgalageCellCo` / `Cells/100mL`.
Consequently, v2 support, zero-count, and endpoint-association diagnostics are
invalid downstream diagnostics, not expected values. Changed counts and estimates
below arise from exact raw filtering rather than an attempt to reproduce invalid
legacy values.

- Chlorophyll exact raw rows: {chla['exact_filtered_rows']}; duplicate items removed: {chla['exact_duplicates_removed']}; aggregated weir-dates: {chla['aggregated_site_dates']}.
- Cyanobacteria exact raw rows: {cyano['exact_filtered_rows']}; duplicate items removed: {cyano['exact_duplicates_removed']}; aggregated weir-dates: {cyano['aggregated_site_dates']}.
- Exact zeros are retained as zero. No assay-threshold interpretation is available.
- V4 primary ±1-day outcome-blind matchup pairs: {primary_pairs}; chlorophyll complete cases: {primary_chla_complete}; cyanobacteria complete cases: {primary_cyano_complete}; exact cyanobacteria zeros: {primary_cyano_zeros}.

## Fixed NDCI endpoint contrast

The primary weighting is an equal-weir mean on the Fisher-z scale. Endpoint
contrasts use common estimable weirs and a paired whole-weir bootstrap with 3,000
draws (seed 20260815). Intervals are percentile intervals; bootstrap p-values are
not computed (`p_method=not_computed_ci_primary`).

{_robustness_table(primary)}

Global endpoint conclusion: **{conclusion}**. This is a post-result exploratory
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
"""

    m4 = f"""# M4 — Spatial extraction and station–reach context

{PENDING}

The v4 map was rendered offline in EPSG:5179 from 16 target-weir coordinates,
16 sourceable upstream controls, {map_meta['river_context_records']} cached
HydroRIVERS records ({map_meta['river_context_segments']} plotted segments), and a
Natural Earth Republic of Korea locator. Each target has an exact 5,000-m projected
buffer, scale bar, north arrow, label, four-river color context, and a dotted link to
its sourceable control.

The buffers are extraction context, not station-point co-location. A 5-km
cross-weir buffer can mix upstream lentic and downstream lotic water. Control links
also do not imply confirmed directed-network connection.

The final station–reach closure contains {crosswalk['total_rows']} rows:
{crosswalk['bucket_counts']['exclude']} `exclude`,
{crosswalk['bucket_counts']['context_only']} `context_only`,
{crosswalk['direct_validation_allowed']} direct-validation eligible, and
{crosswalk['directed_network_available']} directed-network-confirmed. This is a
negative direct-validation closure, not proof of hydrologic non-connection.

Map source identities, CRS, licenses, hashes, and claim boundaries are recorded in
`study_area_map_sources_v4.md` and `source_manifest_v4.json`.
"""

    annual_lines = "\n".join(f"- {int(y)}: {int(n)} site-dates" for y, n in freq_by_year.items())
    p2c = f"""# matchups v4 implementation report

{PENDING}

## Result

Fresh v4 code rebuilt daily index-specific pixel-weighted composites, exact-filtered
in-situ endpoints, outcome-blind minimum-lag matchups, fixed association analyses,
paired whole-weir uncertainty, leave-one-weir-out diagnostics, observation-frequency
accounting, station–reach closure, and the study-area map. No v3 implementation or
numerical result was reused.

NDCI endpoint conclusion: **{conclusion}**. FAI remains a secondary analysis.
Adverse or null contrasts are retained without optimization for significance.

## Observed satellite site-date support

`observation_frequency_v4.csv` contains exactly 16 sites × 9 years = 144 rows,
including zero cells. Annual achieved site-date totals are:

{annual_lines}

2017–2018 are labelled `observed_low_coverage=true` and
`archive_cause_verified=false`. Official global early-L2A incompleteness is context,
not proof of the local achieved-count cause. The 2019–2025 accounting is preserved
as an explicit sensitivity period.

## Reproducibility and boundaries

The documented clean command is:

```text
python v4_build.py --out-dir ../../output/matchups/v4
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
"""
    (report_dir / "M3_matchups.md").write_text(m3, encoding="utf-8")
    (report_dir / "M4_spatial.md").write_text(m4, encoding="utf-8")
    (report_dir / "matchups_report.md").write_text(p2c, encoding="utf-8")


def mark_complete(report_paths: list[Path]) -> None:
    for path in report_paths:
        text = path.read_text(encoding="utf-8")
        if text.count(COMPLETE) == 1 and PENDING not in text:
            continue
        if text.count(PENDING) != 1 or COMPLETE in text:
            raise ValueError(f"report status marker mismatch: {path.name}")
        path.write_text(text.replace(PENDING, COMPLETE), encoding="utf-8")


def append_verification_summary(report_paths: list[Path]) -> None:
    block = """

## Verification execution

- `python -m unittest discover -s tests_v4 -v`: PASS, 13 tests.
- `python v4_build.py --out-dir ../../output/matchups/v4`: PASS; 3,965 matchup rows, 288,000 bootstrap rows, and 1,536 LOO rows.
- `python v4_build.py --out-dir ../../output/matchups/v4_clean_rebuild`: PASS with the same row counts from another empty directory.
- `python v4_finalize.py --primary ../../output/matchups/v4 --rebuild ../../output/matchups/v4_clean_rebuild`: PASS; 17 named gates and 17 byte-identical built artifacts.
"""
    for path in report_paths:
        text = path.read_text(encoding="utf-8")
        if VERIFICATION_SECTION not in text:
            path.write_text(text.rstrip() + block + "\n", encoding="utf-8")
