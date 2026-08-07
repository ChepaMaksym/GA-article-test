# EU26-01 deterministic portability contract v1

Frozen: 2026-08-07, before formal Work4, Work8 or GitHub4 execution.

Scope: authenticated archive parsing and independent fixed-tape
OneMinMax/HV/TwoRate formulas only. This is not stochastic GSEMO scaling and
not source-native paper reproduction.

## Required profiles and retained timings

| Role | Workers | CPU requirement |
|---|---:|---|
| `work4` | 4 | four enforced logical CPUs and cgroup quota of at least four |
| `work8` | 8 | eight enforced logical CPUs and cgroup quota of at least eight |
| `github4` | 4 | GitHub `ubuntu-24.04` exposing exactly four logical CPUs |

Every profile uses one worker per enforced logical CPU. Every worker must
observe `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`,
`NUMEXPR_NUM_THREADS` and `VECLIB_MAXIMUM_THREADS` equal to `1`.

The workload matrix is exact:

- 64 fixed-tape correctness replays;
- 512 fixed-tape throughput replays; and
- all 100 run columns of the exact authenticated focus CSV.

Each profile executes one untimed warm-up followed by exactly five retained
timing batches. No retained timing is discarded. Timing is descriptive and
has no threshold or causal hardware-performance interpretation.

## H0-H5 gates

| Gate | PASS rule |
|---|---|
| H0 provenance | Clean tracked HEAD; stable pre/post Git SHA and hashes for every candidate, workflow, comparator and cohort-registry input; exact archive/member authentication before and after use; OS, architecture, CPU allocation, RAM and Python metadata present; outputs outside the repository. |
| H1 worker allocation | Exactly the requested distinct worker PIDs are observed; every worker has exactly the enforced CPU affinity and all five thread limits equal one. |
| H2 archive identity | Serial and parallel completion vectors, exact statistics and canonical digests are byte-identical and equal the frozen authenticated-output bindings. |
| H3 formula invariants | Every replay matches the fixed fixture; OneMinMax/HV/transition invariants and all frozen invalid-input probes pass; formula digests equal the frozen bindings. |
| H4 repeatability | Warm-up and all five retained batches have the same canonical endpoint digest. |
| H5 cross-profile | Git/source/config/archive/member hashes, exact completion vector/statistics, formula result and endpoint digests match pairwise across `work4`, `work8` and `github4`; the GitHub4 bytes are additionally bound to a separately acquired authenticated GitHub workflow-run/artifact API record. |

`cpu.max` is primary Work-profile quota evidence. If unavailable, the runner
accepts only a fallback in which `os.cpu_count()`, initial affinity and the
effective cpuset identify exactly the requested set. GitHub4 always requires
that exact-visible fallback; a runner merely advertising a larger host does
not satisfy it.

The runner authenticates the whole 173,556,521-byte ZIP once into a private
snapshot and gives forked workers only the immutable exact-member bytes.
Workers never reopen an archive path. A second full authenticated load after
all batches must match the first byte-for-byte and retain the same path inode.

The exact output digests are a post-freeze provenance binding to the already
fixed archive/member and fixed-tape objects. They are not a new numeric target
or an enlarged acceptance tolerance.

A two-profile `work4`/`work8` comparator may report
`PASS_REQUIRED_LOCAL_PAIR`, but H5 remains
`NOT_EVALUATED_MISSING_GITHUB4`. Only all three required roles may report
`PASS_PORTABILITY`, and only when a separate strict API-attestation record
binds repository, workflow path, head SHA, run ID, run attempt, artifact ID
and name, raw `github4.json` SHA-256 and its internal canonical report digest.
The GitHub environment fields inside `github4.json` are self-asserted context,
not authentication. Three matching profile JSON files without the separate
record remain `NOT_EVALUATED_UNAUTHENTICATED_GITHUB4`.

All profile and attestation JSON is parsed fail-closed: duplicate object keys
and non-finite `NaN`/`Infinity` constants are forbidden.

Every profile and comparison must retain:

`literal_one_based_pseudocode_4_low_6_high_vs_prose_and_source_5_low_5_high`.

The overall paper-level status remains `BLOCKED_SOURCE_NATIVE_REPLAY`,
eligibility remains `conditional_noneligible`, and `PASS_FULL` is forbidden.
