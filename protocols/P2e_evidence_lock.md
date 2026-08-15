# P2e EVIDENCE LOCK — mask-variant uncertainty transfer and ED-03 source closure

Written **before** any recomputation. Worker: claude-1 · turn `T1_claude1_9cb710` · 2026-08-15.

---

## 1. What this task is, and what it is not

**This is a verification and transfer task.** The V00–V07 uncertainty evidence was generated in
June 2026 and already exists on disk. P2e reproduces it, reconciles it, and makes it
machine-readable for the manuscript. P2e does **not** select a new method, does not fit a new
model, and does not run any new remote-sensing extraction.

**Explicitly forbidden by this lock:**

- Choosing among available inference schemes by which one is most favourable to the paper.
- Relabelling the Round_2 **temporal-placebo** significance as the common V00–V07 inference.
  The placebo scheme tests a different null and was not applied uniformly across V00–V07.
- Inventing a confidence interval if the CI-generating implementation cannot be located. In that
  case the existing interval is reported as **legacy secondary evidence with exact provenance**.
- Reporting any variant as conventionally significant under the primary scheme.

## 2. Inference hierarchy — fixed here, inherited from Round_2

`Round_2/02_analysis/variant_permutation/inference_decision.md`
(SHA-256 `c3c0fb8595d039f0fbc730a173b855ec86c9ada07f2fa7683c4b2e1bd9f0a117`) decided:

- **PRIMARY, for every V00–V07 row:** exact treatment/control assignment sign-flip over
  pair-level DiD values, enumerated over all 2^n sign patterns.
- **SECONDARY, for every row:** the Round_1 cluster/wild-bootstrap-style CI and p, retained for
  completeness.
- **REJECTED as primary:** temporal placebo-year permutation (different null, not uniformly
  available); sign retention / non-reversal (not significance evidence).

That decision is inherited verbatim. Its stated consequence also binds this task: the manuscript
"may not claim that the pooled default/current-frame effect or any V00-V07 variant is
conventionally significant under the primary inference."

## 3. Authoritative source resolution (decided before recomputation)

Two files describe V00–V07 and **they disagree**. The disagreement is resolved as follows.

| File | SHA-256 | Status |
|---|---|---|
| `research_execution/02_sampling_frame_gate/gate_summary_table.csv` | `575cad69b5e9ce29f427a4d01899a3e529d87ffb5cba6d2a2c584bfc94fad7a3` | **AUTHORITATIVE** — 8 rows, carries `pooled_effect`, `ci_low`, `ci_high`, `p_value`, `admissible_cells`, `verdict` for all of V00–V07 |
| `research_execution/02_sampling_frame_gate/mask_variant_registry.csv` | `8364bd9cc45264ba8a34af59435a72ed07f9cdb76501a12fd03a21195dee1b10` | **STALE — do not use for V04–V07** |

The registry is stale in two specific, checkable ways:

1. It labels V04 `occurrence_threshold_sensitivity` at threshold 30 and V05 at threshold 70,
   whereas the completed gate summary records V04 as `fixed_pre_water_2000_2011` and V05 as
   `high_occurrence_70`.
2. Its `effect_rerun_status` column still reads `water_pixel_count_only` for V04/V05 and
   `full_gee_export_required` for V06/V07, while the gate summary and the GEE export summary both
   record "Full GEE reduceRegions variant extraction completed" for V04–V07.

The registry carries **no** effect, interval, or p column at all. It is a variant-definition
table only.

## 4. Frozen inputs and SHA-256

| SHA-256 | Path (relative to `0_HAB/`) | Role |
|---|---|---|
| `575cad69b5e9ce29f427a4d01899a3e529d87ffb5cba6d2a2c584bfc94fad7a3` | `research_execution/02_sampling_frame_gate/gate_summary_table.csv` | authoritative 8-variant effects + secondary CI/p |
| `fb03c168a557536c2af58f186c166effc246def0ef9a5c494aad7b7607e3f30f` | `research_execution/02_sampling_frame_gate/gate_results_site_year.csv` | pair-level DiD for V00–V03 (16 pairs + `weak_control`, `dalseong` flags) |
| `fbfd47dad8ca491b29800eb2e222f75853b36e2b469c5f1bce1c6acbf0d606c3` | `research_execution/02_sampling_frame_gate/gee_exports/variant_gate_summary.csv` | V04–V07 GEE summary, cross-check |
| `a85f417bf1a5779f72fee868a6c996a926458772f355bff97af36dfc4654548a` | `.../gee_exports/V04_pair_did.csv` | pair-level DiD, V04 |
| `95398a3665846676d24d980d6c4d3054318dbc903ff4438af028a46705089e58` | `.../gee_exports/V05_pair_did.csv` | pair-level DiD, V05 |
| `1a2322330bfbb9f30c8bc91b64ffb4ecb4dfb4bf20ab69eb9b2f4819c39fcc52` | `.../gee_exports/V06_pair_did.csv` | pair-level DiD, V06 |
| `52ba16e2d6b65b54aebdc5afcbcabb6cfe5f0a7ac687c32083a32aee4dc4ac04` | `.../gee_exports/V07_pair_did.csv` | pair-level DiD, V07 |
| `6110baf566cdbb134b69098ed3f7313ca8bd6d26e7e05077b972b1d77a42b311` | `Round_2/02_analysis/variant_permutation/assignment_permutation_summary.csv` | reproduction target: primary p, exact permutation counts |
| `c3c0fb8595d039f0fbc730a173b855ec86c9ada07f2fa7683c4b2e1bd9f0a117` | `Round_2/02_analysis/variant_permutation/inference_decision.md` | inference hierarchy |
| `5dd981ae2e99ef66bfc39eaf4c789a86af632270cfcf68695ce09cd7e66f220a` | `Round_2/.../run_variant_assignment_permutation.py` | historical generator (read for method definition; **not** vendored or executed) |
| `98ac9702cd6d722d144722f3fe346b24111f1440ae3d116855865be60c61c47f` | `manuscript_EI_dense/03_manuscript/figures/render_submission_figures.py` | the renderer that produced the submitted Figure 6 |
| `ac49ec156bbc2c7cc6b9dc4eb03923ca5d291ab83bb7e68f2dc2bee72641e0f2` | `revision_1/original/figure6_sampling_frame_envelope.png` | the submitted Figure 6 itself |

## 5. Variant construction, fixed before recomputation

V00–V03 are filters over the 16 rows of `gate_results_site_year.csv`:

| Variant | Filter | Expected n pairs | Expected exact permutations |
|---|---|---:|---:|
| V00 | all pairs | 16 | 65,536 |
| V01 | `weak_control == False` | 13 | 8,192 |
| V02 | `dalseong == False` | 15 | 32,768 |
| V03 | `weak_control == False` and `dalseong == False` | 13 | 8,192 |

Dalseong Weir is itself one of the three weak-control weirs (the others being Gongju and
Seungchon), so V01 and V03 select the **same 13 pairs** and must produce numerically identical
results. That identity is a structural consequence of the flags, not a duplication defect, and it
is recorded here in advance so it is not later mistaken for one.

V04–V07 take all rows of their own `V0x_pair_did.csv` file.

## 6. Estimator, fixed before recomputation

For pair-level DiD values d_1 … d_n:

```
observed  = mean(d)
null      = { mean(s_i * d_i) : s in {-1,+1}^n }        # all 2^n sign patterns
p_one_sided_positive = #{ x in null : x >= observed - eps } / 2^n
p_two_sided          = #{ x in null : |x| >= |observed| - eps } / 2^n
eps = 1e-15
```

P2e writes its **own independent implementation**. The historical script is read to define the
estimator and is neither vendored nor executed, so agreement is evidence of reproduction rather
than of running the same code twice.

## 7. PASS gates and tolerances, fixed before recomputation

| Gate | Condition | Tolerance |
|---|---|---|
| G1 | recomputed `n_pairs` equals the historical value for all 8 variants | exact |
| G2 | recomputed `exact_permutations` equals 2^n and equals the historical value | exact |
| G3 | recomputed pooled effect equals `pooled_effect` in `assignment_permutation_summary.csv` | atol 1e-12 |
| G4 | recomputed pooled effect equals `pooled_effect` in `gate_summary_table.csv` | atol 1e-9 |
| G5 | recomputed `p_one_sided_positive` equals the historical primary p | atol 1e-12 |
| G6 | recomputed `p_two_sided` equals the historical primary two-sided p | atol 1e-12 |
| G7 | V01 and V03 results identical to each other | exact |
| G8 | every V00–V07 secondary CI contains zero | boolean |
| G9 | no variant has primary one-sided p < 0.05 | boolean |
| G10 | historical input hashes unchanged after the run | exact |

**If G3–G6 fail for any variant, P2e reports a reproduction failure and does not publish a
transferred number for that variant.** G8 and G9 are descriptive gates: they record the central
result and are reported whichever way they resolve.

## 8. Pre-committed expected result

From the packet and from the authoritative table read at lock time, the expected envelope is:
every V00–V07 secondary CI includes zero; no variant reaches conventional significance under the
exact primary scheme; V06 changes sign; V04, V05 and V07 remain small positive point estimates.
If recomputation contradicts any part of this, the contradiction is reported rather than the
expectation.

## 9. Secondary-CI provenance rule

The `ci_low`/`ci_high`/`p_value` columns are described by Round_2 only as "Round_1
cluster/wild-bootstrap-style CI/p retained for completeness". P2e will attempt to locate the
producing implementation by content search. If it is found, the method is named. **If it is not
found, the interval is reported as legacy secondary evidence with its exact file provenance and
is not recomputed, re-derived, or replaced.** No new interval is manufactured under any outcome.

## 10. Write boundary

Writes are confined to `03_analysis/frozen_protocols/P2e_evidence_lock.md`,
`03_analysis/code/P2e/**`, `03_analysis/output/P2e/**`,
`03_analysis/output/M10_mask_uncertainty.md`, and `99_admin/reports/P2e_REPORT.md`.
The manuscript, response letter, comment ledger, deposit, and all historical sources are
read-only in this turn.
