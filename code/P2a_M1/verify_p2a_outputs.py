#!/usr/bin/env python3
"""Independent saved-artifact verifier for P2a; never refits a model."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


SEASONS = ["annual_all_samples", "bloom_season_06_10"]
REQUIRED_MODELS = {
    "legacy_separate_cyano",
    "legacy_separate_chlorophyll",
    "legacy_common_fe_stacked",
    "primary_endpoint_specific_fe_stacked",
    "paired_separate_joint_contrast",
}
LEGACY_SLOPES = {
    ("annual_all_samples", "cyano"): 0.6874057079174496,
    ("annual_all_samples", "chlorophyll_a"): 0.14757774021651276,
    ("bloom_season_06_10", "cyano"): 0.6186412520414742,
    ("bloom_season_06_10", "chlorophyll_a"): 0.3216193241323556,
}
LEGACY_INTERACTIONS = {
    "annual_all_samples": (0.887440253669714, 0.1792907058011252),
    "bloom_season_06_10": (1.0350637385933135, 0.15187298089532514),
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


def check(gates: list[dict], gate_id: str, condition: bool, observed: object, expected: object, evidence: str) -> None:
    gates.append({
        "gate_id": gate_id,
        "status": "PASS" if condition else "FAIL",
        "observed": observed,
        "expected": expected,
        "evidence": evidence,
    })


def verify(args: argparse.Namespace) -> None:
    run_root = args.run_root.resolve()
    log_root = args.log_root.resolve()
    gates: list[dict] = []
    required_files = [
        "run_manifest.json",
        "environment.json",
        "input_audit.json",
        "design_audit.json",
        "legacy_regression_audit.json",
        "legacy_cluster_se_defect_audit.json",
        "legacy/standardized_tau_models.csv",
        "legacy/specificity_interaction.csv",
        "specification_matrix.csv",
        "endpoint_specific_contrasts.csv",
        "cluster_pairs_bootstrap.csv.gz",
        "wcr_signflip_t.csv.gz",
    ]
    missing = [name for name in required_files if not (run_root / name).is_file()]
    check(gates, "V01_REQUIRED_FILES", not missing, missing, [], str(run_root))
    if missing:
        result = {"status": "FAIL", "gates": gates}
        atomic_json(run_root / "verification.json", result)
        raise SystemExit(1)

    manifest = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))
    check(
        gates,
        "V02_MANIFEST_STATUS",
        manifest.get("status") == "ANALYSIS_COMPLETE_AWAITING_VERIFICATION",
        manifest.get("status"),
        "ANALYSIS_COMPLETE_AWAITING_VERIFICATION",
        str(run_root / "run_manifest.json"),
    )
    check(gates, "V03_CODE_HASH", manifest["hashes"]["vendor_sha256"] == args.expected_code_sha256, manifest["hashes"]["vendor_sha256"], args.expected_code_sha256, str(run_root / "run_manifest.json"))
    check(gates, "V04_PANEL_HASH", manifest["hashes"]["panel_sha256"] == args.expected_panel_sha256, manifest["hashes"]["panel_sha256"], args.expected_panel_sha256, str(run_root / "run_manifest.json"))

    freeze = Path(manifest["command_arguments"]["freeze"])
    protocol = Path(manifest["command_arguments"]["protocol"])
    manifest_mtime = (run_root / "run_manifest.json").stat().st_mtime
    freeze_ok = freeze.is_file() and protocol.is_file() and freeze.stat().st_mtime < manifest_mtime and protocol.stat().st_mtime < manifest_mtime
    check(gates, "V05_FREEZE_ORDER", freeze_ok, {"freeze_mtime": freeze.stat().st_mtime if freeze.exists() else None, "protocol_mtime": protocol.stat().st_mtime if protocol.exists() else None, "manifest_mtime": manifest_mtime}, "freeze and protocol before manifest", str(run_root / "run_manifest.json"))

    before = (log_root / "legacy_hashes_before.sha256").read_text(encoding="utf-8")
    after = (log_root / "legacy_hashes_after.sha256").read_text(encoding="utf-8")
    check(gates, "V06_HISTORICAL_UNCHANGED", before == after, after, before, str(log_root))

    symlinks = [str(path) for root in [run_root, log_root] for path in root.rglob("*") if path.is_symlink()]
    check(gates, "V07_NO_SYMLINKS", not symlinks, symlinks, [], f"{run_root};{log_root}")

    input_audit = json.loads((run_root / "input_audit.json").read_text(encoding="utf-8"))
    input_ok = (
        input_audit["shape"] == [288, 32]
        and input_audit["season_counts"] == {"annual_all_samples": 144, "bloom_season_06_10": 144}
        and input_audit["shared_support_counts"] == {"annual_all_samples": 144, "bloom_season_06_10": 144}
        and input_audit["duplicate_keys"] == 0
        and input_audit["n_weirs"] == 16
        and input_audit["n_years"] == 9
        and input_audit["tau_nonpositive"] == 0
    )
    check(gates, "V08_INPUT_CONTRACT", input_ok, input_audit, "canonical 288x32 shared-support contract", str(run_root / "input_audit.json"))

    models = pd.read_csv(run_root / "legacy/standardized_tau_models.csv")
    interactions = pd.read_csv(run_root / "legacy/specificity_interaction.csv")
    legacy_ok = len(models) == 10 and len(interactions) == 2
    primary = models[models["model_family"] == "z_standardized_log1p_outcome"]
    legacy_observed = {}
    for key, expected in LEGACY_SLOPES.items():
        row = primary[(primary["season_scope"] == key[0]) & (primary["outcome"] == key[1])]
        observed = float(row.iloc[0]["beta_log1p_tau"]) if len(row) == 1 else np.nan
        legacy_observed[f"{key[0]}:{key[1]}"] = observed
        legacy_ok = legacy_ok and bool(np.isclose(observed, expected, atol=1e-12, rtol=1e-10))
    for season, expected_pair in LEGACY_INTERACTIONS.items():
        row = interactions[interactions["season_scope"] == season]
        observed = float(row.iloc[0]["interaction_beta_cyano_minus_chla"]) if len(row) == 1 else np.nan
        observed_se = float(row.iloc[0]["cluster_se"]) if len(row) == 1 else np.nan
        legacy_observed[f"{season}:interaction"] = observed
        legacy_observed[f"{season}:interaction_se"] = observed_se
        legacy_ok = legacy_ok and bool(np.isclose(observed, expected_pair[0], atol=1e-12, rtol=1e-10))
        legacy_ok = legacy_ok and bool(np.isclose(observed_se, expected_pair[1], atol=1e-12, rtol=1e-10))
    serializable_legacy_slopes = {
        f"{season}:{outcome}": value
        for (season, outcome), value in LEGACY_SLOPES.items()
    }
    check(
        gates,
        "V09_LEGACY_NUMERIC",
        legacy_ok,
        legacy_observed,
        {"slopes": serializable_legacy_slopes, "interactions": LEGACY_INTERACTIONS},
        str(run_root / "legacy"),
    )

    defect_audit = json.loads(
        (run_root / "legacy_cluster_se_defect_audit.json").read_text(encoding="utf-8")
    )
    defect_records = defect_audit.get("records", [])
    annual_defect_records = [
        row for row in defect_records if row.get("season_scope") == "annual_all_samples"
    ]
    bloom_defect_records = [
        row for row in defect_records if row.get("season_scope") == "bloom_season_06_10"
    ]
    defect_ok = (
        defect_audit.get("status") == "CONFIRMED"
        and len(annual_defect_records) == 2
        and len(bloom_defect_records) == 2
        and all(int(row["legacy_group_count"]) == 16 for row in annual_defect_records)
        and all(int(row["legacy_group_count"]) == 0 for row in bloom_defect_records)
        and all(int(row["reset_group_count"]) == 16 for row in defect_records)
        and all(float(row["cluster_se_legacy"]) == 0.0 for row in bloom_defect_records)
        and all(float(row["cluster_se_index_repaired"]) > 0.0 for row in bloom_defect_records)
        and all(float(row["beta_abs_difference"]) <= 1e-15 for row in defect_records)
    )
    check(
        gates,
        "V09B_LEGACY_CLUSTER_SE_DEFECT",
        defect_ok,
        defect_audit,
        "Bloom legacy grouper has 0 aligned groups; index repair restores 16 positive-SE groups with unchanged coefficients",
        str(run_root / "legacy_cluster_se_defect_audit.json"),
    )

    contrasts = pd.read_csv(run_root / "endpoint_specific_contrasts.csv")
    contrast_ok = len(contrasts) == 2 and set(contrasts["season_scope"]) == set(SEASONS)
    contrast_observed = []
    for _, row in contrasts.iterrows():
        valid = (
            abs(float(row["equality_residual"])) <= 1e-10
            and np.isfinite(float(row["cr1_se_unified"]))
            and float(row["cr1_se_unified"]) > 0
            and int(row["wcr_patterns"]) == 65536
            and int(row["paired_bootstrap_draws"]) == 9999
            and 0 <= float(row["wcr_p_two_sided"]) <= 1
            and 0 <= float(row["wcr_p_holm"]) <= 1
        )
        contrast_ok = contrast_ok and valid
        contrast_observed.append(row.to_dict())
    check(gates, "V10_ENDPOINT_CONTRAST", contrast_ok, contrast_observed, "2 finite algebraically equal contrasts", str(run_root / "endpoint_specific_contrasts.csv"))

    wcr = pd.read_csv(run_root / "wcr_signflip_t.csv.gz")
    wcr_counts = wcr.groupby("season_scope").size().to_dict()
    wcr_unique = wcr.groupby("season_scope")["pattern_id"].nunique().to_dict()
    wcr_ok = (
        wcr_counts == {season: 65536 for season in SEASONS}
        and wcr_unique == {season: 65536 for season in SEASONS}
        and wcr["finite"].astype(bool).all()
        and np.isfinite(wcr[["delta_star", "se_star", "t_star"]].to_numpy(float)).all()
        and (wcr["se_star"] > 0).all()
    )
    check(gates, "V11_WCR_COMPLETE", bool(wcr_ok), {"counts": wcr_counts, "unique": wcr_unique, "finite": bool(wcr["finite"].astype(bool).all())}, {season: 65536 for season in SEASONS}, str(run_root / "wcr_signflip_t.csv.gz"))

    bootstrap = pd.read_csv(run_root / "cluster_pairs_bootstrap.csv.gz")
    bootstrap_counts = bootstrap.groupby("season_scope").size().to_dict()
    bootstrap_unique = bootstrap.groupby("season_scope")["draw_id"].nunique().to_dict()
    bootstrap_ok = (
        bootstrap_counts == {season: 9999 for season in SEASONS}
        and bootstrap_unique == {season: 9999 for season in SEASONS}
        and bootstrap["finite"].astype(bool).all()
        and np.isfinite(bootstrap[["beta_cyano_star", "beta_chlorophyll_star", "difference_star"]].to_numpy(float)).all()
    )
    check(gates, "V12_BOOTSTRAP_COMPLETE", bool(bootstrap_ok), {"counts": bootstrap_counts, "unique": bootstrap_unique, "finite": bool(bootstrap["finite"].astype(bool).all())}, {season: 9999 for season in SEASONS}, str(run_root / "cluster_pairs_bootstrap.csv.gz"))

    matrix = pd.read_csv(run_root / "specification_matrix.csv")
    matrix_models = {season: set(matrix.loc[matrix["season_scope"] == season, "model_id"]) for season in SEASONS}
    matrix_ok = len(matrix) == 10 and all(matrix_models[season] == REQUIRED_MODELS for season in SEASONS)
    check(gates, "V13_SPECIFICATION_MATRIX", matrix_ok, {key: sorted(value) for key, value in matrix_models.items()}, sorted(REQUIRED_MODELS), str(run_root / "specification_matrix.csv"))

    status = "PASS" if all(gate["status"] == "PASS" for gate in gates) else "FAIL"
    verification = {
        "status": status,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_root.name,
        "gates": gates,
    }
    atomic_json(run_root / "verification.json", verification)
    if status != "PASS":
        raise SystemExit(1)

    artifact_paths = sorted(
        path for path in run_root.rglob("*")
        if path.is_file() and path.name not in {"artifact_hashes.sha256", "COMPLETE.json"}
    )
    hashes = "".join(f"{sha256_file(path)}  {path.relative_to(run_root)}\n" for path in artifact_paths)
    atomic_text(run_root / "artifact_hashes.sha256", hashes)
    complete = {
        "status": "COMPLETE",
        "run_id": run_root.name,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "verification_sha256": sha256_file(run_root / "verification.json"),
        "artifact_hashes_sha256": sha256_file(run_root / "artifact_hashes.sha256"),
    }
    atomic_json(run_root / "COMPLETE.json", complete)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--log-root", type=Path, required=True)
    parser.add_argument("--expected-code-sha256", required=True)
    parser.add_argument("--expected-panel-sha256", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    verify(parse_args())
