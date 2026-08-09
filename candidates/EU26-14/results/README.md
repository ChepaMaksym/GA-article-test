# EU26-14 generated evidence

Generated reports are intentionally not required for ordinary unit tests.
`run_artifact_verification.py` writes a create-only JSON report after every
identity and endpoint gate passes. The automatic pull-request full-integration
job uploads the Python, Octave, and bound cross-language reports without
committing the 318 MB input archive. Downloads are bounded before the verifier
enforces exact complete-file sizes and hashes.

The committed fixtures are the small, reviewable evidence surface:

- `../fixtures/frozen_endpoint.json`;
- `../fixtures/run0_cycles.csv`.

Their bytes are regenerated only from the complete-hash-authenticated archive
and the no-execution safe parser; ordinary verification compares rather than
overwrites them.
