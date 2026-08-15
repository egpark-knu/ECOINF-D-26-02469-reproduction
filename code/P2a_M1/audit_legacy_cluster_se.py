#!/usr/bin/env python3
"""Audit the frozen legacy cluster-SE index alignment without altering it."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys

import pandas as pd


SEASONS = ["annual_all_samples", "bloom_season_06_10"]
OUTCOMES = ["cyano", "chlorophyll_a"]


def load_vendor(path: Path):
    module_name = "p2a_frozen_legacy_cluster_se_audit"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load frozen vendor module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def audit(vendor_path: Path, panel_path: Path, output_path: Path) -> None:
    module = load_vendor(vendor_path)
    panel = pd.read_csv(panel_path)
    records: list[dict] = []

    for season in SEASONS:
        for outcome in OUTCOMES:
            frame = module.one_outcome_frame(panel, season, outcome, True)
            legacy_groups = pd.Series(range(len(frame))).groupby(
                frame["weir_name"].astype(str)
            ).groups
            reset_frame = frame.reset_index(drop=True)
            reset_groups = pd.Series(range(len(reset_frame))).groupby(
                reset_frame["weir_name"].astype(str)
            ).groups
            old = module.ols_fit(
                frame,
                "outcome_value",
                ["log1p_tau"],
                ["weir_name", "year"],
                "log1p_tau",
            )
            repaired = module.ols_fit(
                reset_frame,
                "outcome_value",
                ["log1p_tau"],
                ["weir_name", "year"],
                "log1p_tau",
            )
            records.append(
                {
                    "season_scope": season,
                    "outcome": outcome,
                    "n": int(len(frame)),
                    "original_index_min": int(frame.index.min()),
                    "original_index_max": int(frame.index.max()),
                    "legacy_group_count": int(len(legacy_groups)),
                    "reset_group_count": int(len(reset_groups)),
                    "beta_legacy": float(old.beta),
                    "beta_index_repaired": float(repaired.beta),
                    "beta_abs_difference": float(abs(old.beta - repaired.beta)),
                    "cluster_se_legacy": float(old.se_cluster),
                    "cluster_se_index_repaired": float(repaired.se_cluster),
                }
            )

    annual = [row for row in records if row["season_scope"] == "annual_all_samples"]
    bloom = [row for row in records if row["season_scope"] == "bloom_season_06_10"]
    confirmed = (
        all(row["legacy_group_count"] == 16 for row in annual)
        and all(row["legacy_group_count"] == 0 for row in bloom)
        and all(row["reset_group_count"] == 16 for row in records)
        and all(row["cluster_se_legacy"] == 0.0 for row in bloom)
        and all(row["cluster_se_index_repaired"] > 0.0 for row in bloom)
        and all(row["beta_abs_difference"] <= 1e-15 for row in records)
    )
    result = {
        "audit_id": "P2a_legacy_cluster_se_index_alignment",
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "CONFIRMED" if confirmed else "NOT_CONFIRMED",
        "scope": "Frozen legacy per-endpoint clustered uncertainty only; no historical file was modified.",
        "root_cause": (
            "cluster_se groups a RangeIndex Series by a caller-indexed clusters Series; pandas aligns "
            "the external grouper on labels. Bloom rows retain labels 144..287 while the grouped "
            "Series has labels 0..143, producing zero groups and a zero meat matrix."
        ),
        "interpretation": (
            "Resetting the analysis-frame index restores 16 groups and positive Bloom clustered SEs "
            "without changing coefficients. This is an E4 legacy uncertainty-code defect, not an "
            "explanation for the common-FE versus endpoint-specific coefficient gap."
        ),
        "groupby_expression": (
            "pd.Series(np.arange(len(clusters))).groupby(clusters.astype(str)).groups"
        ),
        "records": records,
    }
    atomic_json(output_path, result)
    if not confirmed:
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vendor", type=Path, required=True)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    audit(args.vendor.resolve(), args.panel.resolve(), args.output.resolve())
