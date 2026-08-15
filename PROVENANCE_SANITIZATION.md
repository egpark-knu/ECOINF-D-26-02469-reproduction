# Public provenance sanitization note

The final scientific outputs were produced before public packaging. During the
public-release repair, machine-local provenance fields were replaced with stable
logical labels such as `source-root/...`, `historical-source/...`, or paths
relative to this repository. Private execution identifiers and local runtime
locations were also removed.

This textual sanitization did not change reported estimates, uncertainty
intervals, p-values, sample counts, verdicts, seeds, or historical source
SHA-256 values. Branch-local hash ledgers remain records of the original final
run and therefore are not current-file checksums after provenance text was
sanitized. `MANIFEST.sha256` is the authoritative checksum ledger for this
public tree, while `verify_public_release.py` checks the scientific values and
final gate states.

In particular, the included 288-row annual/bloom panel has the same values and
schema as the frozen analysis input, but its two source-snapshot provenance
columns use logical relative paths. Its public-file checksum therefore differs
from the original-run checksum; both identities are tested and documented.

Only final runs are packaged. Third-party raw inputs remain outside the public
tree under the redistribution boundaries described in `DATA_AVAILABILITY.md`.
The small sampling frame pair-level derived inputs are redistributable and included so the
exact sign-flip and Student-t reconciliation can be recomputed rather than
checked only against a final result table.
The earlier rejected public commit remains in normal Git history because the
repair was additive and did not rewrite history.

## Directory naming (Phase R)

Analysis branch directories were renamed from internal phase identifiers to
content-based names, and the release scanner was extended to keep them out:

Each branch directory appears under both `code/` and `data/`.

| Former branch identifier | Directory name now used |
|---|---|
| first-stage reconciliation branch | `m1_reconciliation` |
| hydrologic robustness branch | `hydrologic_robustness` |
| near-coincident matchup branch | `matchups` |
| withdrawn-design branch | `withdrawn_designs` |
| sampling-frame branch | `sampling_frame` |

Frozen protocol documents, verifier gate names, environment variables, and
module filenames were renamed to match.

### Deliberately preserved

These are records, not repository structure, and were left byte-exact so the
deposit does not misstate its own history:

- **Contents of `data/`.** Only the location of these files changed. Their bytes
  are identical to the previously published commit, including recorded upstream
  paths such as the recorded upstream analysis-code paths and the
  frozen artifact name `data/matchups/v4/reports/P2c_REPORT.md`, which is pinned
  by hash in `clean_rebuild_comparison_v4.json`.
- **`code/m1_reconciliation/vendor/`.** A verbatim copy of the submitted
  pipeline, hash-pinned at
  `29f46b586460bf478e1c512683cdb07ce6e6b6f5b53a85857e2ba2967a1a833f` and checked
  at import. Its internal names were not edited.
- **Frozen protocol and amendment identifiers** such as `P2a_M1_v1`, `P2d_v1`,
  and `P2c_v4_postresult_fresh_20260815`, which label the protocol version that
  produced the reported numbers.

The release scanner's phase-directory pattern is therefore scoped to
repository-root paths (`code/…`, `reproduction_output/…`) and does not flag
recorded upstream provenance.
