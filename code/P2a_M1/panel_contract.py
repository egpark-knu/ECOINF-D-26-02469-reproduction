"""P2a input contract and output-jail checks."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
import pandas as pd


EXPECTED_SEASONS = {
    "annual_all_samples": 144,
    "bloom_season_06_10": 144,
}
OUTCOME_COLUMNS = [
    "log1p_harmful_cyanobacteria_total_mean",
    "log1p_chlorophyll_a_mean",
]
REQUIRED_COLUMNS = ["tau_days", "weir_name", "year", *OUTCOME_COLUMNS]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def validate_new_root(candidate: Path, allowed_parent: Path) -> Path:
    """Return resolved candidate if it is a fresh, non-symlinked descendant."""
    allowed_abs = _absolute_without_resolving(allowed_parent)
    candidate_abs = _absolute_without_resolving(candidate)
    if not allowed_abs.is_dir():
        raise FileNotFoundError(f"allowlisted parent does not exist: {allowed_abs}")
    try:
        relative = candidate_abs.relative_to(allowed_abs)
    except ValueError as exc:
        raise ValueError(f"path escapes allowlist: {candidate_abs}") from exc
    if not relative.parts:
        raise ValueError("candidate must be a strict descendant of allowlisted parent")
    current = allowed_abs
    if current.is_symlink():
        raise ValueError(f"symlinked allowlist is forbidden: {current}")
    for part in relative.parts[:-1]:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError(f"symlink path component is forbidden: {current}")
    if candidate_abs.exists() or candidate_abs.is_symlink():
        raise FileExistsError(f"fresh root already exists: {candidate_abs}")
    resolved = candidate_abs.resolve(strict=False)
    if allowed_abs.resolve() not in resolved.parents:
        raise ValueError(f"resolved path escapes allowlist: {resolved}")
    return resolved


def validate_panel(path: Path) -> tuple[pd.DataFrame, dict]:
    panel = pd.read_csv(path)
    if panel.shape != (288, 32):
        raise ValueError(f"panel shape mismatch: {panel.shape}")
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in panel.columns]
    if missing_columns:
        raise ValueError(f"missing required columns: {missing_columns}")

    for column in ["tau_days", "year", *OUTCOME_COLUMNS]:
        panel[column] = pd.to_numeric(panel[column], errors="coerce")

    season_counts = {
        str(key): int(value)
        for key, value in panel["season_scope"].value_counts().sort_index().items()
    }
    if season_counts != EXPECTED_SEASONS:
        raise ValueError(f"season counts mismatch: {season_counts}")

    duplicate_keys = int(panel.duplicated(["season_scope", "weir_name", "year"]).sum())
    missingness = {column: int(panel[column].isna().sum()) for column in REQUIRED_COLUMNS}
    nonfinite = {
        column: int((~np.isfinite(panel[column].astype(float))).sum())
        for column in ["tau_days", "year", *OUTCOME_COLUMNS]
    }
    tau_nonpositive = int((panel["tau_days"] <= 0).sum())
    if duplicate_keys or any(missingness.values()) or any(nonfinite.values()) or tau_nonpositive:
        raise ValueError(
            f"panel validity failure: duplicates={duplicate_keys}, missing={missingness}, "
            f"nonfinite={nonfinite}, tau_nonpositive={tau_nonpositive}"
        )

    n_weirs = int(panel["weir_name"].astype(str).nunique())
    n_years = int(panel["year"].nunique())
    year_range = [int(panel["year"].min()), int(panel["year"].max())]
    if (n_weirs, n_years, year_range) != (16, 9, [2017, 2025]):
        raise ValueError(f"panel index mismatch: {(n_weirs, n_years, year_range)}")

    shared_support_counts: dict[str, int] = {}
    zscore_metadata: dict[str, dict] = {}
    for season in sorted(EXPECTED_SEASONS):
        subset = panel.loc[panel["season_scope"] == season].dropna(subset=REQUIRED_COLUMNS)
        shared_support_counts[season] = int(len(subset))
        zscore_metadata[season] = {
            column: {
                "mean": float(subset[column].mean()),
                "sd_ddof1": float(subset[column].std(ddof=1)),
            }
            for column in OUTCOME_COLUMNS
        }
    if shared_support_counts != EXPECTED_SEASONS:
        raise ValueError(f"shared support mismatch: {shared_support_counts}")

    audit = {
        "input_path": str(path),
        "input_sha256": sha256_file(path),
        "shape": [int(panel.shape[0]), int(panel.shape[1])],
        "required_columns": REQUIRED_COLUMNS,
        "season_counts": season_counts,
        "duplicate_keys": duplicate_keys,
        "missingness": missingness,
        "nonfinite": nonfinite,
        "tau_nonpositive": tau_nonpositive,
        "n_weirs": n_weirs,
        "n_years": n_years,
        "year_range": year_range,
        "shared_support_counts": shared_support_counts,
        "zscore_metadata": zscore_metadata,
    }
    return panel, audit
