# EU26-02 hardware portability verification — 2026-08-07

Status: **H5 `PASS_BITWISE` across Work 4, Work 8 and GitHub 4-vCPU**.

The Work profiles ran on clean branch Git SHA
`cc6b4834d59c86511c363343fa68f03169c20e2b`. GitHub Actions checked out
PR merge SHA `d4abe4c88dab37e6b0141bd6046568e3ddc162c8`; both commits have the same
tree `188967341ca7df73b8756a6fe90b45bb70f93154`. H0–H4 passed in every profile:
the pinned archive and temporary tar remained unchanged, the requested worker
PID/affinity/thread limits were observed, all 64 formula and 31 archive
correctness objects matched their serial references, all invariants passed,
and all five retained batches matched the warm-up endpoint digest.

| Profile | Workers | Median batch | MAD/median | Formula jobs/s |
|---|---:|---:|---:|---:|
| Work 4 | 4 | 5.405412 s | 0.2359% | 189.4398 |
| Work 8 | 8 | 3.518480 s | 0.1758% | 291.0348 |
| GitHub 4 | 4 | 18.278143 s | 0.0601% | 56.0232 |

Timing is descriptive only: the environments differ and frequency is not
controlled, so these measurements cannot identify a causal CPU-frequency
effect.

All three pairwise comparisons are `PASS_BITWISE`: source maps, original and
temporary archive hashes, full formula objects, full archive objects and
combined aggregates match. The per-case TSVs are byte-identical, SHA-256
`51222aab345b410695b50f4b52a4a22d7804af08337cebd49aa0094fb850f99a`.
The GitHub Actions artifact ZIP has SHA-256
`fdb77334283a754e9caec6fd9a44c761b7aa1418ff0f7666f2dd72a4e522fbd6`;
the fail-closed H5 report is summarized in `cross-profile-summary.json`.

This portability result covers only the frozen archive and formula validators.
It does not clear the paper-level `BLOCKED_MULTIPLE_SOURCE_CONFLICTS` status.
