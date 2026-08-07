# EU26-02 local hardware verification — 2026-08-07

Status: **Work 4/8 `PASS_BITWISE`; H5 `INCONCLUSIVE` pending GitHub 4-vCPU**.

Both profiles ran on clean Git SHA
`79eb3b6e01e581fb364c9f17b4db985544eb0130`. H0–H4 passed in each profile:
the pinned archive and temporary tar remained unchanged, the requested worker
PID/affinity/thread limits were observed, all 64 formula and 31 archive
correctness objects matched their serial references, all invariants passed,
and all five retained batches matched the warm-up endpoint digest.

| Profile | Workers | Median batch | MAD/median | Formula jobs/s |
|---|---:|---:|---:|---:|
| Work 4 | 4 | 5.918211 s | 0.8108% | 173.0253 |
| Work 8 | 8 | 3.508301 s | 0.9425% | 291.8792 |

The descriptive median ratio is 1.686917× for Work 8 versus Work 4. It has no
acceptance threshold and cannot identify a causal CPU-frequency effect. Both
profiles used the same virtualized AMD EPYC 9V74 host and the same eight-CPU
cgroup quota, with affinity restricted to four or eight CPUs.

The Work 4/8 comparison is `PASS_BITWISE`: source maps, original and temporary
archive hashes, full formula objects, full archive objects and combined
aggregates match. The per-case TSVs are byte-identical, SHA-256
`51222aab345b410695b50f4b52a4a22d7804af08337cebd49aa0094fb850f99a`.

Overall H5 remains `INCONCLUSIVE` until the required separate GitHub Actions
4-vCPU JSON passes the fail-closed three-profile comparator. Hardware results
do not clear the paper-level `BLOCKED_MULTIPLE_SOURCE_CONFLICTS` status.
