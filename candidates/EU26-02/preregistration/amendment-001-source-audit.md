# Amendment 001 — paper/code/archive mismatch

Frozen: 2026-08-07, after the v1 source contract but before implementation
tests, formal archive replay, native solver runs, or hardware profiles.

Reason: a deeper read-only source audit exposed facts that v1 did not encode.
This amendment tightens claims and comparisons; it does not alter the pinned
archive, seeds, published targets, or the two time profiles.

## New binding facts

1. Paper Sect. 2.5 defines a queue of the last 50 negative-fitness rewards for
   policy updates. Frozen Deleter code ignores that queue and ranks operators
   by positive-penalty lifetime mean.
2. The paper orders insertion before policy update. Frozen code updates
   Deleter before insertion.
3. Frozen code adds a first-deletion warm-up through source turn 30; the paper
   only says deletion occurs every five generations.
4. The archive has `restart` sentinel rows in 298 CSV files. The pinned source
   has no code that emits those rows, so it cannot be the byte-identical archive
   generator.
5. OpenMP regions use a shared global `std::mt19937` and a shared incrementing
   `Solution::counter` without synchronization. CLI seed replay is not a
   thread-schedule-independent trajectory guarantee.
6. The table pipeline rounds mean-best time to one decimal and converts that
   positive value to an integer. The `r250.5` raw mean is `549.8` and the
   displayed target is `549`; P1 must retain the exact mean and apply
   `int(round(raw_mean, 1))`. On all 31 frozen rows this also equals direct
   positive truncation.
7. The selected native smoke input is the reduced 235-vertex
   `reduced_gcp/r250.5.col`, SHA-256
   `1589cfc27c761c6014e3e6ff108270b49392ea300e9395015e28d535def57b39`.
   Its name and the original/metadata dimensions must not substitute for the
   parsed `p edge 235 13968` declaration.

## Consequences

- Deleter transition tests are explicitly **source-faithful** only.
- P1 can earn `PASS_ARCHIVE_EXACT`, which means exact table-artifact
  provenance, not formula or execution fidelity to the paper.
- G5 and G8–G10 remain unresolved; native build/micro-run can provide
  executability evidence but cannot establish source-native archive replay.
- The mandatory paper-level label is
  `BLOCKED_MULTIPLE_SOURCE_CONFLICTS`; `PASS_FULL` remains forbidden.
