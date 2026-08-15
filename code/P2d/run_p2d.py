#!/usr/bin/env python3
"""Run the frozen P2d M5/M8/M9 branches into a fresh revision-local directory."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd
import scipy

from m5_chronology import chronology_eligibility, legacy_late_post_comparator
from m8_correlation import (
    dependent_correlation_analysis,
    distribution_diagnostics,
    paired_common_support,
    relationship_form_diagnostics,
    within_between_correlations,
)
from m9_hurdle import (
    aggregate_calendar_cells,
    fit_logit_cluster,
    fit_ols_cluster,
    holm_adjust,
    make_fe_design,
    prepare_harmful_panel,
)


SEED = 20260815
M8_BOOTSTRAP = 9999
M9_BOOTSTRAP = 1999
BASE_FREEZE_SHA256 = "cf60dc3bc4935a55ab6ed55df6e8bc67c82fa4c1136077c1efb755206057d4cf"
M9_AMENDMENT_SHA256 = "c3e4fe46dff9f30978e2890187628cb9a77b48e50b6dcaee5a8dc40799f52c4e"
M8_SEASONS = ["annual_all_samples", "bloom_season_06_10"]
M9_WINDOWS = {
    "primary_june_october": [6, 7, 8, 9, 10],
    "sensitivity_may_october": [5, 6, 7, 8, 9, 10],
    "sensitivity_july_september": [7, 8, 9],
    "sensitivity_annual": list(range(1, 13)),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, frame: pd.DataFrame, compression: str | None = None) -> None:
    temporary = path.with_name(path.name + ".tmp")
    frame.to_csv(temporary, index=False, compression=compression)
    os.replace(temporary, path)


def assert_output_jail(output_root: Path) -> Path:
    allowed = Path(
        "/Users/eungyupark/Dropbox/Manuscripts/0_HAB/revision_1/03_analysis/output/P2d"
    ).resolve()
    root = output_root.resolve()
    if root == allowed or allowed not in root.parents:
        raise ValueError(f"output root escapes P2d jail: {root}")
    if root.exists():
        raise FileExistsError(f"fresh output root required: {root}")
    current = root.parent
    while current != allowed.parent:
        if current.exists() and current.is_symlink():
            raise ValueError(f"symlink component forbidden: {current}")
        if current == allowed:
            break
        current = current.parent
    root.mkdir(parents=True)
    return root


def source_record(path: Path) -> dict:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "size_bytes": stat.st_size,
        "mtime": stat.st_mtime,
    }


def build_manifest(args: argparse.Namespace, output_root: Path) -> dict:
    source_paths = [
        args.freeze,
        args.m9_amendment,
        args.raw_cyano,
        args.annual_panel,
        args.events,
        args.coverage,
        args.gaps,
        args.gate_trajectory,
        args.gate_verification,
        args.historical_opening,
        args.historical_proxy,
        args.alert_screen,
        *args.additional_source,
    ]
    missing = [str(path) for path in source_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing frozen source(s): {missing}")
    return {
        "protocol_id": "P2d_v1_with_M9_v1.1_amendment",
        "protocol_branches": {
            "M5": [source_record(args.freeze)],
            "M8": [source_record(args.freeze)],
            "M9": [source_record(args.freeze), source_record(args.m9_amendment)],
        },
        "worker_turn": "T1_codex1_983b5b",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_root": str(output_root),
        "seed": SEED,
        "m8_bootstrap_draws": M8_BOOTSTRAP,
        "m8_sign_patterns_per_season": 65536,
        "m9_bootstrap_draws": M9_BOOTSTRAP,
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
        },
        "sources": [source_record(path) for path in source_paths],
        "status": "RUNNING",
    }


def run_m5(args: argparse.Namespace, root: Path) -> dict:
    events = pd.read_csv(args.events, dtype=str).fillna("")
    coverage = pd.read_csv(args.coverage, dtype=str).fillna("")
    gaps = pd.read_csv(args.gaps, dtype=str).fillna("")
    panel = pd.read_csv(args.annual_panel)
    eligibility = chronology_eligibility(events, coverage, gaps, panel)
    atomic_json(root / "m5_chronology_eligibility.json", eligibility)
    write_csv(root / "m5_chronology_weir_detail.csv", pd.DataFrame(eligibility["weir_detail"]))
    write_csv(root / "m5_basin_counts.csv", pd.DataFrame(eligibility["basin_counts"]))

    comparator = legacy_late_post_comparator(panel)
    historical = pd.read_csv(args.historical_opening)
    merged = comparator.merge(
        historical[["season_scope", "outcome", "did_2018_vs_2017", "did_late_post_vs_2017"]],
        on=["season_scope", "outcome"],
        how="left",
        validate="one_to_one",
        suffixes=("_recomputed", "_historical"),
    )
    merged["immediate_abs_diff"] = (
        merged["did_2018_vs_2017_recomputed"] - merged["did_2018_vs_2017_historical"]
    ).abs()
    merged["late_abs_diff"] = (
        merged["did_late_2019_2025_vs_2017"] - merged["did_late_post_vs_2017"]
    ).abs()
    if len(merged) != 4 or merged[["immediate_abs_diff", "late_abs_diff"]].max().max() > 1e-12:
        raise ValueError("historical late-post comparator reconciliation failed")
    write_csv(root / "m5_legacy_comparator.csv", merged)
    result = {
        "verdict": "AXIS_EXHAUSTED" if not eligibility["eligible"] else "ELIGIBLE_REQUIRES_NEW_PROTOCOL",
        "event_study_run": False,
        "parallel_trend_test_run": False,
        "legacy_comparator_reconciled": True,
        "legacy_comparator_rows": len(merged),
        "chronology": eligibility,
    }
    if eligibility["eligible"]:
        raise ValueError("chronology unexpectedly eligible; P2d_v1 contains no post-gate event estimator")
    atomic_json(root / "m5_result.json", result)
    return result


def run_m8(args: argparse.Namespace, root: Path) -> tuple[dict, pd.DataFrame]:
    panel = pd.read_csv(args.annual_panel)
    x_col = "ndci_mean"
    cyano_col = "log1p_harmful_cyanobacteria_total_mean"
    chla_col = "log1p_chlorophyll_a_mean"
    result_rows = []
    all_patterns = []
    all_bootstrap = []
    all_decomposition = []
    all_distribution = []
    all_relationship = []
    for season_index, season in enumerate(M8_SEASONS):
        frame = panel.loc[panel["season_scope"] == season].copy()
        common = paired_common_support(
            frame,
            ["weir_name", "year", x_col, cyano_col, chla_col],
        )
        if len(common) != 142 or common["weir_name"].nunique() != 16:
            raise ValueError(f"M8 common-support contract failed for {season}: {common.shape}")
        analysis, patterns, bootstrap = dependent_correlation_analysis(
            common,
            x_col=x_col,
            cyano_col=cyano_col,
            chla_col=chla_col,
            cluster_col="weir_name",
            bootstrap_draws=M8_BOOTSTRAP,
            seed=SEED + 100 + season_index,
        )
        analysis["season_scope"] = season
        result_rows.append(analysis)
        patterns.insert(0, "season_scope", season)
        bootstrap.insert(0, "season_scope", season)
        all_patterns.append(patterns)
        all_bootstrap.append(bootstrap)
        decomposition = within_between_correlations(
            common, x_col, cyano_col, chla_col, "weir_name"
        )
        decomposition.insert(0, "season_scope", season)
        all_decomposition.append(decomposition)
        distribution = distribution_diagnostics(common, [x_col, cyano_col, chla_col])
        distribution.insert(0, "season_scope", season)
        all_distribution.append(distribution)
        relationship = relationship_form_diagnostics(common, x_col, [cyano_col, chla_col])
        relationship.insert(0, "season_scope", season)
        all_relationship.append(relationship)

    results = pd.DataFrame(result_rows)
    decomposition = pd.concat(all_decomposition, ignore_index=True)
    annual = results.loc[results["season_scope"] == "annual_all_samples"].iloc[0]
    annual_decomp = decomposition.loc[
        decomposition["season_scope"] == "annual_all_samples"
    ].set_index("component")
    pooled_delta = float(annual_decomp.loc["pooled", "spearman_delta_chla_minus_cyano"])
    within_delta = float(annual_decomp.loc["within_weir", "spearman_delta_chla_minus_cyano"])
    between_delta = float(annual_decomp.loc["between_weir", "spearman_delta_chla_minus_cyano"])
    spatial_dominance = abs(within_delta) < 0.5 * abs(pooled_delta) and abs(between_delta) > abs(within_delta)
    supports = (
        float(annual["spearman_delta_chla_minus_cyano"]) > 0
        and float(annual["exact_p_two_sided"]) < 0.05
        and not spatial_dominance
    )
    verdict = "SUPPORTS" if supports else "WEAKENS_OR_REDIRECTS"
    results["branch_verdict"] = verdict
    write_csv(root / "m8_estimates.csv", results)
    write_csv(root / "m8_decomposition.csv", decomposition)
    write_csv(root / "m8_distribution_diagnostics.csv", pd.concat(all_distribution, ignore_index=True))
    write_csv(root / "m8_relationship_diagnostics.csv", pd.concat(all_relationship, ignore_index=True))
    write_csv(root / "m8_signflip_patterns.csv.gz", pd.concat(all_patterns, ignore_index=True), compression="gzip")
    write_csv(root / "m8_cluster_bootstrap.csv.gz", pd.concat(all_bootstrap, ignore_index=True), compression="gzip")
    summary = {
        "verdict": verdict,
        "spatial_dominance_flag": bool(spatial_dominance),
        "annual_pooled_delta": pooled_delta,
        "annual_within_delta": within_delta,
        "annual_between_delta": between_delta,
        "results": results.to_dict("records"),
    }
    atomic_json(root / "m8_result.json", summary)
    return summary, results


def _model_row(frame: pd.DataFrame, window: str, part: str, balanced: bool) -> dict:
    fe_cols = ["weir_name", "sampling_year", "sampling_month"]
    if not balanced:
        if part == "occurrence":
            model_frame = frame.copy()
            y = model_frame["occurrence"].to_numpy(float)
            x, names = make_fe_design(model_frame, "log2_tau", fe_cols)
            fit = fit_logit_cluster(y, x, model_frame["weir_name"], names)
        else:
            model_frame = frame.dropna(subset=["positive_log"]).copy()
            y = model_frame["positive_log"].to_numpy(float)
            x, names = make_fe_design(model_frame, "log2_tau", fe_cols)
            fit = fit_ols_cluster(y, x, model_frame["weir_name"], names)
    else:
        cells = aggregate_calendar_cells(frame)
        if part == "occurrence":
            model_frame = cells.copy()
            y = model_frame["occurrence_share"].to_numpy(float)
            x, names = make_fe_design(model_frame, "log2_tau", fe_cols)
            fit = fit_logit_cluster(y, x, model_frame["weir_name"], names)
        else:
            model_frame = cells.dropna(subset=["mean_positive_log"]).copy()
            y = model_frame["mean_positive_log"].to_numpy(float)
            x, names = make_fe_design(model_frame, "log2_tau", fe_cols)
            fit = fit_ols_cluster(y, x, model_frame["weir_name"], names)
    beta = fit["coef"]["log2_tau"]
    se = fit["se_cluster"]["log2_tau"]
    return {
        "window": window,
        "part": part,
        "calendar_balanced": balanced,
        "n": fit["n"],
        "n_weirs": fit["n_clusters"],
        "coefficient_log2_tau": beta,
        "cluster_se": se,
        "ci_low": fit["ci_low"]["log2_tau"],
        "ci_high": fit["ci_high"]["log2_tau"],
        "p_two_sided": fit["p_two_sided"]["log2_tau"],
        "effect_ratio_per_tau_doubling": float(np.exp(beta)),
        "effect_percent_per_tau_doubling": float(100 * (np.exp(beta) - 1)),
        "converged": fit["converged"],
        "iterations": fit["iterations"],
    }


def _attempt_model_row(frame: pd.DataFrame, window: str, part: str, balanced: bool) -> dict:
    """Apply the frozen halt rule to one model while preserving other branch evidence."""
    try:
        row = _model_row(frame, window, part, balanced)
        row.update({"model_status": "FIT", "error_type": "", "error_message": ""})
        return row
    except Exception as exc:
        if balanced:
            support = aggregate_calendar_cells(frame)
            outcome = "occurrence_share" if part == "occurrence" else "mean_positive_log"
            support = support.dropna(subset=[outcome])
        else:
            support = frame if part == "occurrence" else frame.dropna(subset=["positive_log"])
        return {
            "window": window,
            "part": part,
            "calendar_balanced": balanced,
            "n": int(len(support)),
            "n_weirs": int(support["weir_name"].astype(str).nunique()),
            "coefficient_log2_tau": np.nan,
            "cluster_se": np.nan,
            "ci_low": np.nan,
            "ci_high": np.nan,
            "p_two_sided": np.nan,
            "effect_ratio_per_tau_doubling": np.nan,
            "effect_percent_per_tau_doubling": np.nan,
            "converged": False,
            "iterations": np.nan,
            "model_status": "HALTED",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }


def _m9_verdict(models: pd.DataFrame) -> tuple[str, str]:
    primary_mask = (models["window"] == "primary_june_october") & (~models["calendar_balanced"])
    primary = models.loc[primary_mask]
    if len(primary) != 2 or set(primary["part"]) != {"occurrence", "positive"}:
        return "AXIS_EXHAUSTED", "Primary two-part model family is incomplete."
    halted = primary.loc[primary["model_status"] != "FIT", "part"].astype(str).tolist()
    if halted:
        return (
            "AXIS_EXHAUSTED",
            "Frozen primary model(s) halted and cannot be replaced post hoc: " + ", ".join(halted),
        )
    supports = bool(
        (primary["coefficient_log2_tau"] > 0).all()
        and (primary["p_holm_primary_family"] < 0.05).all()
    )
    if supports:
        return "SUPPORTS", "Both frozen primary coefficients are positive with Holm p < 0.05."
    return "WEAKENS_OR_REDIRECTS", "At least one fitted frozen primary part fails the joint support rule."


def _primary_bootstrap(primary: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 900)
    clusters = sorted(primary["weir_name"].astype(str).unique().tolist())
    grouped = {cluster: primary.loc[primary["weir_name"].astype(str) == cluster].copy() for cluster in clusters}
    rows = []
    for draw_id in range(M9_BOOTSTRAP):
        selected = rng.choice(clusters, size=len(clusters), replace=True)
        draw = pd.concat([grouped[str(cluster)] for cluster in selected], ignore_index=True)
        try:
            occurrence = _model_row(draw, "primary_june_october", "occurrence", False)
            positive = _model_row(draw, "primary_june_october", "positive", False)
            finite = bool(np.isfinite([occurrence["coefficient_log2_tau"], positive["coefficient_log2_tau"]]).all())
            error = ""
        except Exception as exc:
            occurrence = {"coefficient_log2_tau": np.nan}
            positive = {"coefficient_log2_tau": np.nan}
            finite = False
            error = f"{type(exc).__name__}:{exc}"
        rows.append(
            {
                "draw_id": draw_id,
                "selected_cluster_hash": hashlib.sha256("|".join(map(str, selected)).encode()).hexdigest(),
                "beta_occurrence_star": occurrence["coefficient_log2_tau"],
                "beta_positive_star": positive["coefficient_log2_tau"],
                "finite": finite,
                "error": error,
            }
        )
    result = pd.DataFrame(rows)
    if len(result) != M9_BOOTSTRAP or not result["finite"].all():
        failures = result.loc[~result["finite"], "error"].value_counts().to_dict()
        raise ValueError(f"M9 nonfinite paired cluster bootstrap draw(s): {failures}")
    return result


def run_m9(args: argparse.Namespace, root: Path) -> tuple[dict, pd.DataFrame]:
    raw = pd.read_csv(args.raw_cyano)
    annual_panel = pd.read_csv(args.annual_panel)
    tau = annual_panel.loc[
        annual_panel["season_scope"] == "annual_all_samples", ["weir_name", "year", "tau_days"]
    ].copy()
    raw_harmful = raw.loc[
        (raw["variable"].astype(str) == "harmful_cyanobacteria_total")
        & (raw["source_field"].astype(str) == "iemBgalageCellCo")
    ].copy()
    pre_audit = {
        "raw_total_rows": int(len(raw)),
        "harmful_total_rows": int(len(raw_harmful)),
        "missing_value": int(pd.to_numeric(raw_harmful["value"], errors="coerce").isna().sum()),
        "source_units": sorted(raw_harmful["unit"].dropna().astype(str).unique().tolist()),
        "duplicate_measurement_keys": int(raw_harmful.duplicated(["station_code", "sampling_date", "variable"]).sum()),
    }
    frame = prepare_harmful_panel(raw, tau)
    pre_audit.update(
        {
            "eligible_rows": int(len(frame)),
            "exact_duplicate_rows_collapsed": int(
                len(raw_harmful)
                - len(raw_harmful.drop_duplicates(["station_code", "sampling_date", "variable"]))
            ),
            "excluded_after_exact_dedup_for_missing_or_join": int(
                len(raw_harmful.drop_duplicates(["station_code", "sampling_date", "variable"]))
                - len(frame)
            ),
            "zeros": int((frame["value"] == 0).sum()),
            "positives": int((frame["value"] > 0).sum()),
            "n_weirs": int(frame["weir_name"].nunique()),
            "year_min": int(frame["sampling_year"].min()),
            "year_max": int(frame["sampling_year"].max()),
        }
    )
    atomic_json(root / "m9_sample_accounting.json", pre_audit)

    frequency_year = frame.groupby(["weir_name", "sampling_year"], as_index=False).agg(
        n_observations=("value", "size"),
        n_zeros=("occurrence", lambda s: int((s == 0).sum())),
        n_positive=("occurrence", "sum"),
    )
    frequency_month = frame.groupby(["weir_name", "sampling_year", "sampling_month"], as_index=False).agg(
        n_observations=("value", "size"),
        n_zeros=("occurrence", lambda s: int((s == 0).sum())),
        n_positive=("occurrence", "sum"),
    )
    write_csv(root / "m9_sampling_frequency_weir_year.csv", frequency_year)
    write_csv(root / "m9_sampling_frequency_weir_year_month.csv", frequency_month)
    frequency_summary = {
        "weir_year_min": int(frequency_year["n_observations"].min()),
        "weir_year_max": int(frequency_year["n_observations"].max()),
        "weir_year_cv": float(frequency_year["n_observations"].std(ddof=1) / frequency_year["n_observations"].mean()),
        "weir_year_month_min": int(frequency_month["n_observations"].min()),
        "weir_year_month_max": int(frequency_month["n_observations"].max()),
        "weir_year_month_cv": float(frequency_month["n_observations"].std(ddof=1) / frequency_month["n_observations"].mean()),
    }
    atomic_json(root / "m9_sampling_frequency_summary.json", frequency_summary)

    model_rows = []
    window_accounting = []
    occurrence_by_weir = []
    for window, months in M9_WINDOWS.items():
        subset = frame.loc[frame["sampling_month"].astype(int).isin(months)].copy()
        window_accounting.append(
            {
                "window": window,
                "months": ";".join(map(str, months)),
                "n": len(subset),
                "zeros": int((subset["occurrence"] == 0).sum()),
                "positives": int((subset["occurrence"] == 1).sum()),
                "n_weirs": int(subset["weir_name"].nunique()),
                "n_weir_year_month_cells": int(subset[["weir_name", "sampling_year", "sampling_month"]].drop_duplicates().shape[0]),
            }
        )
        grouped_occurrence = subset.groupby("weir_name", as_index=False)["occurrence"].agg(
            n="size", minimum="min", maximum="max", proportion="mean"
        )
        grouped_occurrence.insert(0, "window", window)
        grouped_occurrence["degenerate"] = grouped_occurrence["minimum"].eq(
            grouped_occurrence["maximum"]
        )
        occurrence_by_weir.append(grouped_occurrence)
        for balanced in [False, True]:
            for part in ["occurrence", "positive"]:
                model_rows.append(_attempt_model_row(subset, window, part, balanced))
    models = pd.DataFrame(model_rows)
    primary_mask = (models["window"] == "primary_june_october") & (~models["calendar_balanced"])
    primary_indices = models.index[primary_mask].tolist()
    if len(primary_indices) != 2:
        raise ValueError("M9 primary family does not contain exactly two parts")
    models["p_holm_primary_family"] = np.nan
    primary_fitted = bool(models.loc[primary_indices, "model_status"].eq("FIT").all())
    if primary_fitted:
        models.loc[primary_indices, "p_holm_primary_family"] = holm_adjust(
            models.loc[primary_indices, "p_two_sided"].to_numpy(float)
        )
    primary = frame.loc[frame["sampling_month"].astype(int).isin(M9_WINDOWS["primary_june_october"])].copy()
    if primary_fitted:
        bootstrap = _primary_bootstrap(primary)
        for part, column in [("occurrence", "beta_occurrence_star"), ("positive", "beta_positive_star")]:
            low, high = np.quantile(bootstrap[column].to_numpy(float), [0.025, 0.975])
            index = models.index[
                (models["window"] == "primary_june_october")
                & (~models["calendar_balanced"])
                & (models["part"] == part)
            ][0]
            models.loc[index, "cluster_bootstrap_ci_low"] = low
            models.loc[index, "cluster_bootstrap_ci_high"] = high
            models.loc[index, "cluster_bootstrap_draws"] = M9_BOOTSTRAP
        bootstrap_status = {
            "status": "COMPLETE",
            "requested_draws": M9_BOOTSTRAP,
            "saved_draws": int(len(bootstrap)),
        }
        write_csv(root / "m9_primary_cluster_bootstrap.csv.gz", bootstrap, compression="gzip")
    else:
        bootstrap_status = {
            "status": "NOT_RUN_PRIMARY_MODEL_HALTED",
            "requested_draws": M9_BOOTSTRAP,
            "saved_draws": 0,
            "reason": "A paired bootstrap cannot be formed because the frozen primary occurrence model halted.",
        }
    write_csv(root / "m9_window_accounting.csv", pd.DataFrame(window_accounting))
    write_csv(root / "m9_occurrence_by_window_weir.csv", pd.concat(occurrence_by_weir, ignore_index=True))
    write_csv(root / "m9_two_part_models.csv", models)
    write_csv(root / "m9_model_failures.csv", models.loc[models["model_status"] != "FIT"].copy())
    atomic_json(root / "m9_primary_cluster_bootstrap_status.json", bootstrap_status)

    primary_models = models.loc[primary_mask].set_index("part")
    verdict, verdict_reason = _m9_verdict(models)
    threshold_block = {
        "status": "BLOCKED",
        "ledger_id": "R2-M09c",
        "source_unit": "Cells/100mL",
        "threshold_language_unit": "cells/mL",
        "conversion_applied": False,
        "reason": "No authoritative in-scope unit reconciliation; exceedance was not analyzed.",
        "evidence_path": str(args.alert_screen.resolve()),
        "evidence_sha256": sha256_file(args.alert_screen),
    }
    atomic_json(root / "m9_threshold_block.json", threshold_block)
    protocol_audit = {
        "status": "AXIS_EXHAUSTED",
        "ledger_id": "R2-m04b",
        "event_triggered_sampling_determined": False,
        "reason": "Timestamps and panel notes describe observations/provenance but do not state whether agency sampling was routine or bloom-event-triggered.",
        "notes_nonempty_rows": int(raw_harmful["notes"].fillna("").astype(str).str.strip().ne("").sum()),
        "inference_forbidden": "Unequal observed frequency cannot identify the agency scheduling protocol.",
    }
    atomic_json(root / "m9_sampling_protocol_audit.json", protocol_audit)
    summary = {
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "primary_models": primary_models.reset_index().to_dict("records"),
        "primary_bootstrap": bootstrap_status,
        "sample_accounting": pre_audit,
        "sampling_frequency": frequency_summary,
        "threshold_branch": threshold_block,
        "sampling_protocol_branch": protocol_audit,
    }
    atomic_json(root / "m9_result.json", summary)
    return summary, models


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--m9-amendment", type=Path, required=True)
    parser.add_argument("--raw-cyano", type=Path, required=True)
    parser.add_argument("--annual-panel", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--gaps", type=Path, required=True)
    parser.add_argument("--gate-trajectory", type=Path, required=True)
    parser.add_argument("--gate-verification", type=Path, required=True)
    parser.add_argument("--historical-opening", type=Path, required=True)
    parser.add_argument("--historical-proxy", type=Path, required=True)
    parser.add_argument("--alert-screen", type=Path, required=True)
    parser.add_argument("--additional-source", type=Path, action="append", default=[])
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    root = assert_output_jail(args.output_root)
    if sha256_file(args.freeze) != BASE_FREEZE_SHA256:
        raise ValueError("base freeze content hash mismatch")
    if sha256_file(args.m9_amendment) != M9_AMENDMENT_SHA256:
        raise ValueError("M9 amendment content hash mismatch")
    if args.freeze.resolve() == args.m9_amendment.resolve():
        raise ValueError("base freeze and M9 amendment must be separate files")
    for protocol_path in [args.freeze, args.m9_amendment]:
        if protocol_path.stat().st_mtime >= root.stat().st_mtime:
            raise ValueError(f"protocol must predate fresh output root: {protocol_path}")
    manifest = build_manifest(args, root)
    atomic_json(root / "source_manifest.json", manifest)
    m5 = run_m5(args, root)
    m8, _ = run_m8(args, root)
    m9, _ = run_m9(args, root)
    manifest["status"] = "ANALYSIS_COMPLETE_AWAITING_VERIFICATION"
    manifest["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["branch_verdicts"] = {
        "M5": m5["verdict"],
        "M8": m8["verdict"],
        "M9": m9["verdict"],
    }
    atomic_json(root / "source_manifest.json", manifest)
    print(root)


if __name__ == "__main__":
    main(parse_args())
