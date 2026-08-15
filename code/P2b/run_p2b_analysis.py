#!/usr/bin/env python3
"""P2b — reproduction gate, hydrologic robustness (M02f/g), basin inference (M06).

Specifications are fixed by 03_analysis/frozen_protocols/P2b_freeze.md sections 6-8.
No specification outside that list is fitted.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BASE = Path(os.environ.get("P2B_SOURCE_ROOT", str(REPOSITORY_ROOT / "raw")))
CODE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("P2B_OUT", str(REPOSITORY_ROOT / "reproduction_output/P2b")))
OUT.mkdir(parents=True, exist_ok=True)

PANEL = BASE / "Round_6/02_analysis/proxy_validation/insitu_annual_analysis_panel.csv"
COV = OUT / "covariate_panel.csv"
TARGETS_SLOPES = BASE / "manuscript_EI_hardening/01_models/standardized_tau_models.csv"
TARGETS_INTER = BASE / "manuscript_EI_hardening/01_models/specificity_interaction.csv"
TARGETS_BY = BASE / "manuscript_EI_terminal/01_models/interaction_basinyear.csv"

spec = importlib.util.spec_from_file_location("m", CODE / "vendored_specificity_model.py")
M = importlib.util.module_from_spec(spec)
sys.modules["m"] = M
spec.loader.exec_module(M)

SEED, N_PERM = M.SEED, M.N_PERM
SEASONS = ["annual_all_samples", "bloom_season_06_10"]
log: list[dict] = []


def note(step: str, **kw):
    rec = {"step": step, **kw}
    log.append(rec)
    print(json.dumps(rec, ensure_ascii=False, default=float))


# ---------------------------------------------------------------- reproduction
def reproduction_gate(panel: pd.DataFrame) -> bool:
    tol = 1e-9
    sl = pd.read_csv(TARGETS_SLOPES)
    it = pd.read_csv(TARGETS_INTER)
    ok = True
    for season in SEASONS:
        f = M.stacked_interaction(panel, season)
        tgt = float(it.loc[it.season_scope == season, "interaction_beta_cyano_minus_chla"].iloc[0])
        good = abs(f.beta - tgt) < tol
        ok &= good
        note("repro_stacked", season=season, got=f.beta, target=tgt,
             abs_err=abs(f.beta - tgt), pass_=bool(good), n=f.n)
        for oc in ["cyano", "chlorophyll_a"]:
            fit = M.single_outcome_beta(panel, season, oc, standardized=True)
            t = sl[(sl.season_scope == season) & (sl.outcome == oc) &
                   (sl.model_family == "z_standardized_log1p_outcome")]
            tgt2 = float(t.beta_log1p_tau.iloc[0])
            g2 = abs(fit.beta - tgt2) < tol
            ok &= g2
            note("repro_slope", season=season, outcome=oc, got=fit.beta, target=tgt2,
                 abs_err=abs(fit.beta - tgt2), pass_=bool(g2), n=fit.n)
    return ok


# ------------------------------------------------------- adjusted stacked frame
def adjusted_frame(cov: pd.DataFrame, season: str, keep_robust_only: bool = False) -> pd.DataFrame:
    c = cov[cov.season_scope == season].copy()
    if keep_robust_only:
        c = c[c.tau_robustness_flag == "robust_candidate_no_low_flow_flag"].copy()
    base = c[["weir_name", "year", "river", "tau_days", "log_storage", "log_discharge",
              "water_level_m", "rainfall_mm", "water_temp_c",
              "harmful_cyanobacteria_total_log1p_mean", "chlorophyll_a_log1p_mean"]].dropna()
    frames = []
    for key, col in [("cyano", "harmful_cyanobacteria_total_log1p_mean"),
                     ("chlorophyll_a", "chlorophyll_a_log1p_mean")]:
        d = base.copy()
        d["outcome_type"] = key
        d["outcome_is_cyano"] = 1.0 if key == "cyano" else 0.0
        d["outcome_std"] = M.zscore(d[col])
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df["log1p_tau"] = np.log1p(df.tau_days.astype(float))
    df["basin_year"] = df.river.astype(str) + "::" + df.year.astype(str)
    df["stack_cluster"] = df.weir_name.astype(str)
    for v in ["log1p_tau", "log_storage", "log_discharge", "water_level_m",
              "rainfall_mm", "water_temp_c"]:
        df[v + "_z"] = M.zscore(df[v])
        df[v + "_x_cyano"] = df[v + "_z"] * df.outcome_is_cyano
    return df.dropna(subset=["outcome_std"]).copy()


def vif(fit, name: str) -> float:
    """Variance inflation for one design column, against all others."""
    names, x = fit.coef_names, fit.x
    j = names.index(name)
    other = np.delete(x, j, axis=1)
    tgt = x[:, j]
    coef = np.linalg.lstsq(other, tgt, rcond=None)[0]
    r = tgt - other @ coef
    ss_tot = float(((tgt - tgt.mean()) ** 2).sum())
    if ss_tot <= 0:
        return float("nan")
    r2 = 1.0 - float((r ** 2).sum()) / ss_tot
    return float("inf") if r2 >= 1 - 1e-12 else 1.0 / (1.0 - r2)


def ri_pvalue(cov, season, main_cols, fe_cols, target, blocks, robust_only=False, tag=""):
    """Permute tau_days within `blocks` at weir-year level; covariates held fixed."""
    rng = np.random.default_rng(M.stable_seed("p2b_ri", season, target, blocks, tag))
    df0 = adjusted_frame(cov, season, robust_only)
    obs = M.ols_fit(df0, "outcome_std", main_cols, fe_cols, target, cluster_col="stack_cluster").beta
    c = cov[cov.season_scope == season].copy()
    if robust_only:
        c = c[c.tau_robustness_flag == "robust_candidate_no_low_flow_flag"].copy()
    c["_blk"] = c.year.astype(str) if blocks == "year" else c.river.astype(str) + "::" + c.year.astype(str)
    ge = 0
    for _ in range(N_PERM):
        p = c.copy()
        p["tau_days"] = p.groupby("_blk")["tau_days"].transform(lambda x: rng.permutation(x.to_numpy()))
        d = adjusted_frame(p.drop(columns="_blk"), season, robust_only)
        b = M.ols_fit(d, "outcome_std", main_cols, fe_cols, target, cluster_col="stack_cluster").beta
        if b >= obs:
            ge += 1
    return float((ge + 1) / (N_PERM + 1)), obs


def fit_spec(cov, season, spec_id, main_cols, fe_cols, target, robust_only=False,
             ri_blocks: str | None = None) -> dict:
    df = adjusted_frame(cov, season, robust_only)
    f = M.ols_fit(df, "outcome_std", main_cols, fe_cols, target, cluster_col="stack_cluster")
    row = {"spec": spec_id, "season_scope": season, "target": target,
           "beta": f.beta, "cluster_se": f.se_cluster, "ci_low": f.ci_low, "ci_high": f.ci_high,
           "cluster_p_two_sided": f.p_cluster_two_sided, "n_stacked": f.n,
           "n_weir_years": f.n // 2, "n_weirs": f.n_weirs, "n_years": f.n_years,
           "df_resid": f.df_resid, "fixed_effects": "+".join(fe_cols),
           "terms": "|".join(main_cols), "vif_target": vif(f, target),
           "ci_excludes_zero": bool(f.ci_low > 0 or f.ci_high < 0)}
    if ri_blocks:
        p, obs = ri_pvalue(cov, season, main_cols, fe_cols, target, ri_blocks,
                           robust_only, tag=spec_id)
        row["ri_p_right"] = p
        row["ri_blocks"] = ri_blocks
        row["n_permutations"] = N_PERM
        assert abs(obs - f.beta) < 1e-12
    note("spec_fitted", **{k: row[k] for k in
         ("spec", "season_scope", "beta", "ci_low", "ci_high", "cluster_p_two_sided",
          "n_stacked", "vif_target")}, ri_p=row.get("ri_p_right"))
    return row


def main() -> None:
    panel = pd.read_csv(PANEL)
    cov = pd.read_csv(COV)

    note("gate_start", tol=1e-9)
    if not reproduction_gate(panel):
        note("HALT", reason="H1 reproduction gate failed")
        pd.DataFrame(log).to_json(OUT / "p2b_run_log.json", orient="records", indent=2)
        raise SystemExit("H1: reproduction gate failed")
    note("gate_passed", detail="all point estimates reproduced within 1e-9")

    # my adjusted frame must reproduce the baseline when unadjusted
    for season in SEASONS:
        d = adjusted_frame(cov, season)
        f = M.ols_fit(d, "outcome_std", ["log1p_tau", "outcome_is_cyano", "log1p_tau_x_cyano_raw"]
                      if False else ["log1p_tau", "outcome_is_cyano", "log1p_tau_x_cyano"],
                      ["weir_name", "year"], "log1p_tau_x_cyano", cluster_col="stack_cluster")
        v = M.stacked_interaction(panel, season)
        note("frame_consistency", season=season, mine_z_scaled=f.beta, vendored_unscaled=v.beta,
             note_="mine uses z-standardized tau so scale differs; sign/inference comparable")

    TAU = "log1p_tau_x_cyano"
    MAIN0 = ["log1p_tau_z", "outcome_is_cyano", TAU]
    FE = ["weir_name", "year"]
    rows = []

    # BASELINE on the P2b frame (z-scaled tau) for like-for-like comparison
    for season in SEASONS:
        rows.append(fit_spec(cov, season, "B0_baseline_zscaled", MAIN0, FE, TAU, ri_blocks="year"))

    # PRIMARY
    P = MAIN0 + ["log_discharge_z", "log_discharge_x_cyano", "water_temp_c_z", "water_temp_c_x_cyano"]
    rows.append(fit_spec(cov, "annual_all_samples", "P_primary", P, FE, TAU, ri_blocks="year"))
    # S7 = primary on bloom scope
    rows.append(fit_spec(cov, "bloom_season_06_10", "S7_primary_bloom", P, FE, TAU, ri_blocks="year"))
    # S1 add storage (expected near-singular)
    S1 = P + ["log_storage_z", "log_storage_x_cyano"]
    rows.append(fit_spec(cov, "annual_all_samples", "S1_plus_storage", S1, FE, TAU, ri_blocks="year"))
    # S2 decomposition: drop tau
    S2 = ["outcome_is_cyano", "log_storage_z", "log_storage_x_cyano",
          "log_discharge_z", "log_discharge_x_cyano"]
    for season in SEASONS:
        for tgt in ["log_storage_x_cyano", "log_discharge_x_cyano"]:
            rows.append(fit_spec(cov, season, f"S2_decomposition[{tgt}]", S2, FE, tgt))
    # S4 low-flow-flag-free subset
    rows.append(fit_spec(cov, "annual_all_samples", "S4_robust_subset", P, FE, TAU,
                         robust_only=True, ri_blocks="year"))
    # S5 water level instead of discharge
    S5 = MAIN0 + ["water_level_m_z", "water_level_m_x_cyano", "water_temp_c_z", "water_temp_c_x_cyano"]
    rows.append(fit_spec(cov, "annual_all_samples", "S5_water_level", S5, FE, TAU, ri_blocks="year"))
    # S6 add rainfall
    S6 = P + ["rainfall_mm_z", "rainfall_mm_x_cyano"]
    rows.append(fit_spec(cov, "annual_all_samples", "S6_plus_rainfall", S6, FE, TAU, ri_blocks="year"))

    est = pd.DataFrame(rows)
    est.to_csv(OUT / "M2_adjusted_estimates.csv", index=False)
    note("M2_written", rows=len(est))

    # ---- S3 per-endpoint adjusted slopes ----
    s3 = []
    for season in SEASONS:
        c = cov[cov.season_scope == season]
        for key, col in [("cyano", "harmful_cyanobacteria_total_log1p_mean"),
                         ("chlorophyll_a", "chlorophyll_a_log1p_mean")]:
            d = c[["weir_name", "year", "river", "tau_days", "log_discharge", "water_temp_c", col]].dropna().copy()
            d["outcome_std"] = M.zscore(d[col])
            d["log1p_tau_z"] = M.zscore(np.log1p(d.tau_days.astype(float)))
            d["log_discharge_z"] = M.zscore(d.log_discharge)
            d["water_temp_c_z"] = M.zscore(d.water_temp_c)
            for tag, mains in [("unadjusted", ["log1p_tau_z"]),
                               ("adjusted", ["log1p_tau_z", "log_discharge_z", "water_temp_c_z"])]:
                f = M.ols_fit(d, "outcome_std", mains, ["weir_name", "year"], "log1p_tau_z")
                s3.append({"spec": f"S3_{tag}", "season_scope": season, "outcome": key,
                           "beta_log1p_tau_z": f.beta, "cluster_se": f.se_cluster,
                           "ci_low": f.ci_low, "ci_high": f.ci_high,
                           "cluster_p_two_sided": f.p_cluster_two_sided, "n": f.n,
                           "vif_tau": vif(f, "log1p_tau_z")})
    pd.DataFrame(s3).to_csv(OUT / "M2_per_endpoint_slopes.csv", index=False)
    note("S3_written", rows=len(s3))

    # ---- M06 basin-preserving inference ----
    by = []
    tgt_by = pd.read_csv(TARGETS_BY)
    for season in SEASONS:
        for basin_year in [False, True]:
            f = M.stacked_interaction(panel, season, basin_year=basin_year)
            p, n = M.stacked_interaction_ri(panel, season, basin_year=basin_year)
            fe = "weir + basin-by-year" if basin_year else "weir + year"
            t = tgt_by[(tgt_by.season_scope == season) & (tgt_by.fixed_effects == fe)]
            tb = float(t.interaction_beta_cyano_minus_chla.iloc[0]) if len(t) else np.nan
            tp = float(t.ri_p_right_cyano_gt_chla.iloc[0]) if len(t) else np.nan
            by.append({"season_scope": season, "fixed_effects": fe,
                       "tau_permutation_blocks": "basin-by-year" if basin_year else "year",
                       "interaction_beta": f.beta, "cluster_se": f.se_cluster,
                       "ci_low": f.ci_low, "ci_high": f.ci_high,
                       "cluster_p_two_sided": f.p_cluster_two_sided,
                       "ri_p_right": p, "n_permutations": n, "n_stacked": f.n,
                       "target_beta": tb, "beta_abs_err": abs(f.beta - tb) if tb == tb else np.nan,
                       "target_ri_p": tp, "ri_p_abs_diff": abs(p - tp) if tp == tp else np.nan,
                       "ci_excludes_zero": bool(f.ci_low > 0)})
            note("M6_fit", season=season, fe=fe, beta=f.beta, ri_p=p,
                 target_beta=tb, beta_abs_err=abs(f.beta - tb) if tb == tb else None,
                 target_ri_p=tp)
    pd.DataFrame(by).to_csv(OUT / "M6_basin_inference.csv", index=False)

    bys = []
    for season in SEASONS:
        for oc in ["cyano", "chlorophyll_a"]:
            for basin_year in [False, True]:
                f = M.single_outcome_beta(panel, season, oc, standardized=True, basin_year=basin_year)
                rp, _ = M.single_outcome_ri(panel, season, oc, standardized=True, basin_year=basin_year)
                bys.append({"season_scope": season, "outcome": oc,
                            "fixed_effects": "weir + basin-by-year" if basin_year else "weir + year",
                            "beta": f.beta, "ci_low": f.ci_low, "ci_high": f.ci_high,
                            "cluster_p_two_sided": f.p_cluster_two_sided,
                            "ri_p_right": rp, "n": f.n})
                note("M6_slope", season=season, outcome=oc,
                     fe=bys[-1]["fixed_effects"], beta=f.beta, ri_p=rp)
    pd.DataFrame(bys).to_csv(OUT / "M6_per_outcome_slopes.csv", index=False)

    pd.DataFrame(log).to_json(OUT / "p2b_run_log.json", orient="records", indent=2)
    print("\nDONE")


if __name__ == "__main__":
    main()
