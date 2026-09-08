# Pre-outcome implementation and model-evidence extension

Recorded 2026-09-08, before the first scientific bridge campaign. This document
extends evidence serialization and infrastructure recovery, not the frozen
scientific protocol. `protocol.json` and `PROTOCOL.md` retain their exact bytes,
SHA-256 digests, seeds, objective, classifier, sample sizes, budget and gates.

## Seven files per paired seed

The five previously planned JSON files remain: row, CHC trace, lambda trace,
status and manifest. Two terminal `joblib` bundles are added, one per arm.
The versioned extension is `eu26-21-common-bridge-model-evidence-v1`, required
in the row and manifest. A complete campaign contains exactly 210 regular
files in 30 isolated seed artifact directories. Each manifest binds the other
six files by SHA-256 and byte length; the external GitHub artifact digest binds
the manifest as well. This extension predates all scientific seed artifacts.

Each bundle contains the terminal fitted Decision Tree, its fitted
preprocessor, selected mask and feature mapping, and implementation identity.
After both complete validation traces have been persisted, the terminal
classifier is fitted once on the internal training partition. Its fitted state
is serialized and round-tripped using only the first eight internal training
rows. Transformed values, predicted labels and probabilities must agree
exactly. This probe neither consumes search objective calls nor evaluates test
quality. The existing single official-test metric evaluation then proceeds.

Only bytes just produced in memory by the runner are deserialized. The
aggregator validates downloaded model hashes and verification records but
never loads downloaded pickle/joblib objects. Users must not deserialize
untrusted bundles. Relevant guidance: [scikit-learn model persistence](https://scikit-learn.org/stable/model_persistence.html).

Optional evidence fields and a terminal-model callback in the corrected
loader/evaluator preserve its existing return metrics and scientific behavior.
Historical result files, protocol manifests and archived source are unchanged.

## Infrastructure recovery, not outcome selection

The immutable source ledger identifies every selected artifact by seed, run
ID, attempt, artifact ID, name and digest. A failed-jobs-only rerun may retain
successful seeds from an earlier attempt of the same run and exact SHA. The
fixture is downloaded by its immutable artifact ID, not the current attempt's
name. Selection always takes the newest existing artifact for each seed;
scientific outcomes are never a selection input. A malformed newest artifact
fails validation; it cannot be replaced by an older favorable result.

The source snapshot retains an `attempt_history` including superseded artifact
identities. Its selected entries are cross-bound to each row's attempt. All
other shared provenance must remain identical. GitHub reaggregation reads the
specific recorded source run attempt, rather than silently switching to the
latest run state. Cancelled/incomplete source attempts are not eligible for
scientific evidence recovery. Retain infrastructure failure diagnostics.

The evidence tag is an exact-SHA dispatch handle, not proof of repository
ruleset protection. Authorization compares actual `github.sha` and
`github.workflow_sha` with the supplied full SHA and records whether GitHub
reports ref protection. This implementation does not change repository
security settings. Do not move the evidence tag after dispatch. Actual
workflow context, not an input echoed as evidence, supplies workflow identity.
[GitHub context reference](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts),
[rerun semantics](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs).

## Verification boundary

All execution is CI-only. The lightweight CI tests use explicitly synthetic
data and mocked external identities, exercise both real search implementations,
write the complete seven-file seed format and validate a 30-pair campaign.
These fixtures are not scientific observations. They cover mixed attempts,
missing/duplicate artifacts, corrupt model bytes, structured provenance,
transition tampering, test-access order and a negative scientific CLI result.

BCa receives an independent vectorized reference using NumPy medians/quantiles
and SciPy normal functions on the same prescribed resampling indices. Exact
threshold equality, nonfinite/degenerate inputs and quality-before-efficiency
gating have separate tests. The full quality workflow also compares bridge HUX
with the authenticated author source and RNG state. No test result is claimed
until the corresponding GitHub Actions run completes successfully.
