# P2d frozen protocol — M5/M8/M9

- Protocol ID: `P2d_v1`
- Worker turn: `T1_codex1_983b5b`
- Frozen before any new M5 comparator, M8 correlation, or M9 model result.
- Runtime: `/Users/eungyupark/anaconda3/envs/mas/bin/python3.12`
- Seed: `20260815`
- Allowed writes: only the paths named in `P2d_task_packet.md`.
- Historical and original trees are read-only.

## Source identities fixed before analysis

| Source | SHA-256 |
|---|---|
| `P2d_task_packet.md` | `d03800cea9c8be5552e14bff3bb14953cbc299e81628b4eb68db75c58d0c926b` |
| `comment_ledger.csv` | `5c55ed42f8dd264e44436208de334c22f8c9858691be46935a34a1e0945708cd` |
| `revision_strategy.md` | `50b25d2f0a4a21ab76b3007e779b7d8048fe5a35c28a9f9db4a8931429a17506` |
| `critical_path.md` | `8b7194a645e93c49aa7913df4d7cb53c8c608fb4040aa7eb28cb14b5b58f2a7b` |
| `P1_REPORT.md` | `47f3d0dafa66441c947842fdb83254dd7eebfa623846b80434053a9d0065819b` |
| `analysis_source_inventory_codex1.md` | `815cd969bd93ff116a4808975837a34174c6c24c77f391c8ea3cbcb45399498c` |
| `cyanobacteria_panel.csv` | `c958efe78888e8a0866c8cf3ab0c06ee74724c84e049feb8dc95126d3f952e2b` |
| `insitu_annual_analysis_panel.csv` | `83fcf10f4a8b06b2adb0d09370321f1b24bb150fb5be9d0b19e9d487aa1039e7` |
| `gate0_trajectory_2017_2025.csv` | `221e287d6bb76404b5d3311897a23fc0a734bc8b85447fb9c031a90024a795ac` |
| `gate0_trajectory_verification_20260630.md` | `2397e31e1a46751f97956cf69f16c40daf9424e6d411847a586a8ded2ea8ed54` |
| `weir_operation_event_candidates.csv` | `3d5e153d8da4c7aa9b34b3018c0c6547ab3d5f74b277791e18777e6f25dd0fd2` |

Additional chronology and historical-comparator sources are recorded with current
paths and hashes in the generated `source_manifest.json`; an inventory path that
does not exist is never silently substituted.

## Global rules

1. Each branch has its own support, estimand, verdict, and blocker.
2. No branch may inherit favorable evidence from another branch.
3. All result-affecting missingness is reported. No imputation is allowed.
4. Cluster means, resamples, and signs are shared across all variables/endpoints in
   the same comparison. Row-wise independent endpoint resampling is forbidden.
5. Primary and sensitivity roles below cannot change after results are known.
6. Two-sided tests use alpha 0.05. Primary families use Holm adjustment where
   explicitly stated.
7. A nonfinite estimate, rank-deficient design, failed convergence, missing cluster,
   hash mismatch, or unsupported path mutation halts the affected branch.

## M5 — chronology and event-time eligibility

### Target

Post-2017 gate-opening event time for in-situ biological outcomes. The 2012
construction event is the wrong intervention and is excluded.

### Chronology acceptance rule

A new event-time/pretrend model is allowed only if the local primary-record packet
supports all of the following before outcomes are inspected:

1. every included weir has an exact-day first meaningful opening/treatment date;
2. subsequent closure, reopening, recovery, and target-level changes are resolved
   sufficiently to assign every 2017–2025 weir-year to a treatment/event-time state;
3. source conflicts are adjudicated rather than averaged or selected for convenience;
4. the design contains pre-treatment support and within-basin treated/comparison
   variation; a Geum/Yeongsan-treated versus Han/Nakdong-control contrast alone is
   not accepted as event-study identification;
5. at least two pre-event and two post-event annual observations exist for each
   included treated weir.

If any criterion fails, M5 event study and parallel-trend test receive
`VERDICT: AXIS_EXHAUSTED`. The report must list the exact files, source coverage,
unresolved weirs/years, conflicts, and why no in-scope source resolves them.

### Historical late-post comparator

Regardless of chronology eligibility, retain the already-defined comparator only:

- groups: five `documented_opened_examples` versus the other eleven legacy
  comparison/unresolved weirs;
- baseline: 2017; immediate comparator: 2018; late comparator: 2019–2025;
- seasons: annual and June–October;
- outcomes: `log1p_harmful_cyanobacteria_total_mean` and
  `log1p_chlorophyll_a_mean`;
- statistic: difference in mean changes relative to 2017;
- provenance: historical Round 6 output is copied/reconciled by hash, not relabeled
  as a valid event-time estimator.

No new causal p-value is attached to this comparator. Its five-versus-eleven,
unresolved-control, and cross-basin limitations remain visible.

## M8 — dependent NDCI correlations

### Scope resolution

The task packet's phrase “residence-time correlations” conflicts with reviewer
R2-M08a/b, the ledger, and the named n=142 proxy panel. The primary M8 question is
therefore frozen exactly as the reviewer stated: compare NDCI–chlorophyll-a with
NDCI–harmful-cyanobacteria correlations on shared observations. Residence time is
not substituted for NDCI.

### Support and variables

- primary season: `annual_all_samples`;
- prespecified secondary season: `bloom_season_06_10`;
- common support requires finite `ndci_mean`,
  `log1p_harmful_cyanobacteria_total_mean`,
  `log1p_chlorophyll_a_mean`, `weir_name`, and `year`;
- expected support is 142 shared weir-years and 16 weirs per season; deviation halts.

### Statistics and dependence

- primary correlation: Spearman rho, chosen before diagnostics because NDCI is
  bounded and the ecological relationship need only be monotone; Pearson is a
  labeled sensitivity, not a replacement;
- primary contrast:
  `Delta = rho(NDCI, chlorophyll-a) - rho(NDCI, cyanobacteria)`;
- cluster-aware test: delete-one-weir jackknife pseudo-values followed by an exact
  two-sided studentized Rademacher sign-flip over all `2^16 = 65,536` patterns;
- paired weir-cluster bootstrap: 9,999 draws, sampling 16 weirs with replacement;
  every draw retains NDCI and both outcomes together and is saved;
- interval: percentile 2.5/97.5 percentiles from the paired cluster bootstrap;
- no multiplicity adjustment is applied to the one annual primary contrast;
  Bloom is secondary.

### Decomposition and diagnostics

- pooled: correlation across shared weir-years;
- within-weir: correlation of each variable after subtracting its weir mean;
- between-weir: correlation of the 16 weir means;
- report Spearman and Pearson for each component and endpoint, plus their
  chlorophyll-minus-cyanobacteria difference;
- diagnostics: Shapiro W/p and skewness for the three pooled variables, Pearson
  versus Spearman divergence, and linear-versus-quadratic unclustered R-squared as
  relationship-form descriptors only.

### Verdict rule

- `SUPPORTS` if annual Spearman `Delta > 0` and exact cluster-aware p < 0.05;
- `WEAKENS_OR_REDIRECTS` if `Delta > 0` but p >= 0.05, or if the annual Spearman
  decomposition meets the prespecified spatial-dominance flag:
  `abs(within Delta) < 0.5 * abs(pooled Delta)` and
  `abs(between Delta) > abs(within Delta)`;
- `AXIS_EXHAUSTED` if the common-support or cluster test cannot be formed.

## M9 — two-part harmful-cyanobacteria outcome

### Source, support, and units

- filter raw `cyanobacteria_panel.csv` to
  `variable == harmful_cyanobacteria_total` and
  `source_field == iemBgalageCellCo`;
- source unit must be exactly `Cells/100mL`; it is preserved as reported;
- join one finite positive `tau_days` per `weir_name` × `sampling_year` from the
  annual-scope analysis panel;
- require unique `station_code` × `sampling_date` × `variable`; duplicates halt;
- values below zero halt; missing outcome/date/weir/year/month/tau are reported and
  excluded without imputation;
- occurrence is `value > 0`; positive magnitude is `ln(value)` among `value > 0`.

The alert-threshold branch R2-M09c is blocked. No conversion between
`Cells/100mL` and threshold language in `cells/mL` is assumed. Presence and
within-source positive magnitude do not require that conversion.

### Windows and primary models

- primary bloom window: June–October (`6,7,8,9,10`);
- prespecified sensitivities: May–October, July–September, and annual months 1–12;
- exposure: `log2(tau_days)`, so coefficients are per residence-time doubling;
- occurrence part: binomial logit with weir, year, and calendar-month fixed effects;
- positive part: OLS for `ln(value)` with the same fixed effects;
- primary support uses every eligible observation in June–October;
- primary inference: CR1 sandwich covariance clustered by 16 weirs, two-sided
  t reference with 15 df;
- primary occurrence/positive p-values form a two-test Holm family;
- paired cluster bootstrap: 1,999 weir-resampling draws for the two June–October
  primary coefficients, with percentile intervals and every draw saved.

Logit uses deterministic IRLS (maximum 100 iterations, coefficient tolerance
`1e-10`). Nonconvergence, separation/nonfinite weights, a rank-deficient design,
or a nonpositive clustered SE halts the affected model.

### Calendar balance and sampling protocol

- report counts by weir-year and weir-year-month, zeros, positives, missingness,
  and coefficient of variation/range of observed sampling frequency;
- calendar-balanced sensitivity aggregates to one weir-year-month cell:
  occurrence proportion and mean positive `ln(value)`, giving each observed month
  cell equal analytic weight; it uses the same FE and clustered inference;
- unequal timestamps cannot establish event-triggered sampling. Search the supplied
  provenance/notes for an explicit agency protocol. If none states routine versus
  event-triggered scheduling, report R2-m04b as `AXIS_EXHAUSTED` for protocol
  attribution while still reporting observed calendar imbalance.

### Effect scale and verdict

- occurrence effect: odds ratio `exp(beta)` per doubling of tau;
- positive effect: `100 * (exp(beta) - 1)` percent change in positive-count geometric
  mean per doubling of tau;
- `SUPPORTS` only if both June–October coefficients are positive and Holm p < 0.05;
- otherwise `WEAKENS_OR_REDIRECTS`, with discordant/adverse parts and sensitivities
  reported rather than replaced;
- `AXIS_EXHAUSTED` only if the primary two-part models cannot be fit from the frozen
  source. The alert-threshold sub-branch remains separately blocked regardless.

## Required saved evidence

- source manifest with hashes, sizes, mtimes, and runtime/package versions;
- chronology eligibility and source-coverage tables;
- historical M5 comparator reconciliation;
- M8 support, diagnostics, decomposition, exact sign patterns, and all bootstrap draws;
- M9 support/calendar accounting, model tables, all primary bootstrap draws, and
  explicit threshold/protocol blockers;
- verification JSON with stable PASS/FAIL gates and artifact hash ledger;
- branch reports plus `P2d_REPORT.md`, including unfavorable results.
