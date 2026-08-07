# USA26-04 evidence-authentication amendment 001

Recorded 2026-08-07 after adversarial review and before publication of any
hardware evidence. This amendment changes evidence admission only. It does not
change formula cases, numeric oracles, descriptive Table 1 values, scientific
scope, or the frozen `BLOCKED_G5_G9` / `INCONCLUSIVE_PUBLISHED_RESULT` status.

The following fail-closed controls supersede weaker transport wording in the
original hardware contract:

- H2 can pass only for a report produced inside the profile runner's own
  init-disabled MATLAB/Octave invocation. The report binds protocol ID,
  current Git SHA, engine/version, every independent `.m` source hash, fixture
  hash, canonical payload and digest. A separately supplied report is
  diagnostic and unauthenticated, even when its values match.
- Each profile binds a nonempty exact current-checkout source map and Git SHA.
  The comparator revalidates the full typed schema, exact unique frozen case
  set, every recomputed canonical record/per-record hash/aggregate digest,
  H0-H4 statuses, five retained timings, worker counts, claim limits, and the
  synthetic controller-state provenance.
- A GitHub profile cannot authenticate its role from JSON. H5 additionally
  requires a separately retrieved API provenance record binding repository,
  frozen workflow, head, run/attempt, artifact ID/name and downloaded report
  SHA-256. The comparator checks this metadata binding only; authenticated API
  retrieval, download and hashing remain an external prerequisite that JSON
  alone cannot establish.
- Generated profile/comparison artifacts must be distinct files outside the
  repository. Missing, malformed, duplicate, extra, type-confused, copied, or
  status-promoted evidence fails closed.

These controls may turn a formerly accepted engineering report into
`INCOMPLETE_*`, `INCONCLUSIVE_*`, or rejection. They can never promote a
scientific claim or authorize `PASS_FULL`.
