#!/usr/bin/env python3
"""hydrologic robustness — build the same-support weir-year covariate panel.

Constructions are fixed by 03_analysis/frozen_protocols/hydrologic_robustness_freeze.md section 5.
Read-only on all historical trees; writes only under HYDRO_OUT.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BASE = Path(os.environ.get("HYDRO_SOURCE_ROOT", str(REPOSITORY_ROOT / "raw")))
OUT = Path(os.environ.get("HYDRO_OUT", str(REPOSITORY_ROOT / "reproduction_output/hydrologic_robustness")))
OUT.mkdir(parents=True, exist_ok=True)

HYD = [BASE / "Round_3/01_data/hydrology/mywater_weir_daily_2017_2020_long.csv",
       BASE / "Round_3/01_data/hydrology/mywater_weir_daily_2021_2025_long.csv"]
CHLA = BASE / "Round_6/01_data/insitu/chlorophyll_panel.csv"
PANEL = BASE / "Round_6/02_analysis/proxy_validation/insitu_annual_analysis_panel.csv"

V_STORAGE, V_DISCHARGE = "저수량 (MCM)", "총방류량 (CMS)"
V_INFLOW, V_LEVEL, V_RAIN = "총유입량 (CMS)", "수위 (EL.m)", "강우량 (mm)"
BLOOM_MONTHS = [6, 7, 8, 9, 10]

acct: list[dict] = []


def note(step: str, **kw):
    rec = {"step": step, **kw}
    acct.append(rec)
    print(json.dumps(rec, ensure_ascii=False))


def load_daily() -> pd.DataFrame:
    cols = ["weir_code", "weir_name", "year", "date", "variable_original", "value"]
    d = pd.concat([pd.read_csv(f, usecols=cols) for f in HYD], ignore_index=True)
    note("hydrology_loaded", rows=len(d), weirs=int(d.weir_name.nunique()),
         years=[int(d.year.min()), int(d.year.max())])
    keep = [V_STORAGE, V_DISCHARGE, V_INFLOW, V_LEVEL, V_RAIN]
    d = d[d.variable_original.isin(keep)].copy()
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d["month"] = d["date"].dt.month
    note("hydrology_filtered", rows=len(d), nonnumeric=int(d.value.isna().sum()))
    w = d.pivot_table(index=["weir_code", "weir_name", "year", "date", "month"],
                      columns="variable_original", values="value", aggfunc="mean").reset_index()
    note("hydrology_pivoted", weir_days=len(w),
         expected=int(d.groupby(["weir_code", "date"]).ngroups))
    return w


def window_aggregate(w: pd.DataFrame, months: list[int] | None, scope: str) -> pd.DataFrame:
    sub = w if months is None else w[w.month.isin(months)]
    # paired positive-discharge day-set: the same rule the submitted tau uses
    pos = sub[sub[V_DISCHARGE] > 0]
    g = pos.groupby(["weir_code", "weir_name", "year"])
    out = pd.DataFrame({
        "storage_mcm": g[V_STORAGE].mean(),
        "discharge_cms": g[V_DISCHARGE].mean(),
        "n_days_positive_pair": g[V_DISCHARGE].size(),
    })
    gall = sub.groupby(["weir_code", "weir_name", "year"])
    out["water_level_m"] = gall[V_LEVEL].mean()
    out["rainfall_mm"] = gall[V_RAIN].sum()
    out["inflow_cms"] = gall[V_INFLOW].mean()
    out["n_days_window"] = gall[V_DISCHARGE].size()
    out = out.reset_index()
    out["season_scope"] = scope
    out["tau_days_recomputed"] = out.storage_mcm * 1e6 / out.discharge_cms / 86400.0
    note(f"hydro_agg_{scope}", rows=len(out),
         n_days_min=int(out.n_days_window.min()), n_days_max=int(out.n_days_window.max()),
         zero_pos_days=int((out.n_days_positive_pair == 0).sum()))
    return out


def temperature(scope: str, months: list[int] | None) -> pd.DataFrame:
    c = pd.read_csv(CHLA, low_memory=False)
    t = c[c.variable == "water_temperature"].copy()
    t["value"] = pd.to_numeric(t["value"], errors="coerce")
    note(f"temp_rows_{scope}", rows=len(t), nonnumeric=int(t.value.isna().sum()))
    if months is not None:
        t = t[t.sampling_month.isin(months)]
    g = t.groupby(["weir_name", "sampling_year"])["value"]
    out = pd.DataFrame({"water_temp_c": g.mean(), "n_temp_obs": g.size()}).reset_index()
    out = out.rename(columns={"sampling_year": "year"})
    note(f"temp_agg_{scope}", weir_years=len(out), total_obs=int(out.n_temp_obs.sum()))
    return out


def main() -> None:
    w = load_daily()
    panel = pd.read_csv(PANEL)
    frames = []
    for scope, months in [("annual_all_samples", None), ("bloom_season_06_10", BLOOM_MONTHS)]:
        hy = window_aggregate(w, months, scope)
        tp = temperature(scope, months)
        p = panel[panel.season_scope == scope][
            ["weir_name", "weir_code", "year", "river", "season_scope", "tau_days",
             "tau_robustness_flag", "harmful_cyanobacteria_total_log1p_mean",
             "chlorophyll_a_log1p_mean", "harmful_cyanobacteria_total_n", "chlorophyll_a_n"]].copy()
        note(f"panel_rows_{scope}", rows=len(p))

        m = p.merge(hy.drop(columns=["weir_name", "season_scope"]),
                    on=["weir_code", "year"], how="left", indicator=True)
        note(f"join_hydro_{scope}", rows=len(m),
             matched=int((m._merge == "both").sum()), unmatched=int((m._merge != "both").sum()))
        m = m.drop(columns="_merge")

        m = m.merge(tp, on=["weir_name", "year"], how="left", indicator=True)
        note(f"join_temp_{scope}", rows=len(m),
             matched=int((m._merge == "both").sum()), unmatched=int((m._merge != "both").sum()))
        m = m.drop(columns="_merge")

        for c in ["storage_mcm", "discharge_cms", "water_level_m", "rainfall_mm",
                  "water_temp_c", "inflow_cms"]:
            note(f"missing_{scope}_{c}", missing=int(m[c].isna().sum()), n=len(m))
        m["log_storage"] = np.log(m.storage_mcm)
        m["log_discharge"] = np.log(m.discharge_cms)
        m["log1p_tau"] = np.log1p(m.tau_days)
        frames.append(m)

    cov = pd.concat(frames, ignore_index=True)
    cov.to_csv(OUT / "covariate_panel.csv", index=False)
    note("covariate_panel_written", rows=len(cov), cols=len(cov.columns))

    # tau reproduction check against the submitted annual tau
    ann = cov[cov.season_scope == "annual_all_samples"]
    err = (ann.tau_days_recomputed - ann.tau_days).abs()
    rel = (err / ann.tau_days).replace([np.inf, -np.inf], np.nan)
    note("tau_reproduction_annual", n=len(ann), max_abs_err=float(err.max()),
         median_abs_err=float(err.median()), max_rel_err=float(rel.max()),
         corr=float(np.corrcoef(ann.tau_days_recomputed, ann.tau_days)[0, 1]))
    bloom = cov[cov.season_scope == "bloom_season_06_10"]
    b = bloom[["weir_code", "year", "tau_days", "tau_days_recomputed"]].copy()
    note("tau_bloom_vs_submitted_annual", n=len(b),
         max_abs_diff=float((b.tau_days_recomputed - b.tau_days).abs().max()),
         corr=float(np.corrcoef(b.tau_days_recomputed, b.tau_days)[0, 1]))

    # structural collinearity, declared in freeze section 5
    a = ann.dropna(subset=["log1p_tau", "log_storage", "log_discharge"])
    note("collinearity_annual",
         corr_tau_logdisch=float(np.corrcoef(a.log1p_tau, a.log_discharge)[0, 1]),
         corr_tau_logstor=float(np.corrcoef(a.log1p_tau, a.log_storage)[0, 1]),
         corr_logstor_logdisch=float(np.corrcoef(a.log_storage, a.log_discharge)[0, 1]))

    pd.DataFrame(acct).to_csv(OUT / "sample_accounting_covariates.csv", index=False)
    (OUT / "sample_accounting_covariates.json").write_text(
        json.dumps(acct, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nWrote", OUT / "covariate_panel.csv")


if __name__ == "__main__":
    main()
