#!/usr/bin/env python3
"""P2e — independent reproduction of the exact V00–V07 assignment sign-flip inference.

Estimator and gates are fixed by 03_analysis/frozen_protocols/P2e_evidence_lock.md.
This is an independent reimplementation: the historical generator is read for the method
definition only, and is neither imported nor executed here.

Read-only on every historical input. Writes only under 03_analysis/output/P2e/.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import os
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BASE = Path(os.environ.get("P2E_SOURCE_ROOT", str(REPOSITORY_ROOT / "data/P2e/source_inputs")))
OUT = Path(os.environ.get("P2E_OUT", str(REPOSITORY_ROOT / "reproduction_output/P2e")))
OUT.mkdir(parents=True, exist_ok=True)

GATE = BASE / "research_execution/02_sampling_frame_gate"
PAIRS_CURRENT = GATE / "gate_results_site_year.csv"
GEE = GATE / "gee_exports"
GATE_SUMMARY = GATE / "gate_summary_table.csv"
REGISTRY = GATE / "mask_variant_registry.csv"
HIST = BASE / "Round_2/02_analysis/variant_permutation/assignment_permutation_summary.csv"

EPS = 1e-15
CURRENT = {"V00": lambda w, d: True,
           "V01": lambda w, d: not w,
           "V02": lambda w, d: not d,
           "V03": lambda w, d: (not w) and (not d)}
GEE_VARIANTS = ["V04", "V05", "V06", "V07"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rows(p: Path) -> list[dict]:
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def exact_sign_flip(vals: list[float]) -> dict:
    """Enumerate all 2^n treatment/control sign patterns over pair-level DiD values."""
    n = len(vals)
    obs = sum(vals) / n
    ge_pos = ge_abs = 0
    total = 0
    for signs in itertools.product((-1.0, 1.0), repeat=n):
        m = sum(s * v for s, v in zip(signs, vals)) / n
        total += 1
        if m >= obs - EPS:
            ge_pos += 1
        if abs(m) >= abs(obs) - EPS:
            ge_abs += 1
    return {"n_pairs": n, "observed_mean": obs, "exact_permutations": total,
            "p_one_sided_positive": ge_pos / total, "p_two_sided": ge_abs / total}


def variant_values(vid: str) -> tuple[list[float], str]:
    if vid in CURRENT:
        keep = CURRENT[vid]
        vals = [float(r["did"]) for r in rows(PAIRS_CURRENT)
                if keep(r["weak_control"] == "True", r["dalseong"] == "True")]
        return vals, str(PAIRS_CURRENT)
    p = GEE / f"{vid}_pair_did.csv"
    return [float(r["did"]) for r in rows(p)], str(p)


def main() -> None:
    inputs = [PAIRS_CURRENT, GATE_SUMMARY, REGISTRY, HIST] + [GEE / f"{v}_pair_did.csv" for v in GEE_VARIANTS]
    before = {str(p.relative_to(BASE)): sha256(p) for p in inputs}

    gate = {r["variant_id"]: r for r in rows(GATE_SUMMARY)}
    hist = {r["variant_id"]: r for r in rows(HIST)}

    results, gates = [], []
    for vid in ["V00", "V01", "V02", "V03"] + GEE_VARIANTS:
        vals, src = variant_values(vid)
        rec = exact_sign_flip(vals)
        h, g = hist[vid], gate[vid]
        row = {
            "variant_id": vid,
            "mask_type": g["mask_type"],
            "variant_definition_source": "gate_summary_table.csv (authoritative)",
            "n_pairs": rec["n_pairs"],
            "admissible_cells": g["admissible_cells"],
            "inadmissible_cells": g["inadmissible_cells"],
            "pooled_effect": rec["observed_mean"],
            "primary_inference": "exact treatment/control assignment sign-flip over pair-level DiD",
            "exact_permutations": rec["exact_permutations"],
            "primary_p_one_sided_positive": rec["p_one_sided_positive"],
            "primary_p_two_sided": rec["p_two_sided"],
            "secondary_inference": "one-sample Student-t interval and one-sample t-test on pair-level DiD (method identified and exactly reproduced by P2e; the Round_2 label 'cluster/wild-bootstrap-style' is inaccurate)",
            "secondary_ci_low": float(g["ci_low"]),
            "secondary_ci_high": float(g["ci_high"]),
            "secondary_p_value": float(g["p_value"]),
            "secondary_ci_includes_zero": float(g["ci_low"]) <= 0.0 <= float(g["ci_high"]),
            "primary_significant_at_0p05": rec["p_one_sided_positive"] < 0.05,
            "sign": "positive" if rec["observed_mean"] > 0 else ("negative" if rec["observed_mean"] < 0 else "zero"),
            "historical_verdict": g["verdict"],
            "pair_source_file": src,
            "summary_source_file": str(GATE_SUMMARY),
        }
        # per-variant reproduction gates
        chk = {
            "G1_n_pairs": rec["n_pairs"] == int(float(h["n_pairs"])),
            "G2_permutations": (rec["exact_permutations"] == 2 ** rec["n_pairs"]
                                and rec["exact_permutations"] == int(float(h["exact_permutations"]))),
            "G3_effect_vs_hist": abs(rec["observed_mean"] - float(h["pooled_effect"])) < 1e-12,
            "G4_effect_vs_gate": abs(rec["observed_mean"] - float(g["pooled_effect"])) < 1e-9,
            "G5_p_one_sided": abs(rec["p_one_sided_positive"] - float(h["primary_perm_p_one_sided_positive"])) < 1e-12,
            "G6_p_two_sided": abs(rec["p_two_sided"] - float(h["primary_perm_p_two_sided"])) < 1e-12,
        }
        row["reproduction_pass"] = all(chk.values())
        gates.append({"variant_id": vid, **chk,
                      "hist_effect": float(h["pooled_effect"]),
                      "hist_p_one_sided": float(h["primary_perm_p_one_sided_positive"]),
                      "hist_p_two_sided": float(h["primary_perm_p_two_sided"]),
                      "gate_effect": float(g["pooled_effect"])})
        results.append(row)
        print(json.dumps({k: row[k] for k in
                          ("variant_id", "n_pairs", "pooled_effect", "primary_p_one_sided_positive",
                           "secondary_ci_low", "secondary_ci_high", "secondary_ci_includes_zero",
                           "reproduction_pass")}, default=float))

    v01 = next(r for r in results if r["variant_id"] == "V01")
    v03 = next(r for r in results if r["variant_id"] == "V03")
    global_gates = {
        "G7_V01_identical_V03": (v01["pooled_effect"] == v03["pooled_effect"]
                                 and v01["primary_p_one_sided_positive"] == v03["primary_p_one_sided_positive"]),
        "G8_all_secondary_CIs_include_zero": all(r["secondary_ci_includes_zero"] for r in results),
        "G9_no_variant_primary_significant": not any(r["primary_significant_at_0p05"] for r in results),
        "G_all_variants_reproduced": all(r["reproduction_pass"] for r in results),
    }
    after = {str(p.relative_to(BASE)): sha256(p) for p in inputs}
    global_gates["G10_inputs_unchanged"] = before == after

    cols = list(results[0].keys())
    with (OUT / "mask_variant_uncertainty.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in results:
            w.writerow(r)

    ver = {
        "protocol": "P2e_evidence_lock.md",
        "task_type": "verification_and_transfer_of_existing_uncertainty",
        "estimator": "exact treatment/control assignment sign-flip, all 2^n patterns, eps=1e-15",
        "primary_inference_source": "Round_2/02_analysis/variant_permutation/inference_decision.md",
        "independent_reimplementation": True,
        "historical_generator_executed": False,
        "tolerances": {"effect_vs_hist": 1e-12, "effect_vs_gate": 1e-9, "p_values": 1e-12},
        "input_hashes_before": before,
        "input_hashes_after": after,
        "per_variant_gates": gates,
        "global_gates": global_gates,
        "overall": "PASS" if all(global_gates.values()) else "FAIL",
    }
    (OUT / "verification.json").write_text(json.dumps(ver, indent=2, default=float), encoding="utf-8")
    print("\nglobal gates:", json.dumps(global_gates))
    print("OVERALL:", ver["overall"])


if __name__ == "__main__":
    main()
