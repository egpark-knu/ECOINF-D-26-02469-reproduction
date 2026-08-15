"""Safe adapter for the byte-identical historical M1 module."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from panel_contract import sha256_file


EXPECTED_VENDOR_SHA256 = "c895385a565dc06835e0a03129fbd3fcb97734aaaa2d62d9838c0e6917ca10b0"

LEGACY_TARGETS = {
    ("annual_all_samples", "cyano"): 0.6874057079174496,
    ("annual_all_samples", "chlorophyll_a"): 0.14757774021651276,
    ("bloom_season_06_10", "cyano"): 0.6186412520414742,
    ("bloom_season_06_10", "chlorophyll_a"): 0.3216193241323556,
}
INTERACTION_TARGETS = {
    "annual_all_samples": {
        "estimate": 0.887440253669714,
        "se": 0.1792907058011252,
        "ci_low": 0.5052911602668142,
        "ci_high": 1.2695893470726138,
        "p": 0.000174599438830119,
        "ri_p": 0.0002,
    },
    "bloom_season_06_10": {
        "estimate": 1.0350637385933135,
        "se": 0.15187298089532514,
        "ci_low": 0.7113541424811642,
        "ci_high": 1.3587733347054627,
        "p": 5.839045628837723e-06,
        "ri_p": 0.0002,
    },
}


def _load_vendor(path: Path):
    observed = sha256_file(path)
    if observed != EXPECTED_VENDOR_SHA256:
        raise ValueError(f"vendor hash mismatch: {observed}")
    spec = importlib.util.spec_from_file_location("p2a_frozen_legacy", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import vendor module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_legacy(
    vendor_path: Path,
    panel_path: Path,
    legacy_root: Path,
    seed: int,
    n_perm: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if legacy_root.exists():
        raise FileExistsError(f"legacy output root already exists: {legacy_root}")
    module = _load_vendor(vendor_path)
    module.PANEL = panel_path
    module.OUT = legacy_root
    module.FIG = legacy_root / "figures"
    module.TABLES = legacy_root / "tables"
    module.LOG = legacy_root / "log"
    module.SEED = int(seed)
    module.N_PERM = int(n_perm)
    module.main()
    models_path = legacy_root / "standardized_tau_models.csv"
    interaction_path = legacy_root / "specificity_interaction.csv"
    if not models_path.is_file() or not interaction_path.is_file():
        raise FileNotFoundError("legacy module did not produce required CSV outputs")
    return pd.read_csv(models_path), pd.read_csv(interaction_path)


def assert_legacy_regression(
    models: pd.DataFrame,
    interaction: pd.DataFrame,
    atol: float = 1e-12,
    rtol: float = 1e-10,
) -> dict:
    if len(models) != 10 or len(interaction) != 2:
        raise AssertionError(f"legacy row counts differ: models={len(models)}, interaction={len(interaction)}")
    primary = models[models["model_family"] == "z_standardized_log1p_outcome"]
    checks = []
    for (season, outcome), expected in LEGACY_TARGETS.items():
        row = primary[(primary["season_scope"] == season) & (primary["outcome"] == outcome)]
        if len(row) != 1:
            raise AssertionError(f"missing/duplicate legacy primary row: {(season, outcome)}")
        observed = float(row.iloc[0]["beta_log1p_tau"])
        passed = bool(np.isclose(observed, expected, atol=atol, rtol=rtol))
        checks.append({"target": f"{season}:{outcome}:beta", "observed": observed, "expected": expected, "pass": passed})
        if not passed:
            raise AssertionError(f"legacy slope mismatch {(season, outcome)}: {observed} vs {expected}")
    for season, target in INTERACTION_TARGETS.items():
        row = interaction[interaction["season_scope"] == season]
        if len(row) != 1:
            raise AssertionError(f"missing/duplicate legacy interaction row: {season}")
        row = row.iloc[0]
        fields = {
            "estimate": "interaction_beta_cyano_minus_chla",
            "se": "cluster_se",
            "ci_low": "cluster_ci_low",
            "ci_high": "cluster_ci_high",
            "p": "cluster_p_two_sided",
            "ri_p": "ri_p_right_cyano_gt_chla",
        }
        for label, column in fields.items():
            observed = float(row[column])
            expected = float(target[label])
            passed = bool(np.isclose(observed, expected, atol=atol, rtol=rtol))
            checks.append({"target": f"{season}:interaction:{label}", "observed": observed, "expected": expected, "pass": passed})
            if not passed:
                raise AssertionError(f"legacy interaction mismatch {season} {label}: {observed} vs {expected}")
        if int(row["n_stacked"]) != 288 or int(row["n_original_weir_years"]) != 144:
            raise AssertionError(f"legacy support mismatch for {season}")
        if int(row["n_permutations"]) != 4999:
            raise AssertionError(f"legacy permutation count mismatch for {season}")
    return {
        "status": "PASS",
        "models_rows": int(len(models)),
        "interaction_rows": int(len(interaction)),
        "checks": checks,
        "legacy_zero_se_rows": int((models["cluster_se"] == 0).sum()),
    }
