# M1 Freeze — P2a residence-time reconciliation

- Protocol ID: `P2a_M1_v1`
- Worker turn: `T1_codex1_2a8433`
- Freeze rule: this file and `M1_protocol_v1.json` were written before any new endpoint-specific result was computed.
- Historical values were already visible in the submitted artifacts; the freeze protects choices for the new comparison and inference.

## Fixed model hierarchy

1. Historical common-weir/year-FE stacked model: exact reproduction only.
2. Separate endpoint-specific TWFE models: point-estimate decomposition.
3. Endpoint-specific-weir/year-FE stacked model: primary direct comparison.
4. Unified weir-cluster system contrast: valid direct joint test; covariance between endpoints is retained.
5. Historical within-year RI: reproduction only, not an equality test.

Annual is primary confirmatory. Bloom season is prespecified secondary. Both must be reported. Primary scale is endpoint-wise `ddof=1` z-score of the existing log1p outcome on identical shared support. Exposure is `log1p(tau_days)`. No support, scale, season, FE, cluster, sidedness, multiplicity, or inference role may change after results are seen.

## Fixed inference

- Null: `beta_cyano - beta_chlorophyll = 0`; alternative: two-sided.
- Cluster: `weir_name`, with both endpoints and all years kept together.
- Primary p-value: null-imposed restricted wild-cluster bootstrap-t using all `2^16 = 65,536` Rademacher sign patterns.
- Secondary interval: paired weir-cluster bootstrap percentile interval with 9,999 draws and seed 20260630.
- Analytic CR1/t(15): diagnostic only.
- Multiplicity: Holm correction over annual and bloom primary-contrast p-values.
- Every sign pattern and bootstrap draw is preserved. Nonfinite or missing draws halt the run.

## Candidate explanations and falsifiers

| ID | Candidate | Supporting observation | Falsifying observation |
|---|---|---|---|
| E1 | Common versus endpoint-specific weir/year FE changes the estimand. | Legacy common-FE values reproduce, while endpoint-specific stacked delta equals the separate arithmetic difference and differs from the common-FE delta. | Endpoint-specific delta fails to equal the separate difference on identical support after design/rank checks; this is an implementation halt. |
| E2 | Different support or z-scaling caused the discrepancy. | The two paths use different rows, means, or SDs and harmonization removes the gap. | Shared support is 144 rows per season with identical outcome means/SDs and the common-FE gap remains. |
| E3 | The reported 0.887/1.035 is a typo or label error. | Frozen code fails to reproduce the historical interaction or the cell maps to another coefficient/sign. | Frozen code/input reproduces the named historical interaction exactly. |
| E4 | A code/design bug caused the discrepancy. | Duplicate/misaligned rows, wrong coefficient index, rank defect, solver disagreement, or independently permuted endpoint exposure is found. | Pairing, rank, coefficient mapping, and algebraic tests pass. |
| E5 | Historical code/output drift prevents attribution. | A canonical hash fails or exact frozen bytes fail numeric regression targets. | All source hashes and numeric targets reproduce within the frozen tolerance. |
| E6 | Cyanobacteria has the stronger defensible endpoint-specific slope. | Endpoint-specific delta is positive and the two-sided WCR/Holm result supports the contrast. | Delta is nonpositive or the primary test/interval fails to support separation; report weakening or direction change without switching models. |

E1–E5 diagnose the discrepancy. E6 assesses the scientific comparison. These are reported separately.

## Adverse-result and D1 rules

- Every prespecified row is reported regardless of favorability.
- Reproduction failure is reported as failure; no nearby substitute value is allowed.
- Positive delta with non-supporting WCR is “direction preserved, inferential support weakened.”
- Nonpositive delta is “direction change/reversal.”
- A defensible endpoint-specific coefficient different from the common-FE coefficient is an estimand change, not an arithmetic correction.
- Historical zero cluster SEs and conflicting inference quantities are disclosed.
- D1 is author-owned. P2a only identifies whether its trigger is present.

## Post-hoc switching guard

A favorable result cannot promote a diagnostic or historical model, and an adverse result cannot demote or omit the endpoint-specific primary model. Any result-aware change requires a new protocol ID and a separately retained run; `v1` is never overwritten.
