# withdrawn designs M9 protocol amendment v1.1 — exact source duplicates

- Amendment ID: `P2d_M9_v1.1`
- Materialized at: `2026-08-15T05:03:01Z`
- Applies only to: M9 source-ingestion duplicate handling
- Fresh certified rerun status at materialization: not started
- Base protocol content SHA-256: `cf60dc3bc4935a55ab6ed55df6e8bc67c82fa4c1136077c1efb755206057d4cf`
- Base protocol immutable copy: `withdrawn_designs_freeze.md`

## Trigger and decision chronology

The first withdrawn designs run halted M9 at the frozen unique-key gate before any M9 model was
fit. Direct source inspection found three duplicated `station_code` ×
`sampling_date` × `variable` keys (six rows). Within each pair, every scientific,
temporal, unit, provenance-snapshot, and value field was identical; only
`source_row_locator` differed, as adjacent item locators within the same saved raw
API snapshot. The affected keys were:

- `3012A07` × `2019-06-24` × `harmful_cyanobacteria_total` (both value 0);
- `3012A42` × `2019-06-24` × `harmful_cyanobacteria_total` (both value 0);
- `5004A35` × `2020-02-18` × `harmful_cyanobacteria_total` (both value 0).

The repair rule was selected from this source-only audit. No M9 coefficient,
standard error, p-value, sign, effect size, fitted probability, or other M9 outcome
was available or inspected when the duplicate-repair decision was made. A later
nonconvergence status is not a basis for, and does not alter, this amendment.

## Deterministic source-locator-only deduplication

Replace only the base protocol sentence `duplicates halt` with this narrow rule:

1. Duplicate measurement keys still halt unless `source_row_locator` is present.
2. For each duplicate key, compare every column other than the key fields and
   `source_row_locator`, treating missingness as a value. Any difference halts M9.
3. If and only if all compared fields are identical, sort the pair/group by
   `source_row_locator` lexicographically, retain the first row, and record the
   number removed. Thus the sole allowed distinction and deterministic tie-breaker
   is the source locator; no outcome, exposure, model, or favorable-result rule is
   consulted.

All negative-value, unit, missingness, join, model, convergence, covariance,
bootstrap, and verdict gates in the base protocol remain unchanged. In particular,
separation or deterministic-IRLS nonconvergence still halts the affected M9 model,
and inability to fit the primary two-part models yields M9 `AXIS_EXHAUSTED`.

## Branch isolation and provenance

M5 and M8 protocols, already-computed results, estimands, diagnostics, random seeds,
and verdict rules are unchanged. This amendment must never be represented as
predating those M5/M8 analyses. M5 and M8 are verified against the base SHA
`cf60dc3b…`; the fresh M9 branch is verified against both that base SHA and this
amendment's independently recorded SHA.

The immutable base copy was materialized after the earlier M5/M8 run, but its bytes
match the base SHA recorded by the pre-result first-run source manifest. File mtime
is therefore not used to claim that the copy itself predates M5/M8. The fresh run's
source manifest and artifact ledger record the base and amendment as separate
records with separate paths, full hashes, sizes, and mtimes. The amendment cannot
self-embed its own final hash without changing it; its hash/mtime are consequently
recorded externally and checked before the fresh rerun.
