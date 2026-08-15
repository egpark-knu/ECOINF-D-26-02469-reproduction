#!/usr/bin/env python3
"""P2b — repair per-endpoint clustered SEs and document the submitted-code defect.

DEFECT (found in P2b, present in the submitted pipeline):
  vendored_specificity_model.cluster_se() computes
      pd.Series(np.arange(len(clusters))).groupby(clusters.astype(str))
  `pd.Series(np.arange(n))` carries a fresh RangeIndex 0..n-1 while `clusters`
  carries the CALLER's index. pandas groupby aligns on index. Any caller frame
  whose index is not 0..n-1 therefore yields empty cluster groups, the meat
  matrix stays zero, and the clustered SE is returned as exactly 0.0.

  `one_outcome_frame()` slices `panel.loc[panel.season_scope == season]`, so
  bloom-season frames carry index 144..287 and are hit; annual frames carry
  0..143 and are not. `stacked_frame()` uses pd.concat(..., ignore_index=True)
  and is not hit.

  Consequence in the submitted output standardized_tau_models.csv: every
  bloom-season per-endpoint row records cluster_se = 0.0 with blank CI and blank
  p-value. Point estimates are unaffected.

REPAIR: reset the frame index before fitting. The vendored module is left
byte-faithful (paths only) so the defect stays demonstrable.
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
PANEL = BASE / "Round_6/02_analysis/proxy_validation/insitu_annual_analysis_panel.csv"
SUBMITTED = BASE / "manuscript_EI_hardening/01_models/standardized_tau_models.csv"

spec = importlib.util.spec_from_file_location("m", CODE / "vendored_specificity_model.py")
M = importlib.util.module_from_spec(spec)
sys.modules["m"] = M
spec.loader.exec_module(M)

SEASONS = ["annual_all_samples", "bloom_season_06_10"]
log = []


def fit_both_ways(panel, season, outcome, basin_year=False):
    d = M.one_outcome_frame(panel, season, outcome, True)
    fe = ["weir_name", "basin_year"] if basin_year else ["weir_name", "year"]
    as_is = M.ols_fit(d, "outcome_value", ["log1p_tau"], fe, "log1p_tau")
    fixed = M.ols_fit(d.reset_index(drop=True), "outcome_value", ["log1p_tau"], fe, "log1p_tau")
    return d, as_is, fixed


def main() -> None:
    panel = pd.read_csv(PANEL)
    sub = pd.read_csv(SUBMITTED)
    sub = sub[sub.model_family == "z_standardized_log1p_outcome"]

    defect, repaired = [], []
    for season in SEASONS:
        for oc in ["cyano", "chlorophyll_a"]:
            for basin_year in [False, True]:
                d, a, f = fit_both_ways(panel, season, oc, basin_year)
                fe_label = "weir + basin-by-year" if basin_year else "weir + year"
                ri, _ = M.single_outcome_ri(panel, season, oc, standardized=True, basin_year=basin_year)
                wl, wh, wp, nb = M.single_outcome_wild_ci(panel, season, oc, standardized=True,
                                                          basin_year=basin_year)
                repaired.append({
                    "season_scope": season, "outcome": oc, "fixed_effects": fe_label,
                    "beta_log1p_tau": f.beta,
                    "cluster_se_repaired": f.se_cluster,
                    "cluster_ci_low_repaired": f.ci_low, "cluster_ci_high_repaired": f.ci_high,
                    "cluster_p_two_sided_repaired": f.p_cluster_two_sided,
                    "wild_ci_low": wl, "wild_ci_high": wh, "wild_p_beta_le_0": wp,
                    "ri_p_right_positive_tau": ri, "n": f.n, "n_weirs": f.n_weirs,
                    "n_permutations": M.N_PERM, "n_bootstrap": nb,
                    "cluster_se_as_submitted_code": a.se_cluster,
                    "defect_hit": bool(a.se_cluster == 0.0 and f.se_cluster > 0.0),
                })
                if not basin_year:
                    s = sub[(sub.season_scope == season) & (sub.outcome == oc)]
                    defect.append({
                        "season_scope": season, "outcome": oc,
                        "frame_index_min": int(d.index.min()), "frame_index_max": int(d.index.max()),
                        "index_is_zero_based": bool(d.index.min() == 0),
                        "beta_unchanged": bool(abs(a.beta - f.beta) < 1e-12),
                        "submitted_cluster_se": float(s.cluster_se.iloc[0]) if len(s) else np.nan,
                        "reproduced_buggy_cluster_se": a.se_cluster,
                        "repaired_cluster_se": f.se_cluster,
                        "repaired_ci_low": f.ci_low, "repaired_ci_high": f.ci_high,
                        "repaired_cluster_p": f.p_cluster_two_sided,
                    })
                log.append({"step": "fit", "season": season, "outcome": oc, "fe": fe_label,
                            "beta": f.beta, "se_buggy": a.se_cluster, "se_repaired": f.se_cluster})
                print(json.dumps(log[-1], ensure_ascii=False, default=float))

    pd.DataFrame(defect).to_csv(OUT / "cluster_se_defect.csv", index=False)
    pd.DataFrame(repaired).to_csv(OUT / "M6_per_outcome_slopes_repaired.csv", index=False)

    # S3 adjusted per-endpoint slopes, index-safe
    cov = pd.read_csv(OUT / "covariate_panel.csv")
    s3 = []
    for season in SEASONS:
        c = cov[cov.season_scope == season]
        for key, col in [("cyano", "harmful_cyanobacteria_total_log1p_mean"),
                         ("chlorophyll_a", "chlorophyll_a_log1p_mean")]:
            d = c[["weir_name", "year", "river", "tau_days", "log_discharge",
                   "water_temp_c", col]].dropna().reset_index(drop=True).copy()
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
                           "ci_excludes_zero": bool(f.ci_low > 0 or f.ci_high < 0)})
                print(json.dumps(s3[-1], default=float))
    pd.DataFrame(s3).to_csv(OUT / "M2_per_endpoint_slopes.csv", index=False)
    (OUT / "repair_log.json").write_text(json.dumps(log, indent=2, default=float), encoding="utf-8")
    print("\nDONE")


if __name__ == "__main__":
    main()
