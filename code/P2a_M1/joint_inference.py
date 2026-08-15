"""Dependence-aware OLS and resampling for the P2a endpoint contrast."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class FitResult:
    coef: np.ndarray
    cov_cluster: np.ndarray
    se_cluster: np.ndarray
    fitted: np.ndarray
    resid: np.ndarray
    names: list[str]
    rank: int
    n: int
    k: int
    n_clusters: int

    @property
    def coef_by_name(self) -> dict[str, float]:
        return {name: float(value) for name, value in zip(self.names, self.coef)}

    @property
    def se_by_name(self) -> dict[str, float]:
        return {name: float(value) for name, value in zip(self.names, self.se_cluster)}


def _cluster_covariance(
    x: np.ndarray,
    residual: np.ndarray,
    clusters: np.ndarray,
) -> np.ndarray:
    n, k = x.shape
    cluster_values = np.asarray(clusters).astype(str)
    unique = sorted(np.unique(cluster_values).tolist())
    g = len(unique)
    if g <= 1 or n <= k:
        raise ValueError(f"invalid cluster covariance dimensions: n={n}, k={k}, g={g}")
    bread = np.linalg.pinv(x.T @ x)
    meat = np.zeros((k, k), dtype=float)
    for cluster in unique:
        idx = cluster_values == cluster
        score = x[idx].T @ residual[idx]
        meat += np.outer(score, score)
    correction = (g / (g - 1)) * ((n - 1) / (n - k))
    covariance = correction * bread @ meat @ bread
    covariance = (covariance + covariance.T) / 2.0
    return covariance


def fit_ols_cluster(
    x: np.ndarray,
    y: np.ndarray,
    clusters: np.ndarray,
    names: list[str],
) -> FitResult:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    clusters = np.asarray(clusters).astype(str)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != len(y) or len(clusters) != len(y):
        raise ValueError("incompatible OLS arrays")
    if x.shape[1] != len(names) or len(set(names)) != len(names):
        raise ValueError("coefficient names are missing or duplicated")
    coef, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    if rank != x.shape[1]:
        raise ValueError(f"rank-deficient design: rank={rank}, k={x.shape[1]}")
    fitted = x @ coef
    residual = y - fitted
    covariance = _cluster_covariance(x, residual, clusters)
    diagonal = np.diag(covariance)
    if np.any(diagonal < -1e-12):
        raise ValueError("negative cluster covariance diagonal")
    se = np.sqrt(np.maximum(diagonal, 0.0))
    return FitResult(
        coef=coef,
        cov_cluster=covariance,
        se_cluster=se,
        fitted=fitted,
        resid=residual,
        names=list(names),
        rank=int(rank),
        n=int(len(y)),
        k=int(x.shape[1]),
        n_clusters=int(len(np.unique(clusters))),
    )


def analytic_contrast(fit: FitResult, coefficient: str) -> dict[str, float]:
    index = fit.names.index(coefficient)
    estimate = float(fit.coef[index])
    se = float(fit.se_cluster[index])
    if not np.isfinite(se) or se <= 0:
        raise ValueError(f"nonpositive/nonfinite contrast SE: {se}")
    df = fit.n_clusters - 1
    t_value = estimate / se
    tcrit = float(stats.t.ppf(0.975, df))
    return {
        "estimate": estimate,
        "se": se,
        "t": float(t_value),
        "df": int(df),
        "ci_low": float(estimate - tcrit * se),
        "ci_high": float(estimate + tcrit * se),
        "p_two_sided": float(2 * stats.t.sf(abs(t_value), df)),
    }


def rademacher_signs(n_clusters: int) -> np.ndarray:
    if n_clusters <= 0 or n_clusters > 20:
        raise ValueError("n_clusters must be between 1 and 20")
    pattern_ids = np.arange(1 << n_clusters, dtype=np.uint32)[:, None]
    bit_positions = np.arange(n_clusters, dtype=np.uint32)[None, :]
    bits = (pattern_ids >> bit_positions) & 1
    return (2.0 * bits.astype(float)) - 1.0


def apply_cluster_signs(
    residual: np.ndarray,
    clusters: np.ndarray,
    sign_by_cluster: dict[str, float],
) -> np.ndarray:
    cluster_values = np.asarray(clusters).astype(str)
    signs = np.array([sign_by_cluster[value] for value in cluster_values], dtype=float)
    return np.asarray(residual, dtype=float) * signs


def restricted_wcr_bootstrap_t(
    x: np.ndarray,
    y: np.ndarray,
    clusters: np.ndarray,
    names: list[str],
    coefficient: str,
    n_patterns: int,
    chunk_size: int = 1024,
) -> tuple[pd.DataFrame, dict[str, float]]:
    full = fit_ols_cluster(x, y, clusters, names)
    observed = analytic_contrast(full, coefficient)
    coefficient_index = names.index(coefficient)
    restricted_x = np.delete(np.asarray(x, dtype=float), coefficient_index, axis=1)
    restricted_coef, _, restricted_rank, _ = np.linalg.lstsq(restricted_x, y, rcond=None)
    if restricted_rank != restricted_x.shape[1]:
        raise ValueError("restricted design is rank-deficient")
    restricted_fitted = restricted_x @ restricted_coef
    restricted_residual = np.asarray(y, dtype=float) - restricted_fitted

    cluster_values = np.asarray(clusters).astype(str)
    unique_clusters = sorted(np.unique(cluster_values).tolist())
    if n_patterns != (1 << len(unique_clusters)):
        raise ValueError("n_patterns must exhaust the Rademacher cluster support")
    cluster_index = np.array([unique_clusters.index(value) for value in cluster_values], dtype=int)
    membership = np.zeros((len(cluster_values), len(unique_clusters)), dtype=float)
    membership[np.arange(len(cluster_values)), cluster_index] = 1.0

    x = np.asarray(x, dtype=float)
    bread = np.linalg.pinv(x.T @ x)
    projection = bread @ x.T
    influence_weight = x @ bread[:, coefficient_index]
    n, k = x.shape
    g = len(unique_clusters)
    correction = (g / (g - 1)) * ((n - 1) / (n - k))

    all_signs = rademacher_signs(g)
    pattern_ids = np.arange(n_patterns, dtype=int)
    delta_star = np.empty(n_patterns, dtype=float)
    se_star = np.empty(n_patterns, dtype=float)
    t_star = np.empty(n_patterns, dtype=float)

    for start in range(0, n_patterns, chunk_size):
        stop = min(start + chunk_size, n_patterns)
        row_signs = all_signs[start:stop, cluster_index]
        y_star = restricted_fitted[None, :] + row_signs * restricted_residual[None, :]
        coef_star = y_star @ projection.T
        residual_star = y_star - coef_star @ x.T
        cluster_scores = (residual_star * influence_weight[None, :]) @ membership
        variance_star = correction * np.sum(cluster_scores ** 2, axis=1)
        se_chunk = np.sqrt(np.maximum(variance_star, 0.0))
        delta_chunk = coef_star[:, coefficient_index]
        delta_star[start:stop] = delta_chunk
        se_star[start:stop] = se_chunk
        t_star[start:stop] = np.divide(
            delta_chunk,
            se_chunk,
            out=np.full_like(delta_chunk, np.nan),
            where=se_chunk > 0,
        )

    finite = np.isfinite(delta_star) & np.isfinite(se_star) & np.isfinite(t_star) & (se_star > 0)
    result = pd.DataFrame({
        "pattern_id": pattern_ids,
        "delta_star": delta_star,
        "se_star": se_star,
        "t_star": t_star,
        "finite": finite,
    })
    if not finite.all():
        raise ValueError(f"nonfinite WCR patterns: {int((~finite).sum())}")
    p_value = float(np.mean(np.abs(t_star) >= abs(observed["t"])))
    summary = {
        **observed,
        "p_wcr_two_sided": p_value,
        "n_patterns": int(n_patterns),
    }
    return result, summary


def _weighted_twfe_slope(
    values: np.ndarray,
    exposure: np.ndarray,
    counts: np.ndarray,
) -> np.ndarray:
    total_clusters = counts.sum(axis=1).astype(float)
    exposure_cluster_mean = exposure.mean(axis=1)
    outcome_cluster_mean = values.mean(axis=1)
    exposure_year_mean = (counts @ exposure) / total_clusters[:, None]
    outcome_year_mean = (counts @ values) / total_clusters[:, None]
    exposure_overall = (counts @ exposure_cluster_mean) / total_clusters
    outcome_overall = (counts @ outcome_cluster_mean) / total_clusters
    exposure_tilde = (
        exposure[None, :, :]
        - exposure_cluster_mean[None, :, None]
        - exposure_year_mean[:, None, :]
        + exposure_overall[:, None, None]
    )
    outcome_tilde = (
        values[None, :, :]
        - outcome_cluster_mean[None, :, None]
        - outcome_year_mean[:, None, :]
        + outcome_overall[:, None, None]
    )
    weights = counts[:, :, None]
    numerator = np.sum(weights * exposure_tilde * outcome_tilde, axis=(1, 2))
    denominator = np.sum(weights * exposure_tilde ** 2, axis=(1, 2))
    return np.divide(
        numerator,
        denominator,
        out=np.full_like(numerator, np.nan),
        where=denominator > 0,
    )


def paired_cluster_bootstrap(
    base: pd.DataFrame,
    n_draws: int,
    seed: int,
) -> pd.DataFrame:
    weirs = sorted(base["weir_name"].astype(str).unique().tolist())
    years = sorted(base["year"].unique().tolist())
    g = len(weirs)
    if len(base) != g * len(years):
        raise ValueError("paired bootstrap requires a balanced weir-year panel")

    indexed = base.assign(weir_name=base["weir_name"].astype(str)).set_index(["weir_name", "year"])
    exposure = indexed["log1p_tau"].unstack("year").reindex(index=weirs, columns=years).to_numpy(float)
    cyano = indexed["z_cyano"].unstack("year").reindex(index=weirs, columns=years).to_numpy(float)
    chla = indexed["z_chlorophyll_a"].unstack("year").reindex(index=weirs, columns=years).to_numpy(float)
    if not np.isfinite(exposure).all() or not np.isfinite(cyano).all() or not np.isfinite(chla).all():
        raise ValueError("paired bootstrap arrays contain missing/nonfinite values")

    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, g, size=(n_draws, g), endpoint=False)
    counts = np.zeros((n_draws, g), dtype=np.int16)
    np.add.at(counts, (np.repeat(np.arange(n_draws), g), sampled.ravel()), 1)
    beta_cyano = _weighted_twfe_slope(cyano, exposure, counts)
    beta_chla = _weighted_twfe_slope(chla, exposure, counts)
    difference = beta_cyano - beta_chla
    finite = np.isfinite(beta_cyano) & np.isfinite(beta_chla) & np.isfinite(difference)

    multiplicities = []
    multiplicity_hashes = []
    for row in counts:
        text = ";".join(f"{weir}:{int(count)}" for weir, count in zip(weirs, row) if count)
        multiplicities.append(text)
        multiplicity_hashes.append(hashlib.sha256(row.tobytes()).hexdigest())
    return pd.DataFrame({
        "draw_id": np.arange(n_draws, dtype=int),
        "selected_cluster_multiplicities": multiplicities,
        "selected_cluster_hash": multiplicity_hashes,
        "beta_cyano_star": beta_cyano,
        "beta_chlorophyll_star": beta_chla,
        "difference_star": difference,
        "finite": finite,
    })


def holm_adjust(p_values: list[float]) -> list[float]:
    values = np.asarray(p_values, dtype=float)
    order = np.argsort(values)
    adjusted_sorted = np.maximum.accumulate((len(values) - np.arange(len(values))) * values[order])
    adjusted_sorted = np.minimum(adjusted_sorted, 1.0)
    adjusted = np.empty_like(values)
    adjusted[order] = adjusted_sorted
    return [float(value) for value in adjusted]
