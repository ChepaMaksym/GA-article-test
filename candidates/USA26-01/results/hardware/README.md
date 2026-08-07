# GESMR hardware-portability verification — 2026-08-06

Status: **Work 4/8 PASS_BITWISE; cross-machine gate INCONCLUSIVE pending GitHub 4-vCPU dispatch**.

This verifies the clean-room GESMR formula implementation and parallel batching of independent seed-runs. It is not a reproduction of the paper's published result and not evidence that one GESMR trajectory scales across cores.

## Frozen protocol

- Runtime source commit: `d53692cd19743ec130a9cece26a1eb95f2207a63`.
- Correctness: Sphere, D=30, initial standard deviation 1, 300 generations, seeds 0..39.
- Throughput: five functions x eight seeds, D=100, initial standard deviation 10, 1000 generations; 40 runs per batch.
- Timing: one warm-up plus five retained batches, with no deletions.
- Every worker has all numerical-library thread limits fixed to one.
- Every result hash covers configuration, seed, accounting, all final arrays and all mutation-rate histories.

## Work VM results

Host evidence: AMD EPYC 9V74 under virtualization; cgroup `cpu.max=800000 100000`, which is an eight-CPU quota. The observed `/proc/cpuinfo` snapshot was 2596.13 MHz in both profiles. This is one host tested with two affinity sets, not two physical machines.

| Profile | Worker PIDs | Affinity | Serial/parallel mismatches | Invariant failures | Median 40-run batch | MAD/median | Throughput |
|---|---:|---|---:|---:|---:|---:|---:|
| Work 4-core | 4 | CPUs 0..3 | 0/40 | 0/40 | 3.932131 s | 2.080% | 10.1726 jobs/s |
| Work 8-core | 8 | CPUs 0..7 | 0/40 | 0/40 | 2.066600 s | 0.928% | 19.3555 jobs/s |

The descriptive batch-throughput ratio is `1.902706x` for 8 workers versus 4 workers. This ratio has no preregistered inferential threshold and does not isolate CPU frequency.

Both profiles produced the same aggregate correctness digest:

`53483c8592df9f2cbb0fbe1e911881532bcc08188e5167c9c82365f3579dcfc0`

The complete per-seed TSV files are byte-identical (`SHA-256 92583e7a829368cf64118d31bf21572c5d05eb8a2ef08aa992dd71def85fa743`). Source files were tracked, identical to Git HEAD, and unchanged from the beginning through the end of each formal profile. All 19 Python formula/harness tests and all 13 registry mutation tests passed before execution.

## Cross-machine status

The pairwise Work 4/8 comparison is `PASS_BITWISE`. The overall protocol remains `INCONCLUSIVE` because the required separate GitHub Actions 4-vCPU profile has not run.

The active workflow on `research/cohort-2026-12` contains the frozen 4-vCPU job. GitHub App writes and the temporary draft PR did not dispatch Actions, and the cloud browser was signed out. PR #2 was therefore closed without merge. An authenticated user must open the [Cohort 2026 formula validation workflow](https://github.com/ChepaMaksym/GA-article-test/actions/workflows/cohort-2026-formula-validation.yml), choose `research/cohort-2026-12`, and click **Run workflow** once. The GitHub job will upload `gesmr-github-4core-profile`; that JSON must then be compared with both Work profiles before H5 can pass.

GitHub documents the standard public `ubuntu-24.04` runner as a separate four-CPU, 16-GB x64 VM. GitHub does not contractually specify or control its CPU GHz, so the final comparison can report observed whole-platform timing but cannot infer a causal GHz effect.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `work-4core.json` | `6cdd65639aeee5b606aa2584d3bbefdefc05ef976dce806d02e86a8ba8d8190b` |
| `work-8core.json` | `01ecad7bf43e6a5cd2b6fea20501c0b2ea135af3608557caeb8e687041a8ad66` |
| `work-partial-comparison.json` | `f9841b148a0bd9c566ad9d7f92d89175d6bf60c24e005d6a0d8589f29848308d` |
