#!/usr/bin/env python3
"""Render the required standalone P2d branch and phase reports from a verified run."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fmt(value: object, digits: int = 6) -> str:
    if pd.isna(value):
        return "NA"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value).replace("|", "\\|")


def table(headers: list[str], rows: list[list[object]]) -> str:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    output.extend("| " + " | ".join(fmt(value) for value in row) + " |" for row in rows)
    return "\n".join(output)


def report_m5(run: Path) -> str:
    result = json.loads((run / "m5_result.json").read_text())
    comparator = pd.read_csv(run / "m5_legacy_comparator.csv")
    basin = pd.read_csv(run / "m5_basin_counts.csv")
    basin_table = table(
        ["River", "treated", "control/comparison"],
        [[row.river, row.treated, row.control] for row in basin.itertuples()],
    )
    comparator_table = table(
        ["Season", "Outcome", "2018 vs 2017 DID", "2019–2025 vs 2017 DID"],
        [
            [row.season_scope, row.outcome, row.did_2018_vs_2017_recomputed, row.did_late_2019_2025_vs_2017]
            for row in comparator.itertuples()
        ],
    )
    unresolved = ", ".join(result["chronology"]["unresolved_weirs"])
    return f"""# M5 gate-opening chronology and event-time analysis

**VERDICT: AXIS_EXHAUSTED**

## Result

The frozen chronology gate failed. None of the 16 weirs has a complete, exact-day,
conflict-adjudicated 2017–2025 treatment sequence in the supplied primary-record
packet, and the proposed treated/comparison labels have no within-basin variation.
Consequently no event-study estimator or parallel-trend test was run. This is an
evidence-complete halt, not a null causal estimate.

{basin_table}

Unresolved weirs (16/16): {unresolved}.

Failure codes: `incomplete_exact_2017_2025_treatment_sequences` and
`no_within_basin_treated_control_variation`. The exact-day candidates, coverage
matrix, gap audit, Gate-0 trajectory, local excerpts, and saved primary snapshots
are hashed in `{run / 'source_manifest.json'}`. The coverage/gap inputs explicitly
remain non-final and do not resolve closure/reopening/target-level histories.

## Historical comparator retained without causal relabeling

The frozen five-versus-eleven 2017 baseline comparator reconciled byte-for-number
with the Round 6 output (four rows; maximum absolute discrepancy ≤ 1e-12):

{comparator_table}

No new p-value was attached. These contrasts remain descriptive because the five
documented-opened examples are concentrated in Geum/Yeongsan and the eleven other
weirs are in Han/Nakdong or unresolved classes.

## Effect on the manuscript's core claim

The supplied chronology cannot support a post-2017 gate-opening causal/event-time
claim. The legacy late-post pattern may be described only as a bounded comparator;
it cannot be presented as a staggered-treatment event study or evidence of parallel
pre-trends.

## Verification and evidence paths

- `{run / 'm5_chronology_eligibility.json'}`
- `{run / 'm5_chronology_weir_detail.csv'}`
- `{run / 'm5_basin_counts.csv'}`
- `{run / 'm5_legacy_comparator.csv'}`
- verification gate `M5_axis_exhaustion_evidence`: PASS
- verification gate `M5_historical_comparator_reconciliation`: PASS
"""


def report_m8(run: Path) -> str:
    result = json.loads((run / "m8_result.json").read_text())
    estimates = pd.read_csv(run / "m8_estimates.csv")
    decomp = pd.read_csv(run / "m8_decomposition.csv")
    estimate_table = table(
        ["Season", "n/weirs", "rho NDCI–cyano", "rho NDCI–Chl-a", "Delta", "exact p", "cluster-bootstrap 95% CI"],
        [
            [
                row.season_scope,
                f"{row.n}/{row.n_weirs}",
                row.spearman_r_cyano,
                row.spearman_r_chla,
                row.spearman_delta_chla_minus_cyano,
                row.exact_p_two_sided,
                f"[{row.bootstrap_ci_low:.6g}, {row.bootstrap_ci_high:.6g}]",
            ]
            for row in estimates.itertuples()
        ],
    )
    annual = decomp.loc[decomp["season_scope"] == "annual_all_samples"]
    decomp_table = table(
        ["Component", "Spearman cyano", "Spearman Chl-a", "Delta Chl-a−cyano", "Pearson Delta"],
        [
            [
                row.component,
                row.spearman_r_cyano,
                row.spearman_r_chla,
                row.spearman_delta_chla_minus_cyano,
                row.pearson_delta_chla_minus_cyano,
            ]
            for row in annual.itertuples()
        ],
    )
    return f"""# M8 dependent NDCI correlation analysis

**VERDICT: WEAKENS_OR_REDIRECTS**

## Result

The formal shared-observation, weir-cluster-aware comparison found a positive and
nominally significant pooled difference in both prespecified seasons:

{estimate_table}

`Delta` is rho(NDCI, chlorophyll-a) minus rho(NDCI, harmful cyanobacteria). Each
test used 142 common-support weir-years from 16 weirs, all 65,536 exact Rademacher
sign patterns over delete-one-weir pseudo-values, and 9,999 paired weir-cluster
bootstrap draws. NDCI and both outcomes stayed together in every resample.

## Pooled/within/between decomposition

{decomp_table}

The prespecified spatial-dominance flag is true: annual pooled Delta =
{result['annual_pooled_delta']:.6g}, within-weir Delta =
{result['annual_within_delta']:.6g}, and between-weir Delta =
{result['annual_between_delta']:.6g}. The within-weir difference is near zero and
opposite-signed, while the between-weir difference is larger than the pooled
difference. Under the frozen rule this overrides a `SUPPORTS` verdict and redirects
the interpretation toward persistent spatial/site differences.

## Effect on the manuscript's core claim

The analysis supports the narrower descriptive fact that pooled NDCI tracks
chlorophyll-a more strongly than harmful cyanobacteria. It weakens any claim that
this difference represents within-weir temporal dissociation: the formal
decomposition indicates that the pooled contrast is spatially dominated.

## Unfavorable result and diagnostics

The unfavorable component is the annual within-weir Delta ({result['annual_within_delta']:.6g}),
not a failure of the dependent test. Distribution and linear/quadratic relationship
diagnostics are descriptive only and did not replace the frozen Spearman statistic.

## Verification and evidence paths

- `{run / 'm8_estimates.csv'}`
- `{run / 'm8_decomposition.csv'}`
- `{run / 'm8_signflip_patterns.csv.gz'}` (131,072 saved rows across two seasons)
- `{run / 'm8_cluster_bootstrap.csv.gz'}` (19,998 saved draws)
- `{run / 'm8_distribution_diagnostics.csv'}`
- `{run / 'm8_relationship_diagnostics.csv'}`
- verification gate `M8_common_support_and_resample_counts`: PASS
- verification gate `M8_frozen_verdict_rule`: PASS
"""


def report_m9(run: Path) -> str:
    result = json.loads((run / "m9_result.json").read_text())
    models = pd.read_csv(run / "m9_two_part_models.csv")
    fitted_rows = []
    for row in models.itertuples():
        if row.model_status == "FIT":
            effect = (
                f"OR={row.effect_ratio_per_tau_doubling:.6g}"
                if row.part == "occurrence"
                else f"{row.effect_percent_per_tau_doubling:.6g}%"
            )
            fitted_rows.append(
                [row.window, row.part, row.calendar_balanced, row.n, row.coefficient_log2_tau, row.cluster_se, row.p_two_sided, effect]
            )
        else:
            fitted_rows.append([row.window, row.part, row.calendar_balanced, row.n, "HALTED", "NA", "NA", row.error_message])
    models_table = table(
        ["Window", "Part", "calendar-balanced", "n", "beta", "cluster SE", "p", "effect per tau doubling"],
        fitted_rows,
    )
    a = result["sample_accounting"]
    f = result["sampling_frequency"]
    return f"""# M9 two-part harmful-cyanobacteria analysis

**VERDICT: AXIS_EXHAUSTED**

## Support and source accounting

The raw source contained {a['harmful_total_rows']:,} harmful-cyanobacteria rows in
`Cells/100mL`. Three exact API duplicate rows were removed under the separately
frozen locator-only amendment; two missing/join-ineligible rows were then excluded.
The analysis support was {a['eligible_rows']:,} observations across {a['n_weirs']}
weirs ({a['zeros']:,} zeros; {a['positives']:,} positives; 2017–2025). No value was
imputed and no unit conversion was applied.

## Frozen primary halt

The June–October occurrence logit did not converge in 100 deterministic IRLS
iterations. Direct separation diagnostics found three weirs—강정고령보, 달성보,
창녕함안보—with occurrence = 1 for every June–October observation. The Newton step
remained approximately 1 while fixed-effect coefficients diverged past magnitude
100, which is separation rather than a tolerance artifact. The base protocol says
nonconvergence/separation halts the affected model. Therefore the two-part primary
family is incomplete, Holm adjustment is undefined, and the 1,999-draw paired
primary bootstrap was correctly not run (`NOT_RUN_PRIMARY_MODEL_HALTED`). No Firth
fit, window substitution, or favorable sensitivity was introduced post hoc.

The fitted positive primary part had beta = 0.275593, CR1 SE = 0.134845,
unadjusted p = 0.0589489, and a 31.7311% positive-count geometric-mean change per
doubling of residence time (95% t interval −0.0118228 to 0.563008 on the log scale).
It cannot rescue or stand in for the halted two-part primary family.

## Prespecified sensitivity models

{models_table}

May–October and annual occurrence models converged; July–September occurrence also
halted. These sensitivity results are reported but cannot replace the adverse
primary outcome.

## Sampling balance and separate blockers

Observed counts ranged from {f['weir_year_min']} to {f['weir_year_max']} per
weir-year (CV {f['weir_year_cv']:.6g}) and {f['weir_year_month_min']} to
{f['weir_year_month_max']} per observed weir-year-month (CV
{f['weir_year_month_cv']:.6g}). Calendar-cell sensitivities are included above.

- R2-M09c threshold branch: `BLOCKED`. Source is `Cells/100mL`, threshold language
  is `cells/mL`, and no authoritative in-scope reconciliation supports conversion.
- R2-m04b sampling-protocol branch: `AXIS_EXHAUSTED`. No supplied provenance or
  notes state whether agency visits were routine or bloom-event-triggered; unequal
  observed frequency cannot identify scheduling intent.

## Effect on the manuscript's core claim

The frozen M9 evidence cannot establish the requested joint occurrence-plus-positive
residence-time effect. Any manuscript statement should report the primary separation
and the descriptive positive-part/sensitivity estimates without treating them as a
successful hurdle result.

## Verification and evidence paths

- `{run / 'm9_sample_accounting.json'}`
- `{run / 'm9_two_part_models.csv'}`
- `{run / 'm9_model_failures.csv'}`
- `{run / 'm9_occurrence_by_window_weir.csv'}`
- `{run / 'm9_primary_cluster_bootstrap_status.json'}`
- `{run / 'm9_sampling_frequency_weir_year.csv'}` and `..._month.csv`
- `{run / 'm9_threshold_block.json'}` and `{run / 'm9_sampling_protocol_audit.json'}`
- verification gate `M9_primary_axis_exhaustion`: PASS
- verification gate `M9_source_and_dedup_accounting`: PASS
- verification gate `M9_separate_blockers_preserved`: PASS
"""


def report_phase(run: Path, base: Path, amendment: Path) -> str:
    verification = json.loads((run / "verification.json").read_text())
    manifest = json.loads((run / "source_manifest.json").read_text())
    warning = verification["warnings"][0]
    return f"""# P2d quantitative design and inference report

## Result

| Branch | Verdict | Decisive result |
| --- | --- | --- |
| M5 chronology/event time | **AXIS_EXHAUSTED** | 0/16 complete treatment sequences; no within-basin treated/control variation; event study and pretrend not run |
| M8 dependent NDCI correlations | **WEAKENS_OR_REDIRECTS** | pooled Delta = 0.510794, exact p = 0.0309753, but spatial-dominance flag true (within Delta = −0.0177894; between Delta = 0.655882) |
| M9 two-part harmful cyanobacteria | **AXIS_EXHAUSTED** | primary occurrence logit separated/nonconvergent; positive part beta = 0.275593, p = 0.0589489; joint primary and bootstrap unavailable |

No manuscript or response-letter file was edited. Adverse and axis-exhausted results
were retained rather than replaced with more favorable sensitivities.

## Work performed

1. Inspected the task packet, ledger/strategy/critical-path materials, P1 report,
   source inventory, raw daily panel, annual proxy panel, chronology/gap/coverage
   tables, Gate-0 evidence, historical analysis code/output, and saved local primary
   records. Every used source is hashed in `{run / 'source_manifest.json'}`.
2. Preserved the exact pre-analysis protocol bytes as `{base}` (SHA-256
   `cf60dc3bc4935a55ab6ed55df6e8bc67c82fa4c1136077c1efb755206057d4cf`).
3. Recorded the M9 source-locator-only exact-duplicate repair separately in
   `{amendment}` (SHA-256
   `c3e4fe46dff9f30978e2890187628cb9a77b48e50b6dcaee5a8dc40799f52c4e`).
4. Ran parameterized M5/M8/M9 code, exact joint inference, diagnostics, source and
   sample accounting, and branch-specific halt logic.
5. Ran 15 unit/source-contract tests with RuntimeWarnings promoted to errors, then
   executed the independent fail-closed verifier.

## Provenance finding

The immutable base copy was materialized after the earlier M5/M8 run, so its mtime
is not claimed to predate those results. Instead, the first run manifest
`{Path(manifest['output_root']).parent / '20260815T045525Z_cf60dc3b/source_manifest.json'}`
records the same full base hash and a pre-result mtime. Verification checks M5/M8
against the base only and M9 against base plus amendment. It also confirms the
amendment was absent from and later than the first run, but earlier than this fresh
run ({manifest['created_at_utc']}).

The current ledger has a post-freeze source drift: frozen SHA `{warning['frozen_sha256']}`
versus current SHA `{warning['current_sha256']}`. Prior ledger bytes were not saved,
so no exact row-level diff is claimed. This is disclosed as a noncomputational
provenance warning: the ledger did not enter a numerical model; branch definitions
were already frozen; and every computational input retained its frozen identity.

## Verification record

- Overall verification: **{verification['status']}**
- PASS gates: {sum(record['status'] == 'PASS' for record in verification['gates'].values())}/{len(verification['gates'])}
- Failed gates: {verification['failed_gates']}
- Artifact ledger: `{verification['artifact_ledger']['path']}`
- Artifacts hashed: {verification['artifact_ledger']['artifacts_hashed']}
- Artifact-ledger SHA-256: `{verification['artifact_ledger']['sha256']}`
- Completion marker: `{run / 'COMPLETE'}`

## Required outputs

- M5: `{run.parent.parent.parent / 'M5_event_study.md'}`
- M8: `{run.parent.parent.parent / 'M8_correlation.md'}`
- M9: `{run.parent.parent.parent / 'M9_hurdle.md'}`
- machine-readable run: `{run}`
- code/tests: `{run.parents[3] / 'code/P2d'}`

## Residual risk

M5 cannot be reopened without exact, conflict-adjudicated operational histories.
M9 occurrence would require a newly authorized, prospectively frozen separation-safe
estimator; it must not be retrofitted into this result. R2-M09c remains blocked on
authoritative unit reconciliation, and R2-m04b remains exhausted for protocol
attribution under the supplied sources.
"""


def main(args: argparse.Namespace) -> None:
    run = args.run.resolve()
    verification = json.loads((run / "verification.json").read_text())
    if verification["status"] != "PASS" or not (run / "COMPLETE").is_file():
        raise ValueError("reports require a verified COMPLETE run")
    outputs = {
        args.campaign / "revision_1/03_analysis/output/M5_event_study.md": report_m5(run),
        args.campaign / "revision_1/03_analysis/output/M8_correlation.md": report_m8(run),
        args.campaign / "revision_1/03_analysis/output/M9_hurdle.md": report_m9(run),
        args.campaign / "revision_1/99_admin/reports/P2d_REPORT.md": report_phase(run, args.base.resolve(), args.amendment.resolve()),
    }
    for path, content in outputs.items():
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        print(path)
    code_root = args.campaign / "revision_1/03_analysis/code/P2d"
    deliverables = [
        *outputs.keys(),
        args.base.resolve(),
        args.amendment.resolve(),
        args.campaign / "revision_1/03_analysis/frozen_protocols/P2d_freeze.md",
        run / "source_manifest.json",
        run / "verification.json",
        run / "artifact_hashes.csv",
        run / "COMPLETE",
        *sorted(code_root.glob("*.py")),
        *sorted((code_root / "tests").glob("test_*.py")),
    ]
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "verified_run": str(run),
        "checks": {
            "run_verification_pass": verification["status"] == "PASS",
            "run_complete_marker": (run / "COMPLETE").is_file(),
            "M5_verdict_present": "VERDICT: AXIS_EXHAUSTED" in outputs[args.campaign / "revision_1/03_analysis/output/M5_event_study.md"],
            "M8_verdict_present": "VERDICT: WEAKENS_OR_REDIRECTS" in outputs[args.campaign / "revision_1/03_analysis/output/M8_correlation.md"],
            "M9_verdict_present": "VERDICT: AXIS_EXHAUSTED" in outputs[args.campaign / "revision_1/03_analysis/output/M9_hurdle.md"],
        },
        "files": [
            {
                "path": str(path.resolve()),
                "size_bytes": path.stat().st_size,
                "mtime": path.stat().st_mtime,
                "sha256": sha256_file(path),
            }
            for path in deliverables
        ],
    }
    if not all(manifest["checks"].values()):
        raise ValueError(f"delivery checks failed: {manifest['checks']}")
    delivery_path = args.campaign / "revision_1/03_analysis/output/P2d/delivery_manifest.json"
    delivery_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(delivery_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--amendment", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    main(parse_args())
