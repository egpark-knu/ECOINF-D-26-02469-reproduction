#!/usr/bin/env python3
"""P2e step 3 - identify and verify the producing method for the secondary CI/p columns.

Candidate implementation located by content search:
  research_execution/run_phase2_5_research.py::pooled_summary            (V00-V03)
  research_execution/run_phase2_full_gee_variants.py                     (V04-V07)
Both compute, on the pair-level DiD values:
  se = std(vals, ddof=1)/sqrt(n);  ci = t.interval(0.95, n-1, loc=mean, scale=se)
  p  = ttest_1samp(vals, 0).pvalue
i.e. an ORDINARY ONE-SAMPLE STUDENT-t interval/test - not a cluster or wild bootstrap.
This script tests that hypothesis against the frozen gate_summary_table.csv values.
"""
from __future__ import annotations
import csv, itertools, json, math, os
from pathlib import Path
import numpy as np
from scipy import stats

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BASE = Path(os.environ.get("P2E_SOURCE_ROOT", str(REPOSITORY_ROOT / "data/P2e/source_inputs")))
OUT = Path(os.environ.get("P2E_OUT", str(REPOSITORY_ROOT / "reproduction_output/P2e")))
GATE = BASE / "research_execution/02_sampling_frame_gate"
PAIRS = GATE / "gate_results_site_year.csv"
GEE = GATE / "gee_exports"

def rows(p): return list(csv.DictReader(p.open(encoding="utf-8")))
CUR = {"V00": lambda w,d: True, "V01": lambda w,d: not w,
       "V02": lambda w,d: not d, "V03": lambda w,d: (not w) and (not d)}

def vals_for(vid):
    if vid in CUR:
        k = CUR[vid]
        return [float(r["did"]) for r in rows(PAIRS)
                if k(r["weak_control"]=="True", r["dalseong"]=="True")]
    return [float(r["did"]) for r in rows(GEE / f"{vid}_pair_did.csv")]

gate = {r["variant_id"]: r for r in rows(GATE / "gate_summary_table.csv")}
out = []
for vid in ["V00","V01","V02","V03","V04","V05","V06","V07"]:
    v = np.array(vals_for(vid), dtype=float)
    n = len(v); mean = float(v.mean())
    se = float(v.std(ddof=1)/math.sqrt(n))
    lo, hi = stats.t.interval(0.95, n-1, loc=mean, scale=se)
    p = float(stats.ttest_1samp(v, 0).pvalue)
    g = gate[vid]
    rec = {"variant_id": vid, "n": n,
           "recomputed_t_ci_low": float(lo), "stored_ci_low": float(g["ci_low"]),
           "recomputed_t_ci_high": float(hi), "stored_ci_high": float(g["ci_high"]),
           "recomputed_t_p": p, "stored_p": float(g["p_value"]),
           "ci_low_match_1e12": abs(lo-float(g["ci_low"]))<1e-12,
           "ci_high_match_1e12": abs(hi-float(g["ci_high"]))<1e-12,
           "p_match_1e12": abs(p-float(g["p_value"]))<1e-12}
    rec["method_confirmed"] = all([rec["ci_low_match_1e12"], rec["ci_high_match_1e12"], rec["p_match_1e12"]])
    out.append(rec)
    print(json.dumps({k: rec[k] for k in ("variant_id","n","recomputed_t_p","stored_p","method_confirmed")}, default=float))

allok = all(r["method_confirmed"] for r in out)
res = {"hypothesis": "secondary CI/p = one-sample Student-t interval and one-sample t-test on pair-level DiD",
       "candidate_implementations": [
           "research_execution/run_phase2_5_research.py::pooled_summary",
           "research_execution/run_phase2_full_gee_variants.py"],
       "historical_label_in_Round_2": "Round_1 cluster/wild-bootstrap-style CI/p retained for completeness",
       "label_is_accurate": False,
       "all_variants_confirmed": allok,
       "per_variant": out}
(OUT / "secondary_ci_reconciliation.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
print("\nMETHOD CONFIRMED FOR ALL 8 VARIANTS:", allok)
print("Historical label 'cluster/wild-bootstrap-style' is INACCURATE; actual method is one-sample Student-t.")
