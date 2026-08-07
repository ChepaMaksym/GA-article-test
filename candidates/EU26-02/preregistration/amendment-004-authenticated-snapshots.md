# Amendment 004 — authenticated snapshots and immutable worker payloads

Frozen: 2026-08-07, after the final adversarial source review and before any
accepted remediation rerun.

## Reason

The review found a hash-close-reopen race in the archive, selected-witness and
hardware paths. A caller-controlled path could be replaced after its bytes were
hashed but before a later open parsed them. End-of-run hashes detect an
ordinary persistent mutation, but they do not prove that every parser consumed
the authenticated bytes and do not fail closed against swap-and-restore.

This is a provenance-binding defect, not evidence that the recorded numerical
Table 2 values, selected coloring or Deleter transition are wrong.

## Superseded evidence

All archive-replay, selected-witness, hardware-profile and H5 cross-profile
evidence produced before this amendment is superseded as acceptance evidence.
Those files may remain as historical records, but none may be cited as the
current passing provenance gate. P1, P2, the selected witness, every required
hardware profile and H5 must be rerun from a clean tracked revision after the
requirements below are implemented and tested.

## Frozen remediation

1. The archive validator must create a private snapshot from one open source
   descriptor while computing SHA-256 and byte length. It must verify both
   values before parsing and must never reopen the caller-controlled source
   path. Decompression and tar parsing must consume only that authenticated
   private snapshot or a descriptor derived from it.
2. The selected-witness validator must apply the same rule independently to
   the archive and graph. Exact tar-member hashes remain mandatory; graph
   parsing and coloring checks must consume the authenticated graph snapshot.
3. The hardware coordinator must authenticate private original and derived
   snapshots before starting workers. Workers must receive immutable member
   payloads, or private descriptors with equivalent immutability, rather than
   repeatedly reopening a mutable shared tar path.
4. Deterministic adversarial tests must replace or mutate each original and
   derived path at the former hash/open boundary. A gate may pass only when the
   parser demonstrably consumed the already-authenticated snapshot; otherwise
   it must fail without writing passing evidence.
5. The remediation implementation, tests, workflow and all preregistration
   files remain inside H0 source hashing. Formal evidence is accepted only from
   a clean tracked HEAD whose source hashes remain unchanged throughout each
   run.

The pinned gzip deterministically yields a 276,705,280-byte tar snapshot with
SHA-256 `a3c5893a1a7de480a05b26cbef24a2e07d161f8ed5923354444d6ea2d2fb5cf8`.
The 1,143 non-TBT root CSV payloads total 104,406,336 bytes; their canonical
`(instance, member name, byte length, member SHA-256)` manifest has SHA-256
`d50f4be5378357a45fc65047849f2ad1e99d01a8a005da42538f2d27fd585a36`.
These are byte-custody identities, not scientific outcomes. H0 and H5 must
reject a profile unless all four derived values match exactly.

The remediation does not alter the frozen deterministic workload endpoints.
To prevent a consistently wrong serial/parallel implementation from passing,
the 64-case formula aggregate remains
`5e0f1346a7eb931a7c5bda08f2df082c2a0027c9b359f37c78b1be5ef5f3d61a`,
the 31-case archive aggregate remains
`9b0b90fca330fd89c259b907a215f9336add73f6ad599a4a94c9946d632183c9`,
and the combined 1,024-formula/31-archive timing endpoint remains
`3fe3d29b882589784d4cc136dc1aced17400e86e12fd0fd0371076a865819962`.
H2–H5 must fail if any of these exact digests changes.

## Unchanged claims and residual trust model

This amendment changes byte custody only. It does not change the archive,
graph, member hashes, optimizer configuration, seeds, profiles, target cells,
statistics, rounding, tolerances, Deleter semantics or outcome labels. The
mandatory paper-level status remains `BLOCKED_MULTIPLE_SOURCE_CONFLICTS`, and
`PASS_FULL` remains forbidden.

After private authenticated snapshots and immutable worker payloads are in
place, the residual model assumes a trusted clean workspace, operating system,
Python runtime and storage stack. Hostile code with permission to alter process
memory, private temporary files or open descriptors is outside scope. Mutation
of caller-controlled input paths before or during snapshot creation remains in
scope and must not produce a passing provenance claim.
