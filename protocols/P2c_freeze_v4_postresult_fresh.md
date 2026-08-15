# P2c v4 post-result fresh implementation freeze

- Protocol ID: `P2c_v4_postresult_fresh_20260815`
- Original execution identifier: `[sanitized for public release]`
- Frozen at UTC: `2026-08-15T05:37:34Z`
- Runtime: `python3`
- Random seed: `20260815`
- Paired weir bootstrap draws: `3000`
- Status: **post-result exploratory corrective analysis; not confirmatory validation**
- v3 is quarantined failed evidence and is not an input, template, or numerical source.
- This document precedes every v4 result. Source/schema inspection preceded the
  freeze; no v4 statistic, matchup, map, or report was generated before it.

## Steering recorded before v4 result generation

At `2026-08-15T05:35:33Z` (`2026-08-15T14:35:33+0900`), the pre-release audit replaced the
v4 task packet before any v4 output existed. The current packet removes invalid
v2 numerical anti-fabrication expectations after independent inspection showed
that the v2 matchup code mixed unrelated raw variables into both endpoint values.
This freeze therefore binds the updated packet identity below. The prior packet
identity is superseded and is not a protocol source for v4.

The old `754` match count, `233` zero count, and every v2 endpoint association
are invalid downstream diagnostics rather than expected v4 values. v4 must use
the exact raw endpoint filters frozen below. Changed counts and associations are
reported as the necessary consequence of that correction, not treated as a
failure to reproduce invalid diagnostics.

## Reviewer target and claim boundary

The direct targets are Reviewer 2 major comments 3–4 and Reviewer 1 comment 8:
near-coincident same-day/±1–3-day satellite–field matchups, temporal-window and
cloud-filter accounting, spatial extraction/offset documentation, pairing confidence,
independent location-verification attempts, usable observation frequency, and a
study-area map. Results are weir-reach-scale temporally matched associations. They
are not point ground validation, proof of measured co-location, or evidence of
hydrologic non-connection.

The fixed endpoint conclusion is `not_robust` unless all three mandatory NDCI
specifications have a positive chlorophyll-minus-cyanobacteria contrast and every
paired 95% interval excludes zero. Directional agreement without inferential support
in all three does not authorize endpoint superiority. FAI is secondary and receives
no endpoint-superiority conclusion regardless of its estimates.

## Frozen sources and identities

| Source role | Required schema/content | SHA-256 |
|---|---|---|
| v4 task packet | updated full v4 requirements; supersedes pre-steering packet | `46ff6f8f3f8239e6f711b2e93a1d07b916499542dff2eabb4bbd3d6f64b9084f` |
| v3 fixed-design packet | bounded estimator/map/semantic design | `440a99a55a37fa80551c51fce638499ae180145266ab559497d9188dd2a76434` |
| three-round debate | six turns and synthesis | `9b435d140c6ad826f7746605d751dfa6d490ac8c7ed410fdfef06ea57d2fa2bc` |
| rejected-v3 audit | quarantine decision and rejected hashes | `f534e74df7d9b386cb43a2245b22f9caba7659657f59e069005085bc14d65e69` |
| reviewer comments | verbatim R1-08 and R2-M03/M04 | `0e3c4954457344ad66e14ccdff0c63d67afc0d5f07f8353c41a2397a19279522` |
| comment ledger | P2c ownership/action rows | `12a467e7f91346d7184f4015784f1a4d63cc9f5d37bde00383504a5c66bc2fd4` |
| official archive note | official early-L2A context; no local causal attribution | `f15940b3db06d69aba27123fdb174265806fd6108ec3ecec55b0671f255d43bf` |
| v2 scene export | 1,949 rows; 14 named fields below | `0e195ca3648a34b4f55858e5df9864075f4aa75a909d841c28f99d37c74e37cc` |
| v2 observation-frequency diagnostic | 144 rows; comparison only | `f68ab22e0af28463669bd71f7cdb25f379e11a9740f88fff87b6718cf1d43345` |
| v2 scene export code | extraction/mask audit only | `06689a7504cf7f80ba310c34eea88954f6bb0620ed553121caea76602b73f7ac` |
| v2 matchup code | defect audit only; no statistic is reused | `389aaa1fc04b6b2ac60a23145253a86df3664100703ae473f25e5009632e703d` |
| v2 map code | map-defect audit only | `012106602b813143d4bca48dcbd7cb2ff9676f4f9ec083f9609524d106db32ee` |
| raw cyanobacteria panel | exact endpoint fields below | `c958efe78888e8a0866c8cf3ab0c06ee74724c84e049feb8dc95126d3f952e2b` |
| raw chlorophyll panel | exact endpoint fields below | `8a9acfd0828d5f4d441ded7caa1706ccd980e16417467a58c13d8006765f5f49` |
| station–reach closure v6 | 32-row final direct-validation closure | `e573503ef24115a51e845931f9cb0e2268d98fa2cbe255d5a31dba3d33ad4633` |
| weir inventory | 16 weirs, Korean/English names, river, lat/lon | `fd75caa126fc4921b9ee602791f1c77474e0989e9a4bde751f99d82527683bd4` |
| control reaches | 16 named controls with lat/lon/context | `a8bf63ec39a6b28dda7bd36a25defca30e3f0ec048b0c1e57fda555f889db64a` |
| HydroRIVERS map cache | 845 mainstem records, lon/lat segments | `9e1437f9b45f624ab8a4cb598a081b407ff26481e209da093f94110f2dd95935` |
| Natural Earth countries | GeoJSON country boundaries | `239eec57ac17f100a11e2536cffc56752c318b50ae765b0918ff7aab4ce8f255` |
| HydroRIVERS technical documentation | v1.0 licence/citation | `4afcdb2b54b93793a0196c2795ffe8ba6e7364a2ef31ecc2f783a7dd3b5df573` |

The v2 scene schema must contain `year,date,utc_timestamp,scene_id,PRODUCT_ID,
MGRS_TILE,collection_id,site,weir_name_kr,CLOUDY_PIXEL_PERCENTAGE,ndci_mean,
ndci_count,fai_mean,fai_count`. Collection, product/scene, tile, acquisition time,
site, both index means, and index-specific counts must be nonblank/finite as
appropriate. Counts must be positive. A duplicate
`site × date × scene_id × PRODUCT_ID × MGRS_TILE` identity halts.

Both in-situ panels must contain `station_code,station_name,weir_name,sampling_date,
variable,source_field,value,unit,source_row_locator,raw_snapshot_sha256`.

## Frozen endpoint correction and in-situ construction

The v2 matchup script is not a valid endpoint constructor: it averaged all five
cyanobacteria variables into `cyano_value` and chlorophyll, water temperature,
dissolved oxygen, pH, transparency, and turbidity into `chla_value`. Therefore its
754/233 downstream diagnostics are anti-fabrication context, not v4 targets.

v4 filters exactly:

- cyanobacteria: `variable=harmful_cyanobacteria_total`,
  `source_field=iemBgalageCellCo`, `unit=Cells/100mL`;
- chlorophyll: `variable=chlorophyll_a`, `source_field=iemChla`, `unit=mg/m3`.

For each endpoint, duplicate `station_code × sampling_date × variable` keys halt
unless every field other than `source_row_locator` is identical. Exact API duplicate
items are sorted by locator and the first retained; the number removed is reported.
Conflicting duplicates, negative values, unexpected units, or invalid dates halt.
Missing endpoint values remain missing. After exact deduplication, endpoint values
are averaged only within `weir_name × sampling_date`; counts, station codes, and
source-row locators are retained. Transformations are `log1p(chlorophyll_a)` and
`log1p(harmful_cyanobacteria_total)`. Exact zero is described only as zero. The
terms censor, censored, detection limit, LOD, below detection, and equivalent assay
interpretations are forbidden because assay metadata are absent.

## Same-date satellite composite

For index `j` in NDCI/FAI and site-date group `g`, with component value `x_jk` and
its own valid-pixel count `n_jk`:

`x_jg = sum_k(n_jk * x_jk) / sum_k(n_jk)`.

NDCI never uses the FAI denominator and vice versa. Save the component row count,
scene IDs, product IDs, tiles, UTC timestamps, component values/counts, summed
valid pixels, numerator, and recomputed weighted result. Every daily identity is
rechecked; any mismatch above `1e-12` halts.

## Outcome-blind matchup rule

The observational unit is one `site × in_situ_date × window`. Create all candidate
edges between an in-situ date and daily satellite dates in the same site within the
window. Windows are:

- primary `pm1_2017_2025` (absolute lag ≤1 day);
- nested sensitivities `pm2_2017_2025` and `pm3_2017_2025`;
- restricted sensitivity `pm1_2019_2025`.

For each unit select the minimum absolute lag without consulting an endpoint value.
If multiple satellite dates share that minimum distance, aggregate all tied daily
composites symmetrically using each index's summed valid pixels. Save tied dates,
signed lags, component counts, `tie_count`, and `min_abs_lag`. The resulting pairs
must be unique by `window × site × in_situ_date`. Complete cases are formed
separately by endpoint during estimation; an endpoint's missingness cannot choose a
different satellite date.

## Fixed specifications and aggregation

All analyses are computed for NDCI and FAI against both log1p endpoints. The three
specifications are:

1. `raw_within_weir_pearson`: subtract each weir mean from predictor and endpoint.
2. `within_weir_percentile_midrank`: within each weir and variable, use average
   tied rank divided by `(n_i + 1)`. A weir-specific correlation is estimable only
   when both transformed variables vary.
3. `site_by_calendar_month_pearson`: subtract the mean within each
   `site × calendar_month` cell from each variable, then correlate. Report total
   cells, singleton cells, cells with at most two rows, and median cell size. Any
   attenuation is only `consistent with shared seasonality`, not causal evidence.

The primary aggregation is `equal_per_weir_fisher_z`: compute an eligible weir's
Pearson `r_i`, clip only for finite Fisher transformation at ±(1−1e-12), average
`atanh(r_i)` with equal weir weight, and apply `tanh`. Chlorophyll and cyanobacteria
use their own eligible weirs; paired contrasts use their common eligible weirs.
The explicit sensitivity `equal_per_observation` pools the transformed/residualized
rows with equal row weight. Its support and weighting label are always visible.

The NDCI endpoint robustness table contains every window × specification ×
aggregation with `n_rows`, `n_weirs_chla`, `n_weirs_cyano`, `n_common_weirs`, the
two common-support associations, `delta_r = r_chla − r_cyano`, paired interval,
interval-zero flag, and support status. FAI receives the same association inference
and LOO diagnostics but no endpoint-superiority verdict.

## Dependence-aware uncertainty and LOO

For each window/specification/aggregation/index/endpoint, bootstrap whole weirs with
replacement for `B=3000`, seed `20260815`. Full-support endpoint intervals resample
that endpoint's eligible weirs. Endpoint contrasts resample the common eligible
weirs once per draw and compute both associations on the same selected weirs. Save
every draw with draw number, window, specification, aggregation, index, endpoint,
full-support association, common-support association, paired contrast, support
counts, and hashes of selected weir sequences. Intervals are percentile 2.5/97.5%.
Bootstrap p-values are not computed because percentile sampling distributions are
not null distributions; tables state `p_method=not_computed_ci_primary`. Literal
`p=0` is forbidden.

Leave-one-weir-out outputs contain actual estimates for every window,
specification, aggregation, omitted weir, index, and endpoint, plus NDCI paired
contrasts on remaining common support. Non-estimable rows are explicit and never
replaced with zero or placeholders.

## Frequency, zero/support, crosswalk, and map

- `observation_frequency_v4.csv` is exactly 16 sites × 2017–2025 = 144 data rows,
  including zeros. It separately reports satellite site-dates, scene/product/tile
  components, unique products/tiles, valid-pixel sums, and temporal gap summaries.
  Years 2017–2018 carry `observed_low_coverage=true` and
  `archive_cause_verified=false`. Official global early-L2A incompleteness is
  context, not proof of the local achieved-count cause. Save a 2019–2025 accounting
  sensitivity.
- For every matchup window, save zero fraction/count, complete-case rows, 16 total
  weirs, endpoint-variable weirs, and named zero-variance weirs. Do not force the v2
  233/754 diagnostic because v2 used incorrectly mixed endpoints.
- Crosswalk must reproduce 32 total rows, 25 `exclude`, 7 `context_only`, zero
  `direct_validation_claim_allowed_v6`, and zero `directed_network_available_v6`.
  Any mismatch halts. This negative direct-validation closure is not hydrologic
  non-connection.
- Render a new map from v4 code in EPSG:5179 using 16 target-weir coordinates, 16
  sourceable controls, exact 5-km weir buffers, four-river/basin color context,
  cached HydroRIVERS mainstems, a scale bar, north arrow, readable legend/labels,
  and a South Korea locator inset from Natural Earth. Map metadata states source,
  CRS, hashes, licence/citation, and that buffers can mix upstream lentic and
  downstream lotic water. The map does not imply station-point co-location.

## Measurement limitations that remain unquantified

The scene export used `COPERNICUS/S2_SR_HARMONIZED`, global cloudiness <30%, JRC
surface-water occurrence ≥50%, QA60 opaque/cirrus bits, and 20-m reduction. It did
not use a dedicated cloud-shadow product. QA60 nominal support is 60 m while the
index reduction scale is 20 m. A 5-km cross-weir buffer may mix upstream lentic and
downstream lotic water. These are disclosed unquantified limitations, not repaired
or quantified findings. NDCI/FAI equations and bands are inherited from the audited
scene export: NDCI=(B5−B4)/(B5+B4); FAI=B8A−[B4+(B11−B4)*(865−665)/(1610−665)],
with reflectance scale 0.0001.

## Provenance, clean rebuild, semantic gates, and halt conditions

The source manifest records relative/logical source paths, SHA-256, size, mtime,
runtime/package versions, the documented relative clean command, seed/draw count,
and this freeze's hash/mtime. Submission-facing CSVs, reports, and map metadata must
contain no machine-local home path, project/account identifier, authentication material, or private orchestration workspace
path, or internal orchestration marker.

The verifier halts on any source/freeze hash drift; missing schema; duplicate or
nonpositive satellite identity/count; conflicting in-situ duplicate; negative
outcome; weighting mismatch; matchup non-uniqueness; non-minimum/tie-asymmetric
selection; fewer than two variable weirs; nonfinite estimable statistic/draw/CI;
wrong bootstrap count; missing LOO coverage; 144-row/frequency mismatch; crosswalk
mismatch; missing map feature/provenance; forbidden path/secret/semantic phrase;
placeholder pattern; absent limitation language; or missing/adverse-result report.

The primary build runs from one documented command into an empty v4 directory. A
second build uses another empty directory and identical frozen inputs. Deterministic
CSV, canonical decompressed bootstrap content, JSON scientific payloads, reports,
and map pixels are compared under declared exclusions for output-root/timestamp
provenance fields. Only a substantive named-gate verifier and a saved rebuild
comparison can set `STATUS: COMPLETE_VERIFIED_V4`.
