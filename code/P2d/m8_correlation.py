"""Paired dependent-correlation analysis with weir-cluster resampling."""

from __future__ import annotations

import hashlib
import itertools

import numpy as np
import pandas as pd
from scipy import stats


def paired_common_support(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.loc[:, columns].copy()
    numeric = [col for col in columns if col not in {"weir_name", "year"}]
    for col in numeric:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=columns).copy()
    finite = np.isfinite(out[numeric].to_numpy(float)).all(axis=1)
    return out.loc[finite].copy()


def _corr(x: np.ndarray, y: np.ndarray, method: str) -> float:
    if len(x) < 3 or np.nanstd(x) == 0 or np.nanstd(y) == 0:
        return np.nan
    if method == "spearman":
        return float(stats.spearmanr(x, y).statistic)
    if method == "pearson":
        return float(stats.pearsonr(x, y).statistic)
    raise ValueError(method)


def _correlation_row(frame: pd.DataFrame, x_col: str, cyano_col: str, chla_col: str, component: str) -> dict:
    x = frame[x_col].to_numpy(float)
    cyano = frame[cyano_col].to_numpy(float)
    chla = frame[chla_col].to_numpy(float)
    result = {"component": component, "n": int(len(frame))}
    for method in ["spearman", "pearson"]:
        rc = _corr(x, cyano, method)
        rh = _corr(x, chla, method)
        result[f"{method}_r_cyano"] = rc
        result[f"{method}_r_chla"] = rh
        result[f"{method}_delta_chla_minus_cyano"] = rh - rc
    return result


def within_between_correlations(
    frame: pd.DataFrame,
    x_col: str,
    cyano_col: str,
    chla_col: str,
    cluster_col: str,
) -> pd.DataFrame:
    pooled = _correlation_row(frame, x_col, cyano_col, chla_col, "pooled")
    within = frame[[cluster_col, x_col, cyano_col, chla_col]].copy()
    within[[x_col, cyano_col, chla_col]] = within[[x_col, cyano_col, chla_col]] - within.groupby(cluster_col)[[x_col, cyano_col, chla_col]].transform("mean")
    within_row = _correlation_row(within, x_col, cyano_col, chla_col, "within_weir")
    between = frame.groupby(cluster_col, as_index=False)[[x_col, cyano_col, chla_col]].mean()
    between_row = _correlation_row(between, x_col, cyano_col, chla_col, "between_weir")
    return pd.DataFrame([pooled, within_row, between_row])


def _spearman_delta(frame: pd.DataFrame, x_col: str, cyano_col: str, chla_col: str) -> tuple[float, float, float]:
    rc = _corr(frame[x_col].to_numpy(float), frame[cyano_col].to_numpy(float), "spearman")
    rh = _corr(frame[x_col].to_numpy(float), frame[chla_col].to_numpy(float), "spearman")
    return rc, rh, rh - rc


def _exact_sign_patterns(pseudo: np.ndarray) -> tuple[dict, pd.DataFrame]:
    g = len(pseudo)
    if g < 3 or not np.isfinite(pseudo).all() or np.std(pseudo, ddof=1) <= 0:
        raise ValueError("invalid jackknife pseudo-values")
    observed_se = float(np.std(pseudo, ddof=1) / np.sqrt(g))
    observed_t = float(np.mean(pseudo) / observed_se)
    rows: list[dict] = []
    extreme = 0
    for pattern_id, bits in enumerate(itertools.product([-1.0, 1.0], repeat=g)):
        signed = pseudo * np.asarray(bits)
        se = float(np.std(signed, ddof=1) / np.sqrt(g))
        finite = bool(np.isfinite(se) and se > 0)
        t_value = float(np.mean(signed) / se) if finite else np.nan
        if finite and abs(t_value) >= abs(observed_t) - 1e-15:
            extreme += 1
        rows.append(
            {
                "pattern_id": pattern_id,
                "sign_bits": "".join("1" if bit > 0 else "0" for bit in bits),
                "t_star": t_value,
                "se_star": se,
                "finite": finite,
            }
        )
    patterns = pd.DataFrame(rows)
    if not patterns["finite"].all():
        raise ValueError("nonfinite exact sign pattern")
    summary = {
        "jackknife_pseudo_mean": float(np.mean(pseudo)),
        "jackknife_se": observed_se,
        "jackknife_t": observed_t,
        "exact_p_two_sided": float(extreme / len(patterns)),
        "sign_patterns": int(len(patterns)),
    }
    return summary, patterns


def dependent_correlation_analysis(
    frame: pd.DataFrame,
    x_col: str,
    cyano_col: str,
    chla_col: str,
    cluster_col: str,
    bootstrap_draws: int,
    seed: int,
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    clusters = sorted(frame[cluster_col].astype(str).unique().tolist())
    g = len(clusters)
    rc, rh, observed = _spearman_delta(frame, x_col, cyano_col, chla_col)
    leave_one_out = []
    for cluster in clusters:
        subset = frame.loc[frame[cluster_col].astype(str) != cluster]
        leave_one_out.append(_spearman_delta(subset, x_col, cyano_col, chla_col)[2])
    pseudo = g * observed - (g - 1) * np.asarray(leave_one_out)
    sign_summary, patterns = _exact_sign_patterns(pseudo)

    rng = np.random.default_rng(seed)
    grouped = {cluster: frame.loc[frame[cluster_col].astype(str) == cluster].copy() for cluster in clusters}
    boot_rows: list[dict] = []
    for draw_id in range(bootstrap_draws):
        selected = rng.choice(clusters, size=g, replace=True)
        pieces = []
        for slot, cluster in enumerate(selected):
            piece = grouped[str(cluster)].copy()
            piece["_bootstrap_cluster"] = f"{slot}:{cluster}"
            pieces.append(piece)
        draw = pd.concat(pieces, ignore_index=True)
        bc, bh, bd = _spearman_delta(draw, x_col, cyano_col, chla_col)
        finite = bool(np.isfinite([bc, bh, bd]).all())
        boot_rows.append(
            {
                "draw_id": draw_id,
                "selected_cluster_hash": hashlib.sha256("|".join(map(str, selected)).encode()).hexdigest(),
                "spearman_r_cyano_star": bc,
                "spearman_r_chla_star": bh,
                "delta_star": bd,
                "finite": finite,
            }
        )
    bootstrap = pd.DataFrame(boot_rows)
    if len(bootstrap) != bootstrap_draws or not bootstrap["finite"].all():
        raise ValueError("nonfinite or missing paired cluster bootstrap draw")
    low, high = np.quantile(bootstrap["delta_star"].to_numpy(float), [0.025, 0.975])
    result = {
        "n": int(len(frame)),
        "n_weirs": g,
        "spearman_r_cyano": rc,
        "spearman_r_chla": rh,
        "spearman_delta_chla_minus_cyano": observed,
        "bootstrap_ci_low": float(low),
        "bootstrap_ci_high": float(high),
        "bootstrap_draws": int(bootstrap_draws),
        **sign_summary,
    }
    return result, patterns, bootstrap


def distribution_diagnostics(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows = []
    for column in columns:
        values = frame[column].to_numpy(float)
        shapiro = stats.shapiro(values)
        rows.append(
            {
                "variable": column,
                "n": len(values),
                "skewness": float(stats.skew(values, bias=False)),
                "shapiro_w": float(shapiro.statistic),
                "shapiro_p": float(shapiro.pvalue),
            }
        )
    return pd.DataFrame(rows)


def relationship_form_diagnostics(frame: pd.DataFrame, x_col: str, outcomes: list[str]) -> pd.DataFrame:
    """Describe linear versus quadratic fit without using it for primary selection."""
    x = frame[x_col].to_numpy(float)
    centered = x - np.mean(x)
    linear_x = np.column_stack([np.ones(len(x)), centered])
    quadratic_x = np.column_stack([np.ones(len(x)), centered, centered ** 2])
    rows = []
    for outcome in outcomes:
        y = frame[outcome].to_numpy(float)
        linear_beta = np.linalg.lstsq(linear_x, y, rcond=None)[0]
        quadratic_beta = np.linalg.lstsq(quadratic_x, y, rcond=None)[0]
        linear_sse = float(np.sum((y - linear_x @ linear_beta) ** 2))
        quadratic_sse = float(np.sum((y - quadratic_x @ quadratic_beta) ** 2))
        total = float(np.sum((y - np.mean(y)) ** 2))
        linear_r2 = 1 - linear_sse / total if total > 0 else np.nan
        quadratic_r2 = 1 - quadratic_sse / total if total > 0 else np.nan
        df_resid = len(y) - quadratic_x.shape[1]
        f_value = ((linear_sse - quadratic_sse) / 1) / (quadratic_sse / df_resid) if quadratic_sse > 0 and df_resid > 0 else np.nan
        p_value = float(stats.f.sf(f_value, 1, df_resid)) if np.isfinite(f_value) else np.nan
        rows.append(
            {
                "outcome": outcome,
                "n": len(y),
                "linear_r2": float(linear_r2),
                "quadratic_r2": float(quadratic_r2),
                "quadratic_incremental_f": float(f_value),
                "quadratic_incremental_p": p_value,
            }
        )
    return pd.DataFrame(rows)
