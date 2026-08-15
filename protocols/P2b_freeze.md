# P2b FREEZE — hydrologic robustness and basin-preserving inference

Written **before** any adjusted model was fitted or any new coefficient viewed.
Worker: claude-1 · 2026-08-15 · turn `T1_claude1_5bd767`
Ledger rows owned: `R2-M02a–g`, `R2-M06a/b`, `R2-m03a` (10 rows).

Everything below is fixed at write time. If a choice here turns out not to be
determined by the evidence, the run **halts and reports** rather than trying an
alternative specification (§9).

---

## 1. Environment (captured before the run)

| Item | Value |
|---|---|
| Interpreter | `python3` — CPython 3.12.13 |
| numpy | 2.4.4 |
| pandas | 2.3.3 |
| scipy | 1.17.1 |
| Seed | `SEED = 20260630` (matches the historical convention) |
| Permutations | `N_PERM = 4999` |
| Wild-bootstrap reps | `N_BOOT = 4999` |

No package is installed or upgraded for this run.

## 2. Frozen inputs and SHA-256

Paths are relative to `source-root/`.

| SHA-256 | Path | Role |
|---|---|---|
| `42f9d731073d3df615f8d172dbfe57c69034f7faf07506abcb86f0b4028bc370` | `Round_3/01_data/hydrology/mywater_weir_daily_2017_2020_long.csv` | daily hydrology 2017–2020 (379,851 rows) |
| `917e8201790de132cc059e687db5c2f4ff540d7af19eec6e9d5e6dee9fef3f7e` | `Round_3/01_data/hydrology/mywater_weir_daily_2021_2025_long.csv` | daily hydrology 2021–2025 (474,753 rows) |
| `8a9acfd0828d5f4d441ded7caa1706ccd980e16417467a58c13d8006765f5f49` | `Round_6/01_data/insitu/chlorophyll_panel.csv` | water temperature source (34,757 rows) |
| `c958efe78888e8a0866c8cf3ab0c06ee74724c84e049feb8dc95126d3f952e2b` | `Round_6/01_data/insitu/cyanobacteria_panel.csv` | record-funnel source (26,868 rows) |
| `83fcf10f4a8b06b2adb0d09370321f1b24bb150fb5be9d0b19e9d487aa1039e7` | `Round_6/02_analysis/proxy_validation/insitu_annual_analysis_panel.csv` | analysis panel (288 rows) |
| `e028d922b48c71d18ead5b0a81ebc190caa228134f6053a1c42553487b1589b2` | `Round_3/01_data/residence_time/tau_panel_candidate_2010_2025_observed_combined.csv` | τ provenance panel (256 rows) |
| `2526e1bf938d618f5073aeabcbece27ede5b0ceda9fa5bebaadee449ce353cda` | `manuscript_EI_terminal/01_models/hardening_specificity_analysis.py` | **model module to vendor** (27,357 B) |
| `c895385a565dc06835e0a03129fbd3fcb97734aaaa2d62d9838c0e6917ca10b0` | `manuscript_EI_hardening/01_models/hardening_specificity_analysis.py` | divergent sibling (23,709 B) — see §3 |
| `c3017354d9bd8ff39317f304d0fd5e8e96c7663fc0b13dcc9d1ce5054e182002` | `manuscript_EI_assert/01_models/basin_year_interaction_analysis.py` | basin-year driver (3 copies byte-identical) |
| `cd7de1cc43040ec756e80589c61a940dfccc23cf9e31851c04d87b5ab96f828f` | `manuscript_EI_hardening/01_models/specificity_interaction.csv` | baseline reproduction target |
| `56f7e95f3d39097dc21620c9975f60821b33ac062c15d8be03e8934e32ddce51` | `manuscript_EI_hardening/01_models/standardized_tau_models.csv` | baseline reproduction target |
| `1b4aa82f2bc68ce66afaa3a1ab6cd5bd987c1e38442e5a8e935f55575e88baa3` | `manuscript_EI_terminal/01_models/interaction_basinyear.csv` | basin-year reproduction target |
| `3b1a398e15c47b9bee95c2119ddbfa9a74bffc96991c6969d63e52a61e5f7cbc` | `manuscript_EI_terminal/01_models/per_outcome_basinyear_slopes.csv` | basin-year reproduction target |

All are read-only. Nothing outside `revision_1/03_analysis/` and
`revision_1/99_admin/reports/` is written.

## 3. Canonical-code selection, decided on hashes not filenames

`hardening_specificity_analysis.py` exists in two **materially different**
versions:

- `manuscript_EI_hardening/` — 23,709 B, `c895385a…`. `stacked_interaction(panel, season)`
  has **no** `basin_year` parameter. This produced the two baseline CSVs.
- `manuscript_EI_{terminal,submit,assert}/` — 27,357 B, `2526e1bf…` (all three
  byte-identical). Adds `permute_tau()`, a `basin_year` argument on
  `stacked_interaction`/`stacked_interaction_ri`, and `basin_year` in `stacked_frame`.

**Decision: vendor the 27,357 B `2526e1bf…` version** as the P2b model module. It
is a strict superset for the estimators P2b needs, and it is the version the
basin-year driver actually imports.

**Known and accepted consequence, recorded before the run:** the two versions seed
the stacked randomization test differently — `stable_seed("stack_ri", season)` in
the 23,709 B version versus `stable_seed("stack_ri", season, basin_year)` in the
27,357 B version. Point estimates must match to floating-point tolerance;
**the weir+year stacked RI p-value may differ in its last digits purely from the
seed**. That is expected, will be reported, and is not treated as a reproduction
failure. Reproduction is judged on point estimates (§7).

## 4. Support, join keys, units, missingness

**Analysis support.** Weir-year, 16 weirs × 9 years (2017–2025) = 144 weir-years
per season scope; two season scopes (`annual_all_samples`, `bloom_season_06_10`)
= 288 panel rows. Join key throughout: `(weir_name, year)`.

**Units, as they appear in the source (Korean labels retained verbatim):**

| Source variable | Unit | Use |
|---|---|---|
| `저수량 (MCM)` | MCM (10⁶ m³) | storage, τ numerator |
| `총방류량 (CMS)` | m³ s⁻¹ | total discharge/outflow, τ denominator |
| `총유입량 (CMS)` | m³ s⁻¹ | inflow — diagnostic only |
| `수위 (EL.m)` | EL.m | water level covariate |
| `강우량 (mm)` | mm | rainfall covariate |
| `water_temperature` (chlorophyll panel) | °C | temperature covariate |

**τ definition, as built by the submitted pipeline** (not re-derived by P2b):
`tau_method = bulk_ratio_mean_paired_storage_over_mean_positive_discharge`, i.e.

```
tau_days = mean_storage_MCM × 1e6 / mean_total_discharge_CMS / 86400
```

where both means are taken over the **same paired day-set restricted to days with
positive total discharge**. This is a bulk ratio of annual means — τ is computed
**after** temporal averaging, not as the mean of daily ratios.

**Discharge is outflow, not inflow** (`총방류량`, `discharge_interpretation =
observed_mywater_total_discharge_cms_candidate`).

**Missingness rule: no imputation anywhere.** Complete-case within each
specification, with N reported for every fit. Daily hydrology has
`value_status = observed_from_downloaded_public_xlsx` on all 854,604 rows and no
nulls, so no daily gap-filling arises.

**Low-flow handling (R2-M02d).** The τ panel carries `tau_robustness_flag` with
three levels. Counts on the 144 analysis weir-years are fixed at freeze time:
`robust_candidate_no_low_flow_flag` 115, `contains_near_zero_or_nonpositive_discharge`
27, `mean_daily_tau_sensitive_to_low_flow` 2. Sensitivity **S4** drops the 29
flagged weir-years.

## 5. Covariate construction (fixed before fitting)

All covariates are built at weir-year level from the frozen daily sources, over
the **same window as the outcome**: calendar year for `annual_all_samples`,
June–October for `bloom_season_06_10`.

| Name | Construction |
|---|---|
| `discharge_cms` | mean of `총방류량 (CMS)` over positive-discharge days in the window |
| `log_discharge` | `log(discharge_cms)` |
| `storage_mcm` | mean of `저수량 (MCM)` over the same positive-discharge paired days |
| `log_storage` | `log(storage_mcm)` |
| `water_level_m` | mean of `수위 (EL.m)` over all days in the window |
| `rainfall_mm` | sum of `강우량 (mm)` over the window |
| `water_temp_c` | mean of in-situ `water_temperature` over the window, by weir |
| `inflow_cms` | mean of `총유입량 (CMS)` — **diagnostic only, never a model term** |

Every covariate is z-standardized within the estimation sample before entering a
model, matching the outcome treatment.

**Structural collinearity, declared in advance.** By construction
`log(tau_days) = log_storage − log_discharge − log(86400/1e6)` at the annual bulk
level. Therefore `log1p_tau`, `log_storage` and `log_discharge` are close to
linearly dependent, and any model containing all three is near-singular **by
arithmetic, not by accident**. This is disclosed, quantified with VIF, and drives
the specification design in §6 — it is not something to be discovered later and
explained away.

## 6. Specifications

Outcome throughout: `outcome_std`, the within-endpoint z-standardized
`log1p` mean of the endpoint. Stacked frame = 144 cyanobacteria rows + 144
chlorophyll-a rows = 288.

The quantity of interest is the **endpoint contrast**: the coefficient on
`log1p_tau × cyano`. A weir-year covariate entering additively cannot change that
contrast, so every covariate also enters **interacted with the endpoint
indicator**. Anything less would not test the reviewer's concern.

### PRIMARY (one specification, chosen now)

**P — discharge- and temperature-adjusted stacked contrast, annual scope:**

```
outcome_std ~ log1p_tau + cyano + log1p_tau:cyano
            + log_discharge + log_discharge:cyano
            + water_temp_c + water_temp_c:cyano
            + weir FE + year FE
cluster = weir ;  target coefficient = log1p_tau:cyano
```

Rationale: discharge is literally the τ denominator and is the reviewer's named
confound; temperature is the other covariate with same-support in-situ coverage.
Storage is deliberately **excluded** from the primary because adding it alongside
τ and discharge reconstructs τ exactly (§5).

### SECONDARY sensitivities (all pre-listed; none may be added later)

| ID | Specification |
|---|---|
| S1 | PRIMARY + `log_storage` and `log_storage:cyano` — expected near-singular; VIF reported |
| S2 | **Decomposition**: drop τ entirely; `log_storage + log_storage:cyano + log_discharge + log_discharge:cyano` + FE. Tests whether the contrast is storage-driven, discharge-driven, or both |
| S3 | Per-endpoint adjusted slopes: `outcome_std ~ log1p_tau + log_discharge + water_temp_c + weir FE + year FE`, fitted separately for cyanobacteria and chlorophyll-a |
| S4 | PRIMARY restricted to the 115 weir-years without a low-flow flag |
| S5 | PRIMARY with `water_level_m` and `water_level_m:cyano` instead of `log_discharge` |
| S6 | PRIMARY + `rainfall_mm` and `rainfall_mm:cyano` |
| S7 | PRIMARY re-fitted on `bloom_season_06_10` with bloom-window covariates |

### M06 basin-preserving inference

Reproduce, with the vendored module and fixed seed:
1. weir+year stacked interaction, τ permuted within `year` (baseline);
2. weir + basin-by-year FE stacked interaction, τ permuted within `river::year`;
3. per-outcome basin-by-year slopes.

Both season scopes. Compared against the frozen targets in §2.

### Inference

- Intervals: weir-clustered, cluster unit = `weir_name`, 16 clusters.
- Randomization inference: permute `tau_days` within `year` (primary) or within
  `river::year` (basin-preserving), `N_PERM = 4999`, seed `20260630`. Covariates
  are held fixed while τ is permuted — τ is the exposure under test.
- Small-cluster caveat: 16 clusters, 4 basins. Clustered normal-approximation
  p-values are secondary to randomization inference, consistent with the
  manuscript's own Supplementary §S7 hierarchy.

## 7. Reproduction gate (must pass before any adjusted result is reported)

The vendored module must reproduce, to `atol = 1e-9` on point estimates:

| Quantity | Target |
|---|---|
| annual stacked interaction, weir+year FE | `0.887440253669714` |
| bloom stacked interaction, weir+year FE | `1.0350637385933135` |
| annual cyanobacteria slope | `0.6874057079174496` |
| annual chlorophyll-a slope | `0.14757774021651276` |
| bloom cyanobacteria slope | `0.6186412520414742` |
| bloom chlorophyll-a slope | `0.3216193241323556` |
| stacked N | 288 (144 original weir-years) |

If any point estimate fails to reproduce, **the run halts** and P2b reports a
reproduction failure rather than adjusted results (§9).

## 8. Expected falsifying observations (pre-committed)

The claim under test is that the cyanobacteria-minus-chlorophyll-a residence-time
contrast is not merely a low-flow artefact. It is **falsified or redirected** if
any of the following is observed in the PRIMARY specification:

- F1 — the `log1p_tau:cyano` coefficient **changes sign**;
- F2 — its weir-clustered 95% CI includes zero **and** its randomization p > 0.05;
- F3 — in S2, the contrast loads on `log_discharge` with the τ-implied sign
  pattern absent, i.e. the differential is a pure discharge effect;
- F4 — the PRIMARY cannot be estimated because VIF on `log1p_tau` exceeds 10,
  in which case that specification is declared uninterpretable and the
  decomposition S2 becomes the reported evidence.

If F1 or F2 fires, the verdict is `WEAKENS_OR_REDIRECTS` and it is reported
prominently. **No further specifications may be tried to recover the result** —
the list in §6 is closed.

## 9. Halt conditions

The run halts and reports instead of continuing if:

- H1 — the reproduction gate (§7) fails on any point estimate;
- H2 — any join loses more than 10% of the 144 weir-years;
- H3 — water-temperature coverage falls below 90% of weir-years (then temperature
  moves out of the PRIMARY into a reduced-support sensitivity, and this is stated);
- H4 — a covariate cannot be constructed from the frozen sources without an
  undocumented assumption;
- H5 — the record funnel for `R2-m03a` cannot be closed against the manuscript's
  stated counts. In that case the discrepancy is reported as an unresolved
  numerical inconsistency, **not** silently reconciled.

## 10. Exclusions, decided now with reasons

- **Nutrients are excluded.** The only candidate,
  `research_execution/03_validation/nier_water_quality_2018_2025_bloom_station_screen_v2.csv`,
  covers 86 stations on a **different monitoring network** with no validated
  spatial/temporal crosswalk to the 16 algae-alert stations. Joining it would
  silently change the estimand and the support. This is a **stated exclusion with
  a reason**, not a deferred task.
- **No stage-storage curve is used or implied.** No rating curve, curve
  identifier, or stage-to-storage conversion table exists anywhere in the
  inspected trees. Storage is the directly observed MyWater `저수량 (MCM)` value.
- **Inflow is diagnostic only.** `총유입량` is reported for transparency about what
  "discharge" means but never enters a model, because the τ denominator is outflow.

## 11. Outputs this run will produce

- `03_analysis/code/P2b/` — vendored module + runnable scripts
- `03_analysis/output/P2b/` — machine-readable estimates, sample accounting, logs
- `03_analysis/output/M2_covariates.md`
- `03_analysis/output/M6_basin_inference.md`
- `99_admin/reports/P2b_REPORT.md`

No manuscript or response file is edited. No Stop-gate marker is created.
