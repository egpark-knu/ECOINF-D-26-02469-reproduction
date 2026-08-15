# M4 — Spatial extraction and station–reach context

STATUS: COMPLETE_VERIFIED_V4

The v4 map was rendered offline in EPSG:5179 from 16 target-weir coordinates,
16 sourceable upstream controls, 845 cached
HydroRIVERS records (845 plotted segments), and a
Natural Earth Republic of Korea locator. Each target has an exact 5,000-m projected
buffer, scale bar, north arrow, label, four-river color context, and a dotted link to
its sourceable control.

The buffers are extraction context, not station-point co-location. A 5-km
cross-weir buffer can mix upstream lentic and downstream lotic water. Control links
also do not imply confirmed directed-network connection.

The final station–reach closure contains 32 rows:
25 `exclude`,
7 `context_only`,
0 direct-validation eligible, and
0 directed-network-confirmed. This is a
negative direct-validation closure, not proof of hydrologic non-connection.

Map source identities, CRS, licenses, hashes, and claim boundaries are recorded in
`study_area_map_sources_v4.md` and `source_manifest_v4.json`.

## Verification execution

- `python -m unittest discover -s tests_v4 -v`: PASS, 13 tests.
- `python v4_build.py --out-dir ../../output/P2c/v4`: PASS; 3,965 matchup rows, 288,000 bootstrap rows, and 1,536 LOO rows.
- `python v4_build.py --out-dir ../../output/P2c/v4_clean_rebuild`: PASS with the same row counts from another empty directory.
- `python v4_finalize.py --primary ../../output/P2c/v4 --rebuild ../../output/P2c/v4_clean_rebuild`: PASS; 17 named gates and 17 byte-identical built artifacts.

