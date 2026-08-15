"""Pure shared-support and fixed-effect design builders for M1 reconciliation."""

from __future__ import annotations

import numpy as np
import pandas as pd


CYANO_COLUMN = "log1p_harmful_cyanobacteria_total_mean"
CHLA_COLUMN = "log1p_chlorophyll_a_mean"
ENDPOINT_Z = {"cyano": "z_cyano", "chlorophyll_a": "z_chlorophyll_a"}


def prepare_shared_support(panel: pd.DataFrame, season: str) -> pd.DataFrame:
    required = ["weir_name", "year", "tau_days", CYANO_COLUMN, CHLA_COLUMN]
    missing = [column for column in required if column not in panel.columns]
    if missing:
        raise ValueError(f"missing design columns: {missing}")
    base = panel.loc[panel["season_scope"] == season, required].copy()
    base = base.dropna(subset=required).sort_values(["weir_name", "year"]).reset_index(drop=True)
    if base.duplicated(["weir_name", "year"]).any():
        raise ValueError("shared-support keys are not unique")
    if (base["tau_days"] <= 0).any():
        raise ValueError("tau_days must be positive")
    base["log1p_tau"] = np.log1p(base["tau_days"].astype(float))
    for source, target in [(CYANO_COLUMN, "z_cyano"), (CHLA_COLUMN, "z_chlorophyll_a")]:
        values = base[source].astype(float)
        sd = values.std(ddof=1)
        if not np.isfinite(sd) or sd <= 0:
            raise ValueError(f"invalid standard deviation for {source}: {sd}")
        base[target] = (values - values.mean()) / sd
    return base


def _dummy_columns(values: pd.Series, prefix: str) -> tuple[list[np.ndarray], list[str], str]:
    levels = sorted(values.astype(str).unique().tolist())
    if not levels:
        raise ValueError(f"no levels for {prefix}")
    arrays = [(values.astype(str) == level).astype(float).to_numpy() for level in levels[1:]]
    names = [f"{prefix}[{level}]" for level in levels[1:]]
    return arrays, names, levels[0]


def separate_design(
    base: pd.DataFrame,
    endpoint: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], dict]:
    if endpoint not in ENDPOINT_Z:
        raise ValueError(f"unknown endpoint: {endpoint}")
    parts = [np.ones(len(base)), base["log1p_tau"].astype(float).to_numpy()]
    names = ["intercept", "log1p_tau"]
    weir_parts, weir_names, reference_weir = _dummy_columns(base["weir_name"], "weir_name")
    year_parts, year_names, reference_year = _dummy_columns(base["year"].astype(str), "year")
    parts.extend(weir_parts)
    parts.extend(year_parts)
    names.extend(weir_names)
    names.extend(year_names)
    x = np.column_stack(parts)
    y = base[ENDPOINT_Z[endpoint]].astype(float).to_numpy()
    clusters = base["weir_name"].astype(str).to_numpy()
    meta = {
        "endpoint": endpoint,
        "reference_weir": reference_weir,
        "reference_year": reference_year,
        "column_names": names,
        "shape": [int(x.shape[0]), int(x.shape[1])],
        "rank": int(np.linalg.matrix_rank(x)),
    }
    return x, y, clusters, names, meta


def endpoint_specific_design(
    base: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], dict]:
    frames = []
    for endpoint, indicator in [("chlorophyll_a", 0.0), ("cyano", 1.0)]:
        frame = base[["weir_name", "year", "log1p_tau", ENDPOINT_Z[endpoint]]].copy()
        frame = frame.rename(columns={ENDPOINT_Z[endpoint]: "outcome_std"})
        frame["outcome_type"] = endpoint
        frame["outcome_is_cyano"] = indicator
        frames.append(frame)
    stacked = pd.concat(frames, ignore_index=True)
    stacked["log1p_tau_x_cyano"] = stacked["log1p_tau"] * stacked["outcome_is_cyano"]

    parts = [
        np.ones(len(stacked)),
        stacked["log1p_tau"].astype(float).to_numpy(),
        stacked["outcome_is_cyano"].astype(float).to_numpy(),
        stacked["log1p_tau_x_cyano"].astype(float).to_numpy(),
    ]
    names = ["intercept", "log1p_tau", "outcome_is_cyano", "log1p_tau_x_cyano"]

    weir_parts, weir_names, reference_weir = _dummy_columns(stacked["weir_name"], "weir_name")
    year_parts, year_names, reference_year = _dummy_columns(stacked["year"].astype(str), "year")
    parts.extend(weir_parts)
    parts.extend(year_parts)
    names.extend(weir_names)
    names.extend(year_names)

    cyano = stacked["outcome_is_cyano"].astype(float).to_numpy()
    for array, name in zip(weir_parts, weir_names):
        parts.append(array * cyano)
        names.append(f"cyano_x_{name}")
    for array, name in zip(year_parts, year_names):
        parts.append(array * cyano)
        names.append(f"cyano_x_{name}")

    x = np.column_stack(parts)
    y = stacked["outcome_std"].astype(float).to_numpy()
    clusters = stacked["weir_name"].astype(str).to_numpy()
    meta = {
        "reference_weir": reference_weir,
        "reference_year": reference_year,
        "column_names": names,
        "shape": [int(x.shape[0]), int(x.shape[1])],
        "rank": int(np.linalg.matrix_rank(x)),
        "n_original": int(len(base)),
        "n_stacked": int(len(stacked)),
        "stack_order": ["chlorophyll_a", "cyano"],
    }
    return x, y, clusters, names, meta
