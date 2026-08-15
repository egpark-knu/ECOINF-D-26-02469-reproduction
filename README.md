# Reproducibility Deposit: Ecological Informatics (ECOINF-D-26-02469)

This repository contains the final derived data, code, frozen protocols, and
verification evidence for the revision analyses. It packages only the final
P2a, P2b, P2c v4, P2d, and P2e branches. Third-party bulk raw data are not
redistributed; see `DATA_AVAILABILITY.md` and `THIRD_PARTY_NOTICES.md`.

## Included-data verification

The release verifier uses only the Python standard library and checks the
manifest, portable-tree contract, final-run selection, schemas, counts, gate
statuses, and submission-facing numerical values:

```bash
python3 verify_public_release.py --root .
shasum -a 256 -c MANIFEST.sha256
python3 -m unittest discover -s tests -v
```

These commands verify the deposited results. They do not download restricted
raw inputs or claim to recreate the raw-data acquisition stage.

## Analysis environment and packaged tests

The package was tested with CPython 3.12.13 and the bounded versions in
`requirements.txt`.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m unittest discover -s code/P2a_M1/tests -v
python -m unittest discover -s code/P2c/tests_v4 -v
python -m unittest discover -s code/P2d/tests -v
python code/P2e/test_signflip.py
python code/P2e/reproduce_signflip.py
python code/P2e/reconcile_secondary_ci.py

python -m compileall -q code verify_public_release.py tests
python -c "import ee, matplotlib, numpy, pandas, PIL, pyproj, scipy; import verify_public_release"
```

The unit tests use deposited derived data or synthetic fixtures. The
`code/legacy_audit/` script is retained for historical method inspection but is
excluded from executable import testing because its original external source
tree is not distributed; it is still syntax-checked by `compileall`.

## Reproduction levels

### P2a from included analysis-ready data

P2a can be recomputed from the included 288-row panel. Output and log roots must
be fresh descendants of the allowlisted repository-relative directories.

```bash
mkdir -p reproduction_output/P2a_M1/runs reproduction_output/P2a_M1/logs
python code/P2a_M1/run_m1_reconciliation.py \
  --protocol protocols/M1_protocol_v1.json \
  --freeze protocols/M1_freeze.md \
  --legacy-module code/P2a_M1/vendor/hardening_specificity_analysis__c895385a.py \
  --panel data/insitu_annual_analysis_panel.csv \
  --output-root reproduction_output/P2a_M1/runs/manual_001 \
  --log-root reproduction_output/P2a_M1/logs/manual_001 \
  --seed 20260630 --legacy-n-perm 4999 \
  --wcr-sign-patterns 65536 --cluster-bootstrap 9999
```

### P2e from included derived source inputs

The small, redistributable pair-level inputs needed by P2e are included under
`data/P2e/source_inputs/`. The three P2e commands above rerun the exact
assignment sign-flip analysis, exercise the original `variant_values` filters
and pair-set equality check, and independently reproduce the Student-t
secondary intervals. Outputs are written under ignored
`reproduction_output/P2e/` by default.

### Full raw-input reruns

P2b, P2c v4, and P2d retain their exact analysis code, but their full
reruns require raw or historical inputs that cannot be redistributed. Acquire
those inputs from the official sources and recreate the logical layout
described in the frozen protocols and branch source manifests. Then provide
source roots through `P2B_SOURCE_ROOT`, `P2C_SOURCE_ROOT`,
`P2C_REVISION_ROOT`, `P2C_PACKET_ROOT`, or `P2C_AUXILIARY_ROOT`, as
applicable. Output locations can be set with `P2B_OUT`,
`P2D_OUTPUT_PARENT`, and `P2D_RUNS_ROOT`. `P2E_SOURCE_ROOT` may optionally
override the included P2e source-input subtree, and `P2E_OUT` changes its
output directory.

The optional Sentinel-2 acquisition route is:

```bash
export GEE_PROJECT="your-project-id"
# For service-account authentication only:
# export GEE_SERVICE_ACCOUNT="service-account-name"
# export GEE_KEY_PATH="path/to/local-key.json"
python code/extract_round5_s2_indices.py
```

No authentication value is stored in this repository. Historical machine-local
provenance was sanitized as documented in `PROVENANCE_SANITIZATION.md`.

## Directory map

- `data/`: final derived analysis-ready inputs and outputs.
- `code/`: analysis, verification, and tests.
- `protocols/`: frozen analysis protocols with public provenance labels.
- `verify_public_release.py`: deterministic release-level verifier.
- `MANIFEST.sha256`: hashes for every package file except the manifest itself.
