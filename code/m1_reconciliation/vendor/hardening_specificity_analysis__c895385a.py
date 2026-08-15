#!/usr/bin/env python3
"""Standardized tau-specificity checks for the HAB EI hardening pass."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BASE = Path(os.environ.get("P2A_SOURCE_ROOT", str(REPOSITORY_ROOT / "raw")))
WORK = Path(os.environ.get("P2A_WORK", str(REPOSITORY_ROOT / "reproduction_output/P2a_legacy")))
PANEL = Path(os.environ.get("P2A_PANEL", str(REPOSITORY_ROOT / "data/insitu_annual_analysis_panel.csv")))
OUT = WORK / "01_models"
FIG = WORK / "03_manuscript/figures"
TABLES = WORK / "03_manuscript/tables"
LOG = WORK / "log"

SEED = 20260630
N_PERM = 4999

OUTCOME_COLS = {
    "cyano": "log1p_harmful_cyanobacteria_total_mean",
    "chlorophyll_a": "log1p_chlorophyll_a_mean",
}
OUTCOME_LABELS = {
    "cyano": "Harmful cyanobacteria (log1p mean)",
    "chlorophyll_a": "Chlorophyll-a (log1p mean)",
}
SEASON_LABELS = {
    "annual_all_samples": "Annual",
    "bloom_season_06_10": "Bloom season (Jun-Oct)",
}


@dataclass
class Fit:
    beta: float
    se_cluster: float
    ci_low: float
    ci_high: float
    p_cluster_two_sided: float
    n: int
    n_weirs: int
    n_years: int
    df_resid: int
    coef_names: list[str]
    coef: np.ndarray
    x: np.ndarray
    resid: np.ndarray


def ensure_dirs() -> None:
    for d in [OUT, FIG, TABLES, LOG]:
        d.mkdir(parents=True, exist_ok=True)


def stable_seed(*parts: object) -> int:
    text = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return SEED + (int(digest[:8], 16) % 100000)


def dummy_matrix(values: pd.Series, prefix: str) -> tuple[np.ndarray, list[str]]:
    vals = values.astype(str)
    levels = sorted(vals.dropna().unique().tolist())
    cols = []
    names = []
    for level in levels[1:]:
        cols.append((vals == level).astype(float).to_numpy())
        names.append(f"{prefix}[{level}]")
    if not cols:
        return np.empty((len(vals), 0)), []
    return np.column_stack(cols), names


def design_matrix(df: pd.DataFrame, main_cols: list[str], fe_cols: list[str]) -> tuple[np.ndarray, list[str]]:
    parts = [np.ones((len(df), 1))]
    names = ["intercept"]
    for col in main_cols:
        parts.append(df[col].astype(float).to_numpy().reshape(-1, 1))
        names.append(col)
    for col in fe_cols:
        mat, mat_names = dummy_matrix(df[col], col)
        if mat.shape[1]:
            parts.append(mat)
            names.extend(mat_names)
    return np.column_stack(parts), names


def cluster_se(x: np.ndarray, resid: np.ndarray, clusters: pd.Series) -> np.ndarray:
    xtx_inv = np.linalg.pinv(x.T @ x)
    meat = np.zeros((x.shape[1], x.shape[1]))
    for _, idx in pd.Series(np.arange(len(clusters))).groupby(clusters.astype(str)).groups.items():
        ix = np.array(list(idx), dtype=int)
        xg = x[ix, :]
        eg = resid[ix].reshape(-1, 1)
        meat += xg.T @ eg @ eg.T @ xg
    g = clusters.astype(str).nunique()
    n, k = x.shape
    correction = 1.0
    if g > 1 and n > k:
        correction = (g / (g - 1)) * ((n - 1) / (n - k))
    cov = correction * xtx_inv @ meat @ xtx_inv
    return np.sqrt(np.maximum(np.diag(cov), 0.0))


def ols_fit(
    df: pd.DataFrame,
    y_col: str,
    main_cols: list[str],
    fe_cols: list[str],
    beta_col: str,
    cluster_col: str = "weir_name",
) -> Fit:
    x, names = design_matrix(df, main_cols, fe_cols)
    y = df[y_col].astype(float).to_numpy()
    coef = np.linalg.lstsq(x, y, rcond=None)[0]
    resid = y - x @ coef
    beta_ix = names.index(beta_col)
    se = cluster_se(x, resid, df[cluster_col])
    beta = float(coef[beta_ix])
    se_beta = float(se[beta_ix])
    df_resid = max(df[cluster_col].astype(str).nunique() - 1, 1)
    tcrit = float(stats.t.ppf(0.975, df_resid))
    tval = beta / se_beta if se_beta > 0 else np.nan
    pval = float(2 * stats.t.sf(abs(tval), df_resid)) if se_beta > 0 else np.nan
    return Fit(
        beta=beta,
        se_cluster=se_beta,
        ci_low=beta - tcrit * se_beta if se_beta > 0 else np.nan,
        ci_high=beta + tcrit * se_beta if se_beta > 0 else np.nan,
        p_cluster_two_sided=pval,
        n=int(len(df)),
        n_weirs=int(df["weir_name"].astype(str).nunique()),
        n_years=int(df["year"].nunique()),
        df_resid=int(len(df) - np.linalg.matrix_rank(x)),
        coef_names=names,
        coef=coef,
        x=x,
        resid=resid,
    )


def zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=1)
    if sd == 0 or pd.isna(sd):
        return pd.Series(np.nan, index=s.index)
    return (s - s.mean()) / sd


def journal_p(p_value: float) -> str:
    if p_value < 0.001:
        return "p < 0.001"
    return f"p={p_value:.3f}"


def one_outcome_frame(panel: pd.DataFrame, season: str, outcome_key: str, standardized: bool) -> pd.DataFrame:
    col = OUTCOME_COLS[outcome_key]
    df = panel.loc[panel["season_scope"] == season, ["weir_name", "year", "river", "tau_days", col]].copy()
    df = df.dropna(subset=["tau_days", col, "weir_name", "year"]).copy()
    df["log1p_tau"] = np.log1p(df["tau_days"].astype(float))
    df["basin_year"] = df["river"].astype(str) + "::" + df["year"].astype(str)
    df["outcome_value"] = zscore(df[col]) if standardized else df[col].astype(float)
    df = df.dropna(subset=["outcome_value"]).copy()
    return df


def single_outcome_beta(panel: pd.DataFrame, season: str, outcome_key: str, standardized: bool, basin_year: bool = False) -> Fit:
    df = one_outcome_frame(panel, season, outcome_key, standardized)
    fe_cols = ["weir_name", "basin_year"] if basin_year else ["weir_name", "year"]
    return ols_fit(df, "outcome_value", ["log1p_tau"], fe_cols, "log1p_tau")


def single_outcome_ri(panel: pd.DataFrame, season: str, outcome_key: str, standardized: bool, basin_year: bool = False) -> tuple[float, int]:
    rng = np.random.default_rng(stable_seed("single_ri", season, outcome_key, standardized, basin_year))
    obs = single_outcome_beta(panel, season, outcome_key, standardized, basin_year).beta
    vals = []
    sub = panel.loc[panel["season_scope"] == season].copy()
    for _ in range(N_PERM):
        perm = sub.copy()
        perm["tau_days"] = perm.groupby("year")["tau_days"].transform(lambda x: rng.permutation(x.to_numpy()))
        vals.append(single_outcome_beta(perm, season, outcome_key, standardized, basin_year).beta)
    arr = np.array(vals, dtype=float)
    return float((np.sum(arr >= obs) + 1) / (len(arr) + 1)), int(len(arr))


def single_outcome_wild_ci(
    panel: pd.DataFrame,
    season: str,
    outcome_key: str,
    standardized: bool,
    basin_year: bool = False,
) -> tuple[float, float, float, int]:
    rng = np.random.default_rng(stable_seed("single_wild", season, outcome_key, standardized, basin_year))
    df = one_outcome_frame(panel, season, outcome_key, standardized)
    fe_cols = ["weir_name", "basin_year"] if basin_year else ["weir_name", "year"]
    fit = ols_fit(df, "outcome_value", ["log1p_tau"], fe_cols, "log1p_tau")
    yhat = fit.x @ fit.coef
    boot = []
    weirs = sorted(df["weir_name"].astype(str).unique().tolist())
    for _ in range(N_PERM):
        signs = {w: rng.choice([-1.0, 1.0]) for w in weirs}
        df_star = df.copy()
        df_star["outcome_value"] = yhat + df["weir_name"].astype(str).map(signs).to_numpy() * fit.resid
        boot.append(ols_fit(df_star, "outcome_value", ["log1p_tau"], fe_cols, "log1p_tau").beta)
    arr = np.array(boot, dtype=float)
    low, high = np.quantile(arr, [0.025, 0.975])
    p_le_0 = float((np.sum(arr <= 0) + 1) / (len(arr) + 1))
    return float(low), float(high), p_le_0, int(len(arr))


def stacked_frame(panel: pd.DataFrame, season: str) -> pd.DataFrame:
    base_cols = ["weir_name", "year", "river", "tau_days"] + list(OUTCOME_COLS.values())
    base = panel.loc[panel["season_scope"] == season, base_cols].dropna().copy()
    frames = []
    for outcome_key, col in OUTCOME_COLS.items():
        d = base[["weir_name", "year", "river", "tau_days", col]].copy()
        d["outcome_type"] = outcome_key
        d["outcome_is_cyano"] = 1.0 if outcome_key == "cyano" else 0.0
        d["outcome_std"] = zscore(d[col])
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df["log1p_tau"] = np.log1p(df["tau_days"].astype(float))
    df["log1p_tau_x_cyano"] = df["log1p_tau"] * df["outcome_is_cyano"]
    df["stack_cluster"] = df["weir_name"].astype(str)
    return df.dropna(subset=["outcome_std", "log1p_tau"]).copy()


def stacked_interaction(panel: pd.DataFrame, season: str) -> Fit:
    df = stacked_frame(panel, season)
    return ols_fit(
        df,
        "outcome_std",
        ["log1p_tau", "outcome_is_cyano", "log1p_tau_x_cyano"],
        ["weir_name", "year"],
        "log1p_tau_x_cyano",
        cluster_col="stack_cluster",
    )


def stacked_interaction_ri(panel: pd.DataFrame, season: str) -> tuple[float, int]:
    rng = np.random.default_rng(stable_seed("stack_ri", season))
    obs = stacked_interaction(panel, season).beta
    vals = []
    sub = panel.loc[panel["season_scope"] == season].copy()
    for _ in range(N_PERM):
        perm = sub.copy()
        perm["tau_days"] = perm.groupby("year")["tau_days"].transform(lambda x: rng.permutation(x.to_numpy()))
        vals.append(stacked_interaction(perm, season).beta)
    arr = np.array(vals, dtype=float)
    return float((np.sum(arr >= obs) + 1) / (len(arr) + 1)), int(len(arr))


def make_model_outputs(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    model_rows = []
    for season in SEASON_LABELS:
        for outcome_key in ["cyano", "chlorophyll_a"]:
            for standardized, family in [(True, "z_standardized_log1p_outcome"), (False, "both_log_raw_log1p_outcome")]:
                fit = single_outcome_beta(panel, season, outcome_key, standardized)
                ri_p, n_perm = single_outcome_ri(panel, season, outcome_key, standardized)
                wild_low, wild_high, wild_p_le_0, n_boot = single_outcome_wild_ci(panel, season, outcome_key, standardized)
                model_rows.append(
                    {
                        "model_family": family,
                        "season_scope": season,
                        "season_label": SEASON_LABELS[season],
                        "outcome": outcome_key,
                        "outcome_label": OUTCOME_LABELS[outcome_key],
                        "beta_log1p_tau": fit.beta,
                        "cluster_se": fit.se_cluster,
                        "cluster_ci_low": fit.ci_low,
                        "cluster_ci_high": fit.ci_high,
                        "cluster_p_two_sided": fit.p_cluster_two_sided,
                        "secondary_ci_method": "weir wild bootstrap",
                        "secondary_ci_low": wild_low,
                        "secondary_ci_high": wild_high,
                        "wild_p_beta_le_0": wild_p_le_0,
                        "n_bootstrap": n_boot,
                        "ri_p_right_positive_tau": ri_p,
                        "n_permutations": n_perm,
                        "n": fit.n,
                        "n_weirs": fit.n_weirs,
                        "n_years": fit.n_years,
                        "fixed_effects": "weir + year",
                        "cluster": "weir",
                    }
                )
            if outcome_key == "cyano":
                fit = single_outcome_beta(panel, season, outcome_key, standardized=True, basin_year=True)
                ri_p, n_perm = single_outcome_ri(panel, season, outcome_key, standardized=True, basin_year=True)
                wild_low, wild_high, wild_p_le_0, n_boot = single_outcome_wild_ci(panel, season, outcome_key, standardized=True, basin_year=True)
                model_rows.append(
                    {
                        "model_family": "z_standardized_log1p_outcome_basin_year_robustness",
                        "season_scope": season,
                        "season_label": SEASON_LABELS[season],
                        "outcome": outcome_key,
                        "outcome_label": OUTCOME_LABELS[outcome_key],
                        "beta_log1p_tau": fit.beta,
                        "cluster_se": fit.se_cluster,
                        "cluster_ci_low": fit.ci_low,
                        "cluster_ci_high": fit.ci_high,
                        "cluster_p_two_sided": fit.p_cluster_two_sided,
                        "secondary_ci_method": "weir wild bootstrap",
                        "secondary_ci_low": wild_low,
                        "secondary_ci_high": wild_high,
                        "wild_p_beta_le_0": wild_p_le_0,
                        "n_bootstrap": n_boot,
                        "ri_p_right_positive_tau": ri_p,
                        "n_permutations": n_perm,
                        "n": fit.n,
                        "n_weirs": fit.n_weirs,
                        "n_years": fit.n_years,
                        "fixed_effects": "weir + basin-by-year",
                        "cluster": "weir",
                    }
                )
    interaction_rows = []
    for season in SEASON_LABELS:
        fit = stacked_interaction(panel, season)
        ri_p, n_perm = stacked_interaction_ri(panel, season)
        interaction_rows.append(
            {
                "season_scope": season,
                "season_label": SEASON_LABELS[season],
                "test": "stacked_standardized_outcome_log1p_tau_x_cyano",
                "interaction_beta_cyano_minus_chla": fit.beta,
                "cluster_se": fit.se_cluster,
                "cluster_ci_low": fit.ci_low,
                "cluster_ci_high": fit.ci_high,
                "cluster_p_two_sided": fit.p_cluster_two_sided,
                "ri_p_right_cyano_gt_chla": ri_p,
                "n_permutations": n_perm,
                "n_stacked": fit.n,
                "n_original_weir_years": int(fit.n / 2),
                "n_weirs": fit.n_weirs,
                "n_years": fit.n_years,
                "fixed_effects": "weir + year",
                "cluster": "weir",
            }
        )
    return pd.DataFrame(model_rows), pd.DataFrame(interaction_rows)


def write_outcome_scales(panel: pd.DataFrame) -> None:
    counts = (
        panel.groupby("season_scope")[["log1p_harmful_cyanobacteria_total_mean", "log1p_chlorophyll_a_mean", "tau_days"]]
        .count()
        .rename(columns={
            "log1p_harmful_cyanobacteria_total_mean": "cyano_log1p_n",
            "log1p_chlorophyll_a_mean": "chlorophyll_log1p_n",
            "tau_days": "tau_n",
        })
    )
    text = f"""# Outcome Scales and Comparability Check

## Current transformations confirmed

The existing Round 6 in-situ tau regressions use annual and bloom-season weir-year panels from:

`{PANEL}`

The panel contains two season scopes:

{counts.to_markdown()}

| outcome | source raw unit | current analysis column | transformation in current model | cross-outcome magnitude comparable before standardization? |
|---|---:|---|---|---|
| harmful cyanobacteria | data.go.kr field unit `Cells/100mL` in the raw panel | `log1p_harmful_cyanobacteria_total_mean` | `log1p(mean harmful_cyanobacteria_total)` within weir-year-season | No. The coefficient is in log cells per unit log residence time. |
| chlorophyll-a | data.go.kr field unit `mg/m3` in the raw panel | `log1p_chlorophyll_a_mean` | `log1p(mean chlorophyll_a)` within weir-year-season | No. The coefficient is in log chlorophyll-a concentration per unit log residence time. |

## Consequence for the headline comparison

The earlier coefficients, including the large harmful-cyanobacteria coefficient and the much smaller chlorophyll-a coefficient, are both log-outcome estimates but are not on a common outcome scale. They are valid within-outcome tau associations, but their raw magnitudes should not be interpreted as a scale-free specificity contrast.

The hardening analysis therefore uses `z_standardized_log1p_outcome` as the primary comparison: each outcome is z-scored within the exact estimation sample for its season scope. The both-log raw-outcome estimates are retained as a robustness description, not as the primary cross-outcome magnitude comparison.

## Precommitted reading rule

The manuscript language should be upgraded only if the stacked standardized interaction supports harmful cyanobacteria responding more strongly than chlorophyll-a. If the interaction is not positive and statistically supported by the randomization test, the headline should be downgraded to a standardized contrast that is descriptive or not statistically distinguishable, depending on the result.
"""
    (OUT / "outcome_scales.md").write_text(text, encoding="utf-8")


def write_interaction_report(models: pd.DataFrame, inter: pd.DataFrame) -> None:
    primary = models[models["model_family"] == "z_standardized_log1p_outcome"].copy()
    primary_display = primary.copy()
    primary_display["ri_p_right_positive_tau"] = primary_display["ri_p_right_positive_tau"].map(journal_p)
    inter_display = inter.copy()
    inter_display["ri_p_right_cyano_gt_chla"] = inter_display["ri_p_right_cyano_gt_chla"].map(journal_p)
    lines = [
        "# Standardized Tau Specificity Interaction",
        "",
        "Primary outcome scaling: z-scored log1p outcome within each season-specific estimation sample.",
        "Primary inference: randomization p-value from permuting residence time within year. Secondary intervals are weir wild-bootstrap CIs for single-outcome slopes and weir-clustered CIs for stacked interactions.",
        "",
        "## Standardized single-outcome tau slopes",
        "",
        primary_display[
            [
                "season_label",
                "outcome",
                "beta_log1p_tau",
                "secondary_ci_low",
                "secondary_ci_high",
                "ri_p_right_positive_tau",
                "n",
            ]
        ].to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Formal stacked interaction",
        "",
        inter_display[
            [
                "season_label",
                "interaction_beta_cyano_minus_chla",
                "cluster_ci_low",
                "cluster_ci_high",
                "ri_p_right_cyano_gt_chla",
                "n_original_weir_years",
            ]
        ].to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Precommitted interpretation",
        "",
    ]
    annual = inter.loc[inter["season_scope"] == "annual_all_samples"].iloc[0]
    bloom = inter.loc[inter["season_scope"] == "bloom_season_06_10"].iloc[0]
    if annual["interaction_beta_cyano_minus_chla"] > 0 and annual["ri_p_right_cyano_gt_chla"] <= 0.05:
        reading = (
            "The annual standardized interaction supports stronger tau sensitivity for harmful cyanobacteria than for "
            "chlorophyll-a. Manuscript language can describe this as a scale-valid specificity contrast, while still "
            "reporting the bloom-season result separately."
        )
    elif bloom["interaction_beta_cyano_minus_chla"] > 0 and bloom["ri_p_right_cyano_gt_chla"] <= 0.05:
        reading = (
            "The bloom-season standardized interaction supports stronger tau sensitivity for harmful cyanobacteria than "
            "for chlorophyll-a, but the annual contrast should not be overstated unless it also passes."
        )
    else:
        reading = (
            "The stacked standardized interaction does not provide a primary randomization-supported basis for claiming "
            "that harmful cyanobacteria are more tau-sensitive than chlorophyll-a. The manuscript should downgrade the "
            "headline from a magnitude comparison of raw coefficients to an outcome-specific tau association with an "
            "explicit standardized contrast."
        )
    lines.extend([reading, "", "## Robustness note", ""])
    robust = models[models["model_family"] == "z_standardized_log1p_outcome_basin_year_robustness"]
    lines.append(
        "Cyano-only basin-by-year robustness estimates are included in `standardized_tau_models.csv`; they add basin-year "
        "fixed effects in place of common year fixed effects while retaining weir fixed effects."
    )
    lines.append("")
    robust_display = robust.copy()
    robust_display["ri_p_right_positive_tau"] = robust_display["ri_p_right_positive_tau"].map(journal_p)
    lines.append(robust_display[["season_label", "beta_log1p_tau", "secondary_ci_low", "secondary_ci_high", "ri_p_right_positive_tau", "n"]].to_markdown(index=False, floatfmt=".4f"))
    lines.append("")
    (OUT / "specificity_interaction.md").write_text("\n".join(lines), encoding="utf-8")


def write_figure(models: pd.DataFrame, inter: pd.DataFrame) -> None:
    primary = models[models["model_family"] == "z_standardized_log1p_outcome"].copy()
    season_short = {
        "annual_all_samples": "Annual",
        "bloom_season_06_10": "Bloom",
    }
    outcome_short = {"cyano": "cyanobacteria", "chlorophyll_a": "Chl-a"}
    primary["label"] = primary["season_scope"].map(season_short) + " " + primary["outcome"].map(outcome_short)
    primary = primary.sort_values(["season_scope", "outcome"], ascending=[True, False])
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    y = np.arange(len(primary))
    colors = primary["outcome"].map({"cyano": "#0072B2", "chlorophyll_a": "#D55E00"}).to_list()
    ax.errorbar(
        primary["beta_log1p_tau"],
        y,
        xerr=[
            primary["beta_log1p_tau"] - primary["secondary_ci_low"],
            primary["secondary_ci_high"] - primary["beta_log1p_tau"],
        ],
        fmt="none",
        ecolor="#333333",
        capsize=3,
        lw=1.4,
        zorder=1,
    )
    ax.scatter(primary["beta_log1p_tau"], y, c=colors, s=72, zorder=2)
    ax.axvline(0, color="#777777", lw=1, ls="--")
    ax.set_yticks(y)
    ax.set_yticklabels(primary["label"])
    ax.set_xlabel("Standardized outcome slope per log1p residence time")
    ax.set_title("Scale-valid tau specificity contrast")
    ax.grid(axis="x", alpha=0.25)
    note = []
    for _, row in inter.iterrows():
        note.append(
            f"{row['season_label']}: interaction={row['interaction_beta_cyano_minus_chla']:.2f}, "
            f"RI {journal_p(row['ri_p_right_cyano_gt_chla'])}"
        )
    fig.subplots_adjust(left=0.30, right=0.96, top=0.84, bottom=0.30)
    fig.text(
        0.5,
        0.08,
        "Stacked standardized interaction:\n" + "\n".join(note),
        ha="center",
        va="bottom",
        fontsize=8.3,
    )
    for path in [FIG / "figure4_tau_specificity.svg", FIG / "figure4_tau_specificity.png"]:
        fig.savefig(path, dpi=300)
    plt.close(fig)


def main() -> None:
    ensure_dirs()
    panel = pd.read_csv(PANEL)
    for col in ["year", "tau_days", *OUTCOME_COLS.values()]:
        panel[col] = pd.to_numeric(panel[col], errors="coerce")
    write_outcome_scales(panel)
    models, inter = make_model_outputs(panel)
    models.to_csv(OUT / "standardized_tau_models.csv", index=False)
    inter.to_csv(OUT / "specificity_interaction.csv", index=False)
    write_interaction_report(models, inter)
    write_figure(models, inter)
    (TABLES / "table_specificity_standardized_tau.csv").write_text(
        models[models["model_family"].str.startswith("z_standardized")]
        .to_csv(index=False),
        encoding="utf-8",
    )
    print(f"Wrote {OUT / 'outcome_scales.md'}")
    print(f"Wrote {OUT / 'standardized_tau_models.csv'} ({len(models)} rows)")
    print(f"Wrote {OUT / 'specificity_interaction.md'}")
    print(f"Wrote {FIG / 'figure4_tau_specificity.svg'}")


if __name__ == "__main__":
    main()
