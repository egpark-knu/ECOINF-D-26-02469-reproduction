#!/usr/bin/env python3
"""Execute the frozen P2a M1 plan in a fresh revision-local run directory."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import traceback

import matplotlib
import numpy as np
import pandas as pd
import scipy

from endpoint_design import endpoint_specific_design, prepare_shared_support, separate_design
from joint_inference import (
    analytic_contrast,
    fit_ols_cluster,
    holm_adjust,
    paired_cluster_bootstrap,
    restricted_wcr_bootstrap_t,
)
from legacy_adapter import assert_legacy_regression, run_legacy
from panel_contract import sha256_file, validate_new_root, validate_panel


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PARENT = Path(os.environ.get(
    "P2A_OUTPUT_PARENT", str(REPOSITORY_ROOT / "reproduction_output/P2a_M1/runs")
))
LOG_PARENT = Path(os.environ.get(
    "P2A_LOG_PARENT", str(REPOSITORY_ROOT / "reproduction_output/P2a_M1/logs")
))
SEASONS = ["annual_all_samples", "bloom_season_06_10"]
SEASON_ROLES = {
    "annual_all_samples": "primary_confirmatory",
    "bloom_season_06_10": "secondary_prespecified",
}
HISTORICAL_PATHS = [
    REPOSITORY_ROOT / "code/P2a_M1/vendor/hardening_specificity_analysis__c895385a.py",
    REPOSITORY_ROOT / "data/insitu_annual_analysis_panel.csv",
    REPOSITORY_ROOT / "data/P2a_M1/runs/20260815T042826Z_c2ac8933/legacy/standardized_tau_models.csv",
    REPOSITORY_ROOT / "data/P2a_M1/runs/20260815T042826Z_c2ac8933/legacy/specificity_interaction.csv",
]
EXPECTED_CODE_SHA256 = "29f46b586460bf478e1c512683cdb07ce6e6b6f5b53a85857e2ba2967a1a833f"
EXPECTED_PANEL_SHA256 = "c7c709986648dde52930da3feedba7deb27a5e347490ea31d87272936f1d68ff"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, frame: pd.DataFrame, gzip: bool = False) -> None:
    temporary = path.with_name(path.name + ".tmp")
    if gzip:
        frame.to_csv(temporary, index=False, compression={"method": "gzip", "mtime": 0})
    else:
        frame.to_csv(temporary, index=False)
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def assert_no_symlink_path(path: Path) -> None:
    absolute = Path(os.path.abspath(os.fspath(path)))
    chain = [absolute, *absolute.parents]
    for item in chain:
        if item.exists() and item.is_symlink():
            raise ValueError(f"symlink path component forbidden: {item}")


def hash_snapshot() -> str:
    return "".join(f"{sha256_file(path)}  {path}\n" for path in HISTORICAL_PATHS)


def runtime_snapshot() -> dict:
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "matplotlib": matplotlib.__version__,
        "statsmodels": "unavailable",
    }


def legacy_rows(
    models: pd.DataFrame,
    interaction: pd.DataFrame,
    protocol_id: str,
    run_id: str,
    run_root: Path,
) -> list[dict]:
    rows: list[dict] = []
    primary = models[models["model_family"] == "z_standardized_log1p_outcome"]
    for season in SEASONS:
        for outcome, model_id in [
            ("cyano", "legacy_separate_cyano"),
            ("chlorophyll_a", "legacy_separate_chlorophyll"),
        ]:
            source = primary[(primary["season_scope"] == season) & (primary["outcome"] == outcome)].iloc[0]
            rows.append({
                "protocol_id": protocol_id,
                "run_id": run_id,
                "season_scope": season,
                "season_role": SEASON_ROLES[season],
                "model_id": model_id,
                "estimand_id": f"beta_{outcome}_legacy_separate_twfe",
                "estimate": float(source["beta_log1p_tau"]),
                "se_method": "legacy_CR1_weir",
                "se": float(source["cluster_se"]),
                "ci_method": "legacy_weir_wild_bootstrap",
                "ci_low": float(source["secondary_ci_low"]),
                "ci_high": float(source["secondary_ci_high"]),
                "test_null": "beta=0",
                "test_sidedness": "one_sided_right_historical",
                "p_raw": float(source["ri_p_right_positive_tau"]),
                "p_holm": np.nan,
                "inference_role": "historical_reproduction",
                "n_original": int(source["n"]),
                "n_stacked": np.nan,
                "n_weirs": int(source["n_weirs"]),
                "n_years": int(source["n_years"]),
                "fixed_effects": "endpoint-specific separate weir + year",
                "cluster": "weir_name",
                "resampling_method": "historical_tau_permutation_within_year",
                "n_resamples": int(source["n_permutations"]),
                "source_artifact": str(run_root / "legacy/standardized_tau_models.csv"),
                "status": "reproduced",
            })
        source = interaction[interaction["season_scope"] == season].iloc[0]
        rows.append({
            "protocol_id": protocol_id,
            "run_id": run_id,
            "season_scope": season,
            "season_role": SEASON_ROLES[season],
            "model_id": "legacy_common_fe_stacked",
            "estimand_id": "delta_common_interaction",
            "estimate": float(source["interaction_beta_cyano_minus_chla"]),
            "se_method": "legacy_CR1_weir",
            "se": float(source["cluster_se"]),
            "ci_method": "legacy_CR1_t15",
            "ci_low": float(source["cluster_ci_low"]),
            "ci_high": float(source["cluster_ci_high"]),
            "test_null": "delta_common=0",
            "test_sidedness": "one_sided_right_historical_RI",
            "p_raw": float(source["ri_p_right_cyano_gt_chla"]),
            "p_holm": np.nan,
            "inference_role": "historical_reproduction_changed_estimand",
            "n_original": int(source["n_original_weir_years"]),
            "n_stacked": int(source["n_stacked"]),
            "n_weirs": int(source["n_weirs"]),
            "n_years": int(source["n_years"]),
            "fixed_effects": "common weir + year across endpoints",
            "cluster": "weir_name",
            "resampling_method": "historical_tau_permutation_within_year",
            "n_resamples": int(source["n_permutations"]),
            "source_artifact": str(run_root / "legacy/specificity_interaction.csv"),
            "status": "reproduced",
        })
    return rows


def execute(args: argparse.Namespace) -> None:
    start_dt = datetime.now(timezone.utc)
    run_root = validate_new_root(args.output_root, OUTPUT_PARENT)
    log_root = validate_new_root(args.log_root, LOG_PARENT)
    for path in [args.protocol, args.freeze, args.legacy_module, args.panel]:
        assert_no_symlink_path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
    if args.freeze.stat().st_mtime >= start_dt.timestamp() or args.protocol.stat().st_mtime >= start_dt.timestamp():
        raise ValueError("freeze/protocol does not predate run start")

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("candidate_explanations") != ["E1", "E2", "E3", "E4", "E5", "E6"]:
        raise ValueError("protocol lacks exact E1-E6 candidates")
    if protocol["seed"] != args.seed or protocol["legacy_n_perm"] != args.legacy_n_perm:
        raise ValueError("seed or legacy permutation count differs from protocol")
    if protocol["n_cluster_sign_patterns"] != args.wcr_sign_patterns:
        raise ValueError("WCR pattern count differs from protocol")
    if protocol["n_cluster_bootstrap"] != args.cluster_bootstrap:
        raise ValueError("cluster bootstrap count differs from protocol")
    if sha256_file(args.legacy_module) != EXPECTED_CODE_SHA256:
        raise ValueError("vendor code hash mismatch")
    if sha256_file(args.panel) != EXPECTED_PANEL_SHA256:
        raise ValueError("frozen panel hash mismatch")

    run_root.mkdir()
    log_root.mkdir()
    stdout_path = log_root / "stdout.log"
    stderr_path = log_root / "stderr.log"
    before_path = log_root / "legacy_hashes_before.sha256"
    after_path = log_root / "legacy_hashes_after.sha256"
    atomic_text(before_path, hash_snapshot())
    manifest = {
        "protocol_id": protocol["protocol_id"],
        "run_id": run_root.name,
        "status": "RUNNING",
        "started_at_utc": start_dt.isoformat(),
        "execution_origin": "public_reproduction",
        "command_arguments": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
        "paths": {"run_root": str(run_root), "log_root": str(log_root)},
        "hashes": {
            "protocol_sha256": sha256_file(args.protocol),
            "freeze_sha256": sha256_file(args.freeze),
            "vendor_sha256": sha256_file(args.legacy_module),
            "panel_sha256": sha256_file(args.panel),
        },
        "freeze_mtime": args.freeze.stat().st_mtime,
        "protocol_mtime": args.protocol.stat().st_mtime,
    }

    try:
        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
            with redirect_stdout(stdout_handle), redirect_stderr(stderr_handle):
                print(f"P2a run started: {run_root.name}")
                environment = runtime_snapshot()
                atomic_json(run_root / "environment.json", environment)
                panel, input_audit = validate_panel(args.panel)
                atomic_json(run_root / "input_audit.json", input_audit)
                print("Input contract: PASS")

                models, interaction = run_legacy(
                    args.legacy_module,
                    args.panel,
                    run_root / "legacy",
                    args.seed,
                    args.legacy_n_perm,
                )
                legacy_audit = assert_legacy_regression(models, interaction)
                atomic_json(run_root / "legacy_regression_audit.json", legacy_audit)
                print("Legacy reproduction gate: PASS")

                design_audit = {"seasons": {}}
                contrasts: list[dict] = []
                wcr_frames = []
                bootstrap_frames = []
                fits_by_season: dict[str, dict] = {}

                for season in SEASONS:
                    print(f"Endpoint-specific analysis: {season}")
                    base = prepare_shared_support(panel, season)
                    separate_fits = {}
                    separate_meta = {}
                    for endpoint in ["cyano", "chlorophyll_a"]:
                        x_sep, y_sep, clusters_sep, names_sep, meta_sep = separate_design(base, endpoint)
                        separate_fits[endpoint] = fit_ols_cluster(x_sep, y_sep, clusters_sep, names_sep)
                        separate_meta[endpoint] = meta_sep

                    x, y, clusters, names, stacked_meta = endpoint_specific_design(base)
                    stacked_fit = fit_ols_cluster(x, y, clusters, names)
                    analytic = analytic_contrast(stacked_fit, "log1p_tau_x_cyano")
                    beta_cyano = separate_fits["cyano"].coef_by_name["log1p_tau"]
                    beta_chla = separate_fits["chlorophyll_a"].coef_by_name["log1p_tau"]
                    arithmetic_difference = beta_cyano - beta_chla
                    delta = stacked_fit.coef_by_name["log1p_tau_x_cyano"]
                    equality_residual = delta - arithmetic_difference
                    if not np.isclose(delta, arithmetic_difference, atol=1e-10, rtol=1e-10):
                        raise AssertionError(f"endpoint algebra mismatch for {season}: {equality_residual}")

                    wcr, wcr_summary = restricted_wcr_bootstrap_t(
                        x,
                        y,
                        clusters,
                        names,
                        "log1p_tau_x_cyano",
                        args.wcr_sign_patterns,
                    )
                    wcr.insert(0, "season_scope", season)
                    wcr_frames.append(wcr)

                    bootstrap = paired_cluster_bootstrap(base, args.cluster_bootstrap, args.seed)
                    bootstrap.insert(0, "season_scope", season)
                    if len(bootstrap) != args.cluster_bootstrap or not bootstrap["finite"].all():
                        raise ValueError(f"paired bootstrap failed for {season}")
                    bootstrap_frames.append(bootstrap)
                    interval_low, interval_high = np.quantile(bootstrap["difference_star"], [0.025, 0.975])

                    independent_se = float(np.sqrt(
                        separate_fits["cyano"].se_by_name["log1p_tau"] ** 2
                        + separate_fits["chlorophyll_a"].se_by_name["log1p_tau"] ** 2
                    ))
                    contrast = {
                        "protocol_id": protocol["protocol_id"],
                        "run_id": run_root.name,
                        "season_scope": season,
                        "season_role": SEASON_ROLES[season],
                        "beta_cyano": beta_cyano,
                        "beta_chlorophyll": beta_chla,
                        "arithmetic_difference": arithmetic_difference,
                        "delta_endpoint_specific_stacked": delta,
                        "equality_residual": equality_residual,
                        "cr1_se_unified": analytic["se"],
                        "cr1_t": analytic["t"],
                        "cr1_df": analytic["df"],
                        "cr1_ci_low": analytic["ci_low"],
                        "cr1_ci_high": analytic["ci_high"],
                        "cr1_p_two_sided": analytic["p_two_sided"],
                        "forbidden_independent_se_diagnostic": independent_se,
                        "wcr_p_two_sided": wcr_summary["p_wcr_two_sided"],
                        "wcr_patterns": wcr_summary["n_patterns"],
                        "paired_bootstrap_ci_low": float(interval_low),
                        "paired_bootstrap_ci_high": float(interval_high),
                        "paired_bootstrap_draws": int(len(bootstrap)),
                        "n_original": int(len(base)),
                        "n_stacked": int(len(y)),
                        "n_weirs": int(base["weir_name"].nunique()),
                        "n_years": int(base["year"].nunique()),
                    }
                    contrasts.append(contrast)
                    design_audit["seasons"][season] = {
                        "separate": separate_meta,
                        "endpoint_specific_stacked": stacked_meta,
                        "equality_residual": equality_residual,
                        "unified_cr1_se": analytic["se"],
                        "forbidden_independent_se_diagnostic": independent_se,
                        "zscore_metadata": input_audit["zscore_metadata"][season],
                    }
                    fits_by_season[season] = {"separate": separate_fits, "stacked": stacked_fit}

                holm = holm_adjust([row["wcr_p_two_sided"] for row in contrasts])
                for row, adjusted in zip(contrasts, holm):
                    row["wcr_p_holm"] = adjusted
                    if row["delta_endpoint_specific_stacked"] <= 0:
                        row["inference_status"] = "direction_change_or_reversal"
                    elif adjusted <= protocol["alpha"]:
                        row["inference_status"] = "positive_and_holm_supported"
                    else:
                        row["inference_status"] = "positive_but_not_holm_supported"

                contrast_frame = pd.DataFrame(contrasts)
                atomic_csv(run_root / "endpoint_specific_contrasts.csv", contrast_frame)
                atomic_json(run_root / "design_audit.json", design_audit)
                atomic_csv(run_root / "wcr_signflip_t.csv.gz", pd.concat(wcr_frames, ignore_index=True), gzip=True)
                atomic_csv(run_root / "cluster_pairs_bootstrap.csv.gz", pd.concat(bootstrap_frames, ignore_index=True), gzip=True)

                matrix_rows = legacy_rows(models, interaction, protocol["protocol_id"], run_root.name, run_root)
                for contrast in contrasts:
                    status = contrast["inference_status"]
                    common = {
                        "protocol_id": protocol["protocol_id"],
                        "run_id": run_root.name,
                        "season_scope": contrast["season_scope"],
                        "season_role": contrast["season_role"],
                        "estimand_id": "delta_endpoint_specific_beta_cyano_minus_chlorophyll",
                        "estimate": contrast["delta_endpoint_specific_stacked"],
                        "se_method": "unified_CR1_weir_diagnostic",
                        "se": contrast["cr1_se_unified"],
                        "ci_method": "paired_weir_cluster_bootstrap_percentile",
                        "ci_low": contrast["paired_bootstrap_ci_low"],
                        "ci_high": contrast["paired_bootstrap_ci_high"],
                        "test_null": "delta_ES=0",
                        "test_sidedness": "two_sided",
                        "p_raw": contrast["wcr_p_two_sided"],
                        "p_holm": contrast["wcr_p_holm"],
                        "n_original": contrast["n_original"],
                        "n_stacked": contrast["n_stacked"],
                        "n_weirs": contrast["n_weirs"],
                        "n_years": contrast["n_years"],
                        "fixed_effects": "endpoint-specific weir + endpoint-specific year",
                        "cluster": "weir_name",
                        "resampling_method": "exhaustive_restricted_WCR_Rademacher",
                        "n_resamples": args.wcr_sign_patterns,
                        "source_artifact": str(run_root / "endpoint_specific_contrasts.csv"),
                        "status": status,
                    }
                    matrix_rows.append({
                        **common,
                        "model_id": "primary_endpoint_specific_fe_stacked",
                        "inference_role": "primary_direct_comparison",
                    })
                    matrix_rows.append({
                        **common,
                        "model_id": "paired_separate_joint_contrast",
                        "inference_role": "paired_separate_point_estimates_with_unified_joint_test",
                    })
                specification_matrix = pd.DataFrame(matrix_rows)
                ordered_columns = [
                    "protocol_id", "run_id", "season_scope", "season_role", "model_id", "estimand_id",
                    "estimate", "se_method", "se", "ci_method", "ci_low", "ci_high", "test_null",
                    "test_sidedness", "p_raw", "p_holm", "inference_role", "n_original", "n_stacked",
                    "n_weirs", "n_years", "fixed_effects", "cluster", "resampling_method", "n_resamples",
                    "source_artifact", "status",
                ]
                specification_matrix = specification_matrix[ordered_columns]
                atomic_csv(run_root / "specification_matrix.csv", specification_matrix)
                print("New endpoint-specific analysis: COMPLETE")

        atomic_text(after_path, hash_snapshot())
        if before_path.read_text(encoding="utf-8") != after_path.read_text(encoding="utf-8"):
            raise RuntimeError("historical hashes changed during execution")
        manifest.update({
            "status": "ANALYSIS_COMPLETE_AWAITING_VERIFICATION",
            "finished_at_utc": utc_now(),
            "environment": runtime_snapshot(),
            "legacy_regression": "PASS",
            "new_analysis_seasons": SEASONS,
        })
        atomic_json(run_root / "run_manifest.json", manifest)
    except Exception as exc:
        atomic_text(after_path, hash_snapshot())
        manifest.update({
            "status": "FAILED",
            "failed_at_utc": utc_now(),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        atomic_json(run_root / "run_manifest.json", manifest)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--legacy-module", type=Path, required=True)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--log-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--legacy-n-perm", type=int, required=True)
    parser.add_argument("--wcr-sign-patterns", type=int, required=True)
    parser.add_argument("--cluster-bootstrap", type=int, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    execute(parse_args())
