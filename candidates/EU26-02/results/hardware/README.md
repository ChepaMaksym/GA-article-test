# EU26-02 authenticated hardware verification — 2026-08-07

Status: **H5 `PASS_BITWISE` across Work 4, Work 8 and GitHub 4-vCPU**.

The Work profiles ran on clean local source commit
`4a37d5fb829540a63694fd641600de7d30c5173f`. GitHub Actions checked out PR
merge commit `714e45b11804da49db43ee851b0e4514173ea024` for remote source commit
`71c84c657f98466d3446855dd65491fef32a910a`. All three profiles retained the
same 48-file H0 source map.

H0–H4 passed in every profile: the pinned archive/tar identities and immutable
payload manifest matched, the requested worker PID/affinity/thread limits were
observed, all 64 formula and 31 archive correctness objects matched their
serial references and frozen endpoints, and all five retained batches matched
the warm-up endpoint digest.

| Profile | Workers | Median batch | MAD/median | Formula jobs/s |
|---|---:|---:|---:|---:|
| Work 4 | 4 | 5.981151 s | 8.7645% | 171.2045 |
| Work 8 | 8 | 3.821808 s | 1.9193% | 267.9360 |
| GitHub 4 | 4 | 17.719875 s | 0.1493% | 57.7882 |

Timing is descriptive only: the environments differ and frequency is not
controlled, so these measurements cannot identify a causal CPU-frequency
effect.

All three pairwise comparisons are `PASS_BITWISE`: current source maps,
archive/tar identities, payload manifests, full formula objects, full archive
objects and recomputed aggregate objects match. The per-case TSVs are
byte-identical, SHA-256
`51222aab345b410695b50f4b52a4a22d7804af08337cebd49aa0094fb850f99a`.
GitHub Actions run `31163080278`, job `92817792768`, produced artifact
`8987939842`; its 94,295-byte ZIP has SHA-256
`d2ee7e3c46d4bcaf24ff8d4635e7af71e951a39fdca5ac86a8490edb401a1f82`.

This portability result covers only the frozen archive and formula validators.
It does not clear the paper-level `BLOCKED_MULTIPLE_SOURCE_CONFLICTS` status.
