# Bridge infrastructure recovery ledger

## 2026-09-08: artifact extraction layout, before optimizer execution

The first manual dispatch was
[run 34192825801](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34192825801),
attempt 1, commit `0e682ceaac461285c2140f5b3f369f49e8ff3f80`, tag
`eu26-21-common-bridge-evidence-v1`. All three required implementation CIs
were green before dispatch. The authorization and shared fixture jobs passed.

Seed job `101954385190` failed at `Verify and restore authenticated fixtures`:
`archive.sha256` was absent at the expected root. Its download log shows the
single artifact ID was extracted into an additional artifact-name directory.
The optimizer step was skipped. This is infrastructure-invalid evidence,
not a negative scientific result. No scientific seed outcome was inspected.
The complete original matrix is retained. GitHub's jobs API, inspected after
the run completed, reports 33 completed jobs, 30 paired seed jobs and exactly
30 skipped `Run both search arms for one protected paired seed` steps. Thus
no optimizer ran in this attempt. This check preceded replacement dispatch.

The fixed input artifact was `10042814144`, SHA-256
`d29f25b6467e2b7e701811d354b3340eabf5972c4956fd8badebe3be2f14cee2`.
Its archive download and digest verification succeeded. The error concerned
the local runner extraction layout, not UCI data integrity.

Recovery adds `merge-multiple: true` only for the single, exact fixture ID.
The 30 seed artifacts still use separate directories (`merge-multiple: false`).
The contract CI now performs an actual synthetic upload/download round trip
using the pinned Actions and verifies the expected root-level file. Static
regression tests distinguish fixture flattening from forbidden seed merging.
See the [pinned download-artifact documentation](https://github.com/actions/download-artifact/tree/d3f86a106a0bac45b974a628896c90dbdf5c8093).

The original tag will never be moved. Recovery uses a new exact-SHA tag,
`eu26-21-common-bridge-evidence-v2`, after its own green CI. Scientific protocol
and configuration bytes, search/evaluator implementation, data hashes,
seed ledger `41001..41030`, 400-call budgets, bootstrap seed and decision
thresholds are unchanged. Replacement
[run 34233477859](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34233477859)
at SHA `79c9b154206cdc3d318b90b598c7f0f48ca02b53`, attempt 1, completed
30/30 paired seed jobs and aggregation successfully. Reaggregation
[34234286460](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34234286460)
authenticated all 30 artifacts without rerunning searches. Its scientific
decision is `FAIL_JOINT_BRIDGE_CLAIM_QUALITY_NONINFERIORITY`; that negative
decision caused no retries, exclusions or threshold changes.
