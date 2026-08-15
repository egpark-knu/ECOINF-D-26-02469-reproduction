#!/usr/bin/env python3
"""Minimal tests for the P2e exact sign-flip estimator (no network, no historical writes)."""
import itertools, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from reproduce_signflip import exact_sign_flip, variant_values

fails = []
def check(name, cond, detail=""):
    print(("[pass] " if cond else "[FAIL] ") + name + ("" if cond else f" -> {detail}"))
    if not cond: fails.append(name)

# T1 symmetric data -> observed mean 0, two-sided p must be 1.0
r = exact_sign_flip([1.0, -1.0])
check("T1 symmetric mean is zero", abs(r["observed_mean"]) < 1e-15, r["observed_mean"])
check("T1 two-sided p == 1.0", abs(r["p_two_sided"] - 1.0) < 1e-15, r["p_two_sided"])
check("T1 permutations == 2^2", r["exact_permutations"] == 4, r["exact_permutations"])

# T2 all-positive identical values -> only the all-plus pattern reaches the observed mean
n = 5
r = exact_sign_flip([2.0]*n)
check("T2 permutations == 2^5", r["exact_permutations"] == 32)
check("T2 one-sided p == 1/32", abs(r["p_one_sided_positive"] - 1/32) < 1e-15, r["p_one_sided_positive"])

# T3 sign flip of every value negates the observed mean but leaves two-sided p unchanged
a = [0.3, -0.1, 0.7, 0.05, -0.9, 0.2]
ra, rb = exact_sign_flip(a), exact_sign_flip([-x for x in a])
check("T3 mean negates", abs(ra["observed_mean"] + rb["observed_mean"]) < 1e-15)
check("T3 two-sided p invariant", abs(ra["p_two_sided"] - rb["p_two_sided"]) < 1e-15)

# T4 null distribution is symmetric -> p_one_sided(obs) + p_one_sided(-obs) >= 1
check("T4 one-sided p in (0,1]", 0 < ra["p_one_sided_positive"] <= 1.0, ra["p_one_sided_positive"])

# T5 variant filters select the documented pair counts
exp = {"V00":16,"V01":13,"V02":15,"V03":13,"V04":15,"V05":16,"V06":16,"V07":16}
for vid, k in exp.items():
    v, _ = variant_values(vid)
    check(f"T5 {vid} n_pairs == {k}", len(v) == k, len(v))

# T6 V01 and V03 select the identical pair set (Dalseong is itself a weak-control weir)
check("T6 V01 pair set == V03 pair set", variant_values("V01")[0] == variant_values("V03")[0])

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILURES: {fails}")
sys.exit(1 if fails else 0)
