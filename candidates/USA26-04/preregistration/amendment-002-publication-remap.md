# USA26-04 publication-remap amendment 002

Recorded 2026-08-07 after the candidate-only branch was published and before
admission of any hardware evidence. Publication sanitized the local development
history and therefore changed the object ID of the outcome-blind freeze commit:

- prepublication local commit: `a8322b17dcd8e6f722b6d70390f24262f5bcbff2`;
- published remote commit: `c76c7ebf26777c52f2ff9a78482d894534dfb94b`;
- shared tree: `f836090953f8b70374495c78f57dc009e455316a`;
- shared parent: `eeac926e15107503377cbe09cdc8e830a6607fa5`.

The two commit IDs are exact freeze twins: they have the same parent, tree,
message, source-manifest blob, protocol blob, and descriptive Table 1 blob.
Their mapping is provenance-only. It changes no formula case, numeric oracle,
descriptive target, reward interpretation, ambiguity, source assertion,
hardware gate, scientific scope, or status. In particular,
`BLOCKED_G5_G9`, `INCONCLUSIVE_PUBLISHED_RESULT`, `conditional_noneligible`,
and the prohibition on `PASS_FULL` and Table 1 execution remain frozen.

The published remote ID is the current `freeze_commit`. Validation enumerates
both IDs, verifies every available twin against the exact shared tree, parent,
blob IDs, and byte hashes, and requires exactly one twin to be an ancestor of
the evidence-producing `HEAD`. On the published branch that unique ancestor
must be the published remote ID. Missing, altered, unrelated, or jointly merged
twin histories fail closed.
