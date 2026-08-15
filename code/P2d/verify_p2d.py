#!/usr/bin/env python3
"""Fail-closed, branch-specific verification for a completed P2d analysis run."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


BASE_SHA = "cf60dc3bc4935a55ab6ed55df6e8bc67c82fa4c1136077c1efb755206057d4cf"
AMENDMENT_SHA = "c3e4fe46dff9f30978e2890187628cb9a77b48e50b6dcaee5a8dc40799f52c4e"
FROZEN_LEDGER_SHA = "5c55ed42f8dd264e44436208de334c22f8c9858691be46935a34a1e0945708cd"


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


def iso_epoch(value: str) -> float:
    return datetime.fromisoformat(value).timestamp()


def verify(args: argparse.Namespace) -> dict:
    root = args.run_root.resolve()
    allowed = Path(
        "/Users/eungyupark/Dropbox/Manuscripts/0_HAB/revision_1/03_analysis/output/P2d/runs"
    ).resolve()
    if allowed not in root.parents or not root.is_dir() or root.is_symlink():
        raise ValueError("run root is not a real directory inside the P2d run jail")

    gates: dict[str, dict] = {}

    def gate(name: str, condition: bool, evidence: object) -> None:
        gates[name] = {"status": "PASS" if condition else "FAIL", "evidence": evidence}

    manifest = json.loads((root / "source_manifest.json").read_text())
    created_epoch = iso_epoch(manifest["created_at_utc"])
    gate(
        "analysis_manifest_complete",
        manifest.get("status") == "ANALYSIS_COMPLETE_AWAITING_VERIFICATION",
        manifest.get("status"),
    )
    expected_branches = {
        "M5": [BASE_SHA],
        "M8": [BASE_SHA],
        "M9": [BASE_SHA, AMENDMENT_SHA],
    }
    actual_branches = {
        branch: [record["sha256"] for record in records]
        for branch, records in manifest.get("protocol_branches", {}).items()
    }
    gate("branch_specific_protocol_map", actual_branches == expected_branches, actual_branches)
    protocol_records = manifest["protocol_branches"]["M9"]
    gate(
        "fresh_protocols_predate_fresh_run",
        all(record["mtime"] < created_epoch for record in protocol_records),
        {"run_created_epoch": created_epoch, "protocol_records": protocol_records},
    )
    gate("immutable_base_hash", sha256_file(args.base_freeze) == BASE_SHA, str(args.base_freeze))
    gate("separate_amendment_hash", sha256_file(args.amendment) == AMENDMENT_SHA, str(args.amendment))

    first_manifest = json.loads((args.first_run / "source_manifest.json").read_text())
    first_protocol = first_manifest["sources"][0]
    gate(
        "pre_result_base_content_provenance",
        first_protocol["sha256"] == BASE_SHA
        and first_protocol["mtime"] < iso_epoch(first_manifest["created_at_utc"]),
        {
            "first_run_created_at": first_manifest["created_at_utc"],
            "recorded_protocol": first_protocol,
            "claim": "content hash predates first-run results; immutable-copy mtime is not used",
        },
    )
    gate(
        "amendment_not_backdated_into_first_run",
        AMENDMENT_SHA not in [record["sha256"] for record in first_manifest["sources"]]
        and args.amendment.stat().st_mtime > iso_epoch(first_manifest["created_at_utc"]),
        {
            "first_run_created_at": first_manifest["created_at_utc"],
            "amendment_mtime": args.amendment.stat().st_mtime,
        },
    )

    current_ledger_sha = sha256_file(args.current_ledger)
    warnings = []
    if current_ledger_sha != FROZEN_LEDGER_SHA:
        warnings.append(
            {
                "code": "NONCOMPUTATIONAL_LEDGER_SOURCE_DRIFT",
                "frozen_sha256": FROZEN_LEDGER_SHA,
                "current_sha256": current_ledger_sha,
                "current_mtime": args.current_ledger.stat().st_mtime,
                "scope": "The ledger is not a numerical model input; frozen branch definitions and all computational sources are separately hashed. Prior ledger bytes were not preserved, so an exact row-level diff is unavailable.",
            }
        )

    m5 = json.loads((root / "m5_result.json").read_text())
    comparator = pd.read_csv(root / "m5_legacy_comparator.csv")
    gate(
        "M5_axis_exhaustion_evidence",
        m5["verdict"] == "AXIS_EXHAUSTED"
        and not m5["event_study_run"]
        and not m5["parallel_trend_test_run"]
        and m5["chronology"]["n_resolved"] == 0
        and len(m5["chronology"]["unresolved_weirs"]) == 16
        and not m5["chronology"]["within_basin_variation"],
        m5,
    )
    gate(
        "M5_historical_comparator_reconciliation",
        len(comparator) == 4
        and comparator[["immediate_abs_diff", "late_abs_diff"]].to_numpy(float).max() <= 1e-12,
        {"rows": len(comparator), "max_abs_diff": float(comparator[["immediate_abs_diff", "late_abs_diff"]].to_numpy(float).max())},
    )

    m8 = json.loads((root / "m8_result.json").read_text())
    m8_estimates = pd.read_csv(root / "m8_estimates.csv")
    patterns = pd.read_csv(root / "m8_signflip_patterns.csv.gz")
    bootstrap = pd.read_csv(root / "m8_cluster_bootstrap.csv.gz")
    decomposition = pd.read_csv(root / "m8_decomposition.csv")
    gate(
        "M8_common_support_and_resample_counts",
        len(m8_estimates) == 2
        and m8_estimates["n"].eq(142).all()
        and m8_estimates["n_weirs"].eq(16).all()
        and patterns.groupby("season_scope").size().eq(65536).all()
        and bootstrap.groupby("season_scope").size().eq(9999).all()
        and np.isfinite(bootstrap["delta_star"]).all(),
        {
            "support": m8_estimates[["season_scope", "n", "n_weirs"]].to_dict("records"),
            "sign_patterns": patterns.groupby("season_scope").size().to_dict(),
            "bootstrap_draws": bootstrap.groupby("season_scope").size().to_dict(),
        },
    )
    annual = m8_estimates.loc[m8_estimates["season_scope"] == "annual_all_samples"].iloc[0]
    annual_decomp = decomposition.loc[decomposition["season_scope"] == "annual_all_samples"].set_index("component")
    spatial = bool(
        abs(annual_decomp.loc["within_weir", "spearman_delta_chla_minus_cyano"])
        < 0.5 * abs(annual_decomp.loc["pooled", "spearman_delta_chla_minus_cyano"])
        and abs(annual_decomp.loc["between_weir", "spearman_delta_chla_minus_cyano"])
        > abs(annual_decomp.loc["within_weir", "spearman_delta_chla_minus_cyano"])
    )
    gate(
        "M8_frozen_verdict_rule",
        annual["spearman_delta_chla_minus_cyano"] > 0
        and annual["exact_p_two_sided"] < 0.05
        and spatial
        and m8["spatial_dominance_flag"]
        and m8["verdict"] == "WEAKENS_OR_REDIRECTS",
        {"annual": annual.to_dict(), "spatial_dominance_recomputed": spatial},
    )

    m9 = json.loads((root / "m9_result.json").read_text())
    m9_models = pd.read_csv(root / "m9_two_part_models.csv")
    accounting = m9["sample_accounting"]
    occurrence_weir = pd.read_csv(root / "m9_occurrence_by_window_weir.csv")
    primary_deg = occurrence_weir.loc[
        (occurrence_weir["window"] == "primary_june_october")
        & occurrence_weir["degenerate"]
        & occurrence_weir["proportion"].eq(1.0)
    ]
    expected_counts = {
        "harmful_total_rows": 6748,
        "duplicate_measurement_keys": 3,
        "exact_duplicate_rows_collapsed": 3,
        "excluded_after_exact_dedup_for_missing_or_join": 2,
        "eligible_rows": 6743,
        "zeros": 3434,
        "positives": 3309,
        "n_weirs": 16,
    }
    gate(
        "M9_source_and_dedup_accounting",
        all(accounting[key] == value for key, value in expected_counts.items())
        and accounting["source_units"] == ["Cells/100mL"],
        accounting,
    )
    primary = m9_models.loc[
        (m9_models["window"] == "primary_june_october") & (~m9_models["calendar_balanced"])
    ].set_index("part")
    gate(
        "M9_primary_axis_exhaustion",
        m9["verdict"] == "AXIS_EXHAUSTED"
        and primary.loc["occurrence", "model_status"] == "HALTED"
        and "failed to converge" in primary.loc["occurrence", "error_message"]
        and primary.loc["positive", "model_status"] == "FIT"
        and set(primary_deg["weir_name"]) == {"강정고령보", "달성보", "창녕함안보"}
        and m9["primary_bootstrap"]["status"] == "NOT_RUN_PRIMARY_MODEL_HALTED"
        and not (root / "m9_primary_cluster_bootstrap.csv.gz").exists(),
        {
            "primary_models": primary.reset_index().to_dict("records"),
            "all_positive_weirs": sorted(primary_deg["weir_name"].tolist()),
            "bootstrap": m9["primary_bootstrap"],
        },
    )
    gate(
        "M9_separate_blockers_preserved",
        m9["threshold_branch"]["status"] == "BLOCKED"
        and not m9["threshold_branch"]["conversion_applied"]
        and m9["sampling_protocol_branch"]["status"] == "AXIS_EXHAUSTED"
        and not m9["sampling_protocol_branch"]["event_triggered_sampling_determined"],
        {
            "threshold": m9["threshold_branch"],
            "sampling_protocol": m9["sampling_protocol_branch"],
        },
    )

    symlinks = [str(path) for path in root.rglob("*") if path.is_symlink()]
    gate("no_symlink_artifacts", not symlinks, symlinks)

    excluded = {"artifact_hashes.csv", "verification.json", "COMPLETE"}
    artifacts = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name not in excluded and not path.name.endswith(".tmp"):
            artifacts.append(
                {
                    "relative_path": str(path.relative_to(root)),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    artifact_frame = pd.DataFrame(artifacts)
    artifact_frame.to_csv(root / "artifact_hashes.csv", index=False)
    ledger_hash = sha256_file(root / "artifact_hashes.csv")

    failed = [name for name, record in gates.items() if record["status"] != "PASS"]
    result = {
        "status": "FAIL" if failed else "PASS",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_root": str(root),
        "gates": gates,
        "failed_gates": failed,
        "warnings": warnings,
        "artifact_ledger": {
            "path": str((root / "artifact_hashes.csv").resolve()),
            "sha256": ledger_hash,
            "artifacts_hashed": len(artifact_frame),
            "excludes": sorted(excluded),
        },
    }
    atomic_json(root / "verification.json", result)
    if failed:
        raise ValueError(f"P2d verification failed: {failed}")
    verification_hash = sha256_file(root / "verification.json")
    atomic_text(
        root / "COMPLETE",
        "status=PASS\n"
        f"verified_at_utc={result['verified_at_utc']}\n"
        f"verification_sha256={verification_hash}\n"
        f"artifact_hashes_sha256={ledger_hash}\n",
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--first-run", type=Path, required=True)
    parser.add_argument("--base-freeze", type=Path, required=True)
    parser.add_argument("--amendment", type=Path, required=True)
    parser.add_argument("--current-ledger", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    outcome = verify(parse_args())
    print(json.dumps({"status": outcome["status"], "warnings": outcome["warnings"]}, ensure_ascii=False))
