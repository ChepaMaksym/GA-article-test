# Amendment 002 — archive-provenance binding

Frozen: 2026-08-07, after implementation review and before any accepted
formal P1/P2, selected-witness, or hardware run.

The first attempted formal command stopped at its clean-HEAD SHA assertion,
before opening the pinned archive. It produced no scientific result.

## Binding clarification

`aggregate_results()` accepts independently parsed per-instance result
objects. Internal consistency and canonical digests cannot prove which tar
container produced those objects. The exported aggregator therefore may
return `PASS_AGGREGATE_EXACT`, but it is forbidden from returning
`PASS_ARCHIVE_EXACT`.

Only `validate_archive()` may upgrade a complete 31-instance P1 result to
`PASS_ARCHIVE_EXACT`, and only after it has verified the original archive's
pinned SHA-256 and parsed the member groups from that same open container.
The hardware profile separately binds its parallel aggregate to the unchanged
pinned original archive and its deterministic temporary uncompressed
derivative; its H2 result does not relabel the aggregate as a standalone
archive replay.

Report digests use the immutable source identifier rather than a machine-local
absolute archive path. This changes report portability only, not any target,
seed, statistic, tolerance, time profile, or allowed paper-level claim.

The same review corrected the registry's G6 wording: `insertion_head`
replaces the two-parent population with the two children and sorts them by
penalty. At the elite cadence, the code samples replacement index 0 or 1
uniformly, switches to the other index when the sampled child's distance to
the current elite exceeds `floor(0.99 * nb_vertices)`, and replaces the
resulting child. Elite reinsertion can therefore replace either the current
best or worst child. Termination can be caused by the time limit, iteration
limit, or a legal target solution. The G6 status remains `pass`; the mandatory
paper-level status remains `BLOCKED_MULTIPLE_SOURCE_CONFLICTS`.
