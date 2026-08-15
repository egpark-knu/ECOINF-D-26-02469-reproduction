"""Two-part harmful-cyanobacteria models with weir-cluster covariance."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from scipy.special import expit


def make_fe_design(frame: pd.DataFrame, predictor: str, fe_cols: list[str]) -> tuple[np.ndarray, list[str]]:
    parts = [np.ones((len(frame), 1)), frame[predictor].to_numpy(float).reshape(-1, 1)]
    names = ["intercept", predictor]
    for column in fe_cols:
        values = frame[column].astype(str)
        levels = sorted(values.unique().tolist())
        for level in levels[1:]:
            parts.append((values == level).to_numpy(float).reshape(-1, 1))
            names.append(f"{column}[{level}]")
    design = np.column_stack(parts)
    if np.linalg.matrix_rank(design) != design.shape[1]:
        raise ValueError("rank-deficient fixed-effect design")
    return design, names


def _cluster_covariance(bread: np.ndarray, scores: np.ndarray, clusters: pd.Series | np.ndarray, n: int, k: int) -> np.ndarray:
    labels = np.asarray(pd.Series(clusters).astype(str))
    unique = sorted(set(labels))
    if len(unique) < 2:
        raise ValueError("at least two clusters required")
    meat = np.zeros((k, k))
    for label in unique:
        score = scores[labels == label].sum(axis=0)
        meat += np.outer(score, score)
    correction = (len(unique) / (len(unique) - 1)) * ((n - 1) / (n - k))
    return correction * bread @ meat @ bread


def _result(beta: np.ndarray, cov: np.ndarray, names: list[str], clusters: pd.Series | np.ndarray, converged: bool = True, iterations: int = 1) -> dict:
    se = np.sqrt(np.maximum(np.diag(cov), 0))
    g = pd.Series(clusters).astype(str).nunique()
    t_values = beta / se
    p_values = 2 * stats.t.sf(np.abs(t_values), df=g - 1)
    critical = stats.t.ppf(0.975, df=g - 1)
    return {
        "coef": dict(zip(names, map(float, beta))),
        "se_cluster": dict(zip(names, map(float, se))),
        "p_two_sided": dict(zip(names, map(float, p_values))),
        "ci_low": dict(zip(names, map(float, beta - critical * se))),
        "ci_high": dict(zip(names, map(float, beta + critical * se))),
        "n": int(len(clusters)),
        "k": int(len(names)),
        "n_clusters": int(g),
        "converged": bool(converged),
        "iterations": int(iterations),
    }


def fit_ols_cluster(y: np.ndarray, x: np.ndarray, clusters: pd.Series | np.ndarray, names: list[str], weights: np.ndarray | None = None) -> dict:
    y = np.asarray(y, dtype=float)
    weights = np.ones(len(y)) if weights is None else np.asarray(weights, dtype=float)
    if not np.isfinite(y).all() or not np.isfinite(x).all() or not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("nonfinite OLS input")
    xtwx = x.T @ (weights[:, None] * x)
    if np.linalg.matrix_rank(xtwx) != x.shape[1]:
        raise ValueError("rank-deficient weighted OLS")
    bread = np.linalg.inv(xtwx)
    beta = bread @ (x.T @ (weights * y))
    resid = y - x @ beta
    scores = x * (weights * resid)[:, None]
    cov = _cluster_covariance(bread, scores, clusters, len(y), x.shape[1])
    return _result(beta, cov, names, clusters)


def fit_logit_cluster(
    y: np.ndarray,
    x: np.ndarray,
    clusters: pd.Series | np.ndarray,
    names: list[str],
    weights: np.ndarray | None = None,
    max_iter: int = 100,
    tolerance: float = 1e-10,
) -> dict:
    y = np.asarray(y, dtype=float)
    weights = np.ones(len(y)) if weights is None else np.asarray(weights, dtype=float)
    if not np.isfinite(y).all() or not np.isfinite(x).all() or not np.isfinite(weights).all():
        raise ValueError("nonfinite logit input")
    if ((y < 0) | (y > 1)).any() or (weights <= 0).any():
        raise ValueError("invalid binomial response or weight")
    beta = np.zeros(x.shape[1])
    converged = False
    for iteration in range(1, max_iter + 1):
        eta = np.clip(x @ beta, -30, 30)
        probability = np.clip(expit(eta), 1e-9, 1 - 1e-9)
        variance_weight = weights * probability * (1 - probability)
        hessian = x.T @ (variance_weight[:, None] * x)
        if np.linalg.matrix_rank(hessian) != x.shape[1]:
            raise ValueError("rank-deficient logit Hessian")
        score = x.T @ (weights * (y - probability))
        step = np.linalg.solve(hessian, score)
        beta_new = beta + step
        if not np.isfinite(beta_new).all() or np.max(np.abs(beta_new)) > 1e6:
            raise ValueError("logit separation or divergence")
        beta = beta_new
        if np.max(np.abs(step)) < tolerance:
            converged = True
            break
    if not converged:
        raise ValueError("logit failed to converge")
    probability = np.clip(expit(np.clip(x @ beta, -30, 30)), 1e-9, 1 - 1e-9)
    variance_weight = weights * probability * (1 - probability)
    hessian = x.T @ (variance_weight[:, None] * x)
    bread = np.linalg.inv(hessian)
    scores = x * (weights * (y - probability))[:, None]
    cov = _cluster_covariance(bread, scores, clusters, len(y), x.shape[1])
    return _result(beta, cov, names, clusters, converged=True, iterations=iteration)


def prepare_harmful_panel(raw: pd.DataFrame, tau: pd.DataFrame) -> pd.DataFrame:
    frame = raw.loc[
        (raw["variable"].astype(str) == "harmful_cyanobacteria_total")
        & (raw["source_field"].astype(str) == "iemBgalageCellCo")
    ].copy()
    units = sorted(frame["unit"].dropna().astype(str).unique().tolist())
    if units != ["Cells/100mL"]:
        raise ValueError(f"unexpected harmful-cyanobacteria unit: {units}")
    keys = ["station_code", "sampling_date", "variable"]
    duplicate = frame.duplicated(keys, keep=False)
    if duplicate.any():
        if "source_row_locator" not in frame.columns:
            raise ValueError("duplicate measurement keys lack source-row locators")
        duplicate_rows = frame.loc[duplicate].copy()
        compare_columns = [
            column
            for column in frame.columns
            if column not in set(keys + ["source_row_locator"])
        ]
        conflicts = duplicate_rows.groupby(keys, dropna=False)[compare_columns].nunique(dropna=False)
        if (conflicts > 1).any().any():
            raise ValueError("conflicting duplicate station-date-variable measurements")
        frame = (
            frame.sort_values(keys + ["source_row_locator"])
            .drop_duplicates(keys, keep="first")
            .copy()
        )
    frame["sampling_date"] = pd.to_datetime(frame["sampling_date"], errors="coerce")
    frame["sampling_year"] = pd.to_numeric(frame["sampling_year"], errors="coerce")
    frame["sampling_month"] = pd.to_numeric(frame["sampling_month"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    if (frame["value"].dropna() < 0).any():
        raise ValueError("negative harmful-cyanobacteria count")
    tau = tau[["weir_name", "year", "tau_days"]].copy()
    tau["tau_days"] = pd.to_numeric(tau["tau_days"], errors="coerce")
    if tau.duplicated(["weir_name", "year"]).any():
        conflicting = tau.groupby(["weir_name", "year"])["tau_days"].nunique(dropna=False)
        if (conflicting > 1).any():
            raise ValueError("conflicting tau values within weir-year")
        tau = tau.drop_duplicates(["weir_name", "year"])
    frame = frame.merge(tau, left_on=["weir_name", "sampling_year"], right_on=["weir_name", "year"], how="left", validate="many_to_one")
    required = ["sampling_date", "sampling_year", "sampling_month", "weir_name", "value", "tau_days"]
    frame = frame.dropna(subset=required).copy()
    if (frame["tau_days"] <= 0).any():
        raise ValueError("nonpositive residence time")
    frame["log2_tau"] = np.log2(frame["tau_days"].astype(float))
    frame["occurrence"] = (frame["value"] > 0).astype(float)
    frame["positive_log"] = np.nan
    positive = frame["value"] > 0
    frame.loc[positive, "positive_log"] = np.log(frame.loc[positive, "value"])
    return frame


def aggregate_calendar_cells(frame: pd.DataFrame) -> pd.DataFrame:
    keys = ["weir_name", "sampling_year", "sampling_month"]
    grouped = frame.groupby(keys, as_index=False).agg(
        log2_tau=("log2_tau", "first"),
        n_observations=("occurrence", "size"),
        n_occurrences=("occurrence", "sum"),
        occurrence_share=("occurrence", "mean"),
        n_positive=("positive_log", "count"),
        mean_positive_log=("positive_log", "mean"),
    )
    return grouped


def holm_adjust(p_values: list[float] | np.ndarray) -> np.ndarray:
    values = np.asarray(p_values, dtype=float)
    order = np.argsort(values)
    adjusted = np.empty_like(values)
    running = 0.0
    m = len(values)
    for rank, index in enumerate(order):
        candidate = (m - rank) * values[index]
        running = max(running, candidate)
        adjusted[index] = min(running, 1.0)
    return adjusted
