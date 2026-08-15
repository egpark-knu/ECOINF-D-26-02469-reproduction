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
The small P2e pair-level derived inputs are redistributable and included so the
exact sign-flip and Student-t reconciliation can be recomputed rather than
checked only against a final result table.
The earlier rejected public commit remains in normal Git history because the
repair was additive and did not rewrite history.
