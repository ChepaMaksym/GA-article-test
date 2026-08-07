# EU26-02 archive/formula validation contract v1

Frozen: 2026-08-07, before implementation tests or any new AHEAD solver run.

Status: **`ARCHIVE_AND_FORMULA_VALIDATION_ONLY`**

Published-paper gate: **`BLOCKED_MULTIPLE_SOURCE_CONFLICTS`**

This contract authorizes source audit, exact replay of already-published raw
CSV artifacts, independent Deleter transition tests, native build/micro-run
checks, and deterministic hardware-portability checks. It does not authorize
a claim that the paper's one-hour experiment was reproduced.

## Frozen sources and cell

- Paper DOI: `10.1007/978-3-031-57712-3_5`.
- Code: `Cyril-Grelier/gcp_ahead` at
  `04da9dd489f6e8e76fa3504d105c137bdf9ea323`.
- Inputs: `Cyril-Grelier/gc_instances` at
  `68e2563a82af68a42ef2ce397317d80b78a5b2a1`.
- Deleter archive SHA-256:
  `1b7e8cf1ef637005bd994104f6e1ee520256ed387994b126bbe875a137632e41`.
- Run ledger: CLI seeds `0..19` for each of the 31 GCP instances.
- Focus cell: Table 2 AHEAD+Deleter on `C2000.9`: best `404`, mean
  `405.6`, displayed mean-best time `2988` seconds.
- Full gate: every AHEAD+Deleter row in
  `fixtures/published_table2_ahead_deleter.csv`, not only the focus cell.

The target values are transcribed from the paper before the validator is run.
No tolerance may be enlarged after observing a replay.

## Frozen profiles

### P1 — `artifact_actual_10800`

For every root (non-`tbt`) CSV in the pinned archive:

1. Parse comments and require the metadata header to be structurally valid.
2. Require `time_limit=10800` and a seed in `0..19`.
3. Take the final data row without a time filter.
4. Retain it only when `penalty=0` and `nb_uncolored=0`.
5. Require exactly one retained legal target per instance/seed.
6. For every instance compute `best=min(nb_colors)`, arithmetic mean colors
   rounded to one decimal, and arithmetic mean `time` among runs whose color
   count equals `best`.

P1 passes archive replay only if the archive hash, all 31 seed sets, and all 31
published best/mean/time cells match. Numeric comparison uses exact integers
for best, exact one-decimal values for mean, and the paper's displayed positive
integer time after first rounding the arithmetic mean to one decimal and then
converting it to an integer. The exact time mean remains in the evidence
report.

### P2 — `paper_claimed_3600_diagnostic`

Within each available CSV, retain data rows with `time <= 3600`, then apply the
same legal-row and aggregation logic. P2 has no acceptance target and cannot
pass the paper protocol: the archive jobs were launched with 10,800-second
per-attempt budgets, target retries are separate jobs, and the stored rows do
not reconstruct a fresh one-hour independent run. P2 is reported only to show
whether the conflict changes the result.

The profiles must never be pooled or relabeled.

## Deleter transition gates

| Gate | Requirement |
|---|---|
| D1 initialization | Surviving indices are exactly `0..5`; counts and lifetime means are zero. |
| D2 selection | Every selected index belongs to the current survivor set; fixed-tape selection is used for cross-language checks. |
| D3 mean | Each update equals the exact online lifetime arithmetic mean of child penalties. |
| D4 warm-up | No deletion occurs on turns `0..29`. |
| D5 cadence | First deletion is on source turn 30; later deletions occur only on turns divisible by 5. |
| D6 ranking | The largest lifetime mean is deleted; equal means delete the lowest surviving index. |
| D7 boundary | One action remains and can never be deleted. |
| D8 adaptation | At least one deletion occurs in the deterministic smoke trajectory. |
| D9 determinism | Repeated same-seed runs within an environment are byte-identical. |
| D10 fail closed | Invalid dimensions, indices, non-finite scores, negative turns, malformed CSVs and duplicate retained seeds are rejected. |

Python and MATLAB/Octave must independently match the frozen transition
fixture exactly; all transition values are integer or rational, so the
tolerance is zero.

## Native-source gate

A native check requires a clean temporary checkout at the pinned revisions,
verified source hashes, declared compiler/dependencies, a successful build,
and a seedable micro-run on a pinned legal DIMACS input. It is evidence of
source executability only. Amendment 001 records why it cannot identify the
archive-producing executable. It cannot resolve P1 versus the paper's P2
claim, and a missing LibTorch/environment lock is reported as `NOT_RUN` or
`INCONCLUSIVE`, never waived.

## Outcome labels

- `PASS_AGGREGATE_EXACT`: internally consistent 31-instance per-seed objects
  match every target, without independently establishing their tar-container
  provenance; this status cannot satisfy the archive gate by itself.
- `PASS_ARCHIVE_EXACT`: P1 reproduces every frozen Table 2 cell.
- `PASS_FORMULA`: all D1–D10 and Python/Octave fixed-tape gates pass.
- `PASS_PORTABILITY`: the separate hardware contract passes.
- `BLOCKED_MULTIPLE_SOURCE_CONFLICTS`: mandatory overall paper-level label
  while the protocol, formula, source-revision and environment discrepancies
  remain.
- `PASS_FULL`: forbidden under v1 of this contract.
