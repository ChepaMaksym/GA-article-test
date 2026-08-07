# EU26-02 deterministic validation portability contract v1

Frozen: 2026-08-07, before formal Work 4/8-worker and GitHub 4-vCPU runs.

Scope: archive parsing and independent Deleter formula workloads only. This is
not solver scaling and not a paper-result reproduction.

## Profiles and workloads

- Work VM with four worker processes.
- Work VM with eight worker processes.
- GitHub-hosted `ubuntu-24.04` with exactly four logical CPUs exposed to the
  validation process.
- Archive workload: partition the 31 instance parsers across workers, using the
  byte-identical pinned upstream archive.
- Formula workload: deterministic independent Deleter simulations from the
  matrix in `config/hardware_smoke_matrix.csv`.
- One untimed warm-up plus five retained timing batches; no retained timing may
  be deleted.

Every worker must set `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
`MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` and `VECLIB_MAXIMUM_THREADS` to `1`.
Parallelism is across independent validation tasks only.

## Gates

| Gate | PASS rule |
|---|---|
| H0 provenance | Git SHA; pre/post hashes of every imported module, fixture, config and comparator; archive SHA; OS, architecture, CPU model/allocation, RAM and Python metadata are present and unchanged. |
| H1 worker allocation | Exactly the requested number of distinct worker PIDs is observed, with the requested affinity and all five thread limits set to one. |
| H2 archive identity | Every parallel per-instance canonical result and the combined 31-row digest equal the serial result byte for byte. |
| H3 formula invariants | D1–D10 hold for every workload seed and at least one deletion occurs per trajectory. |
| H4 repeatability | Warm-up and all five retained batches have the same canonical result digest. |
| H5 cross-profile | Source/config/archive hashes and full canonical result arrays match byte for byte across Work 4, Work 8 and GitHub 4-vCPU. |

`cpu.max` is primary CPU-quota evidence. If absent, H0 accepts only the exact
fallback in which `os.cpu_count()`, initial and enforced affinity, and
`cpuset.cpus.effective` identify the same requested CPU set.

Timing is descriptive. No speed threshold affects H0–H5, and no claim is made
about one AHEAD trajectory scaling across cores, physical-core count, GHz, or
causal hardware performance.
