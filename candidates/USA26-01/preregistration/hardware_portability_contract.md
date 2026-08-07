# GESMR hardware portability contract v1.1

Status: v1 frozen before formal runs; v1.1 metadata-only amendment after the first GitHub runs

Date: 2026-08-06; amended 2026-08-07
Scope: clean-room formula implementation only; this is not a published-result reproduction gate.

## Question

Does parallel execution of independent GESMR seed-runs preserve the numerical result when the batch is executed with four or eight worker processes and on a second cloud VM?

One GESMR trajectory remains sequential. The hardware test parallelizes independent seeds; it does not change the algorithm inside a run.

## Frozen environments

1. Work VM: eight-CPU cgroup quota, tested with affinity restricted to four and eight logical CPUs.
2. GitHub-hosted `ubuntu-24.04`: separate standard public-repository VM with four vCPUs.

CPU frequency is observed metadata only. VM clock rate, turbo state and processor model are not controlled, so this protocol cannot identify a causal GHz effect.

## Frozen workloads

The exact matrix is `config/hardware_smoke_matrix.csv`.

- Correctness seed gate: Sphere, D=30, initial standard deviation 1, 300 generations, seeds 0 through 39.
- Throughput workload: Ackley, Griewank, Rastrigin, Rosenbrock and Sphere, D=100, initial standard deviation 10, 1000 generations, seeds 0 through 7 for every function.
- Timing: one untimed warm-up batch followed by five retained batches. No timing observation may be deleted.

Every process is restricted to one numerical-library thread through `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` and `VECLIB_MAXIMUM_THREADS`.

## Frozen gates

| Gate | PASS rule |
|---|---|
| H0 provenance | Git SHA, source hashes, OS, architecture, CPU model, CPU-allocation evidence, RAM, Python, NumPy and BLAS metadata are present; every hashed executable/configuration source is tracked and byte-identical to that Git HEAD before and after execution, with no source/HEAD change during the run. |
| H1 seed ledger | Exactly the 40 unique correctness seeds 0..39 are retained. |
| H2 invariants | No crash/NaN/Inf; all mutation rates remain positive and change within-run; elitist best fitness is non-increasing within 1e-12; evaluation counts are exact. |
| H3 parallel safety | Every parallel correctness-run V1 SHA-256 equals its serial-reference V1 SHA-256 on the same profile. |
| H4 repeatability | Every measured timing batch returns the same full V1 endpoint digest as the warm-up batch. |
| H5 cross-profile portability | `PASS_BITWISE` only when all correctness hashes and source hashes match. Any hash mismatch is `INCONCLUSIVE` and requires a separate full-array numerical review; sparse summary values cannot grant PASS. |

The worker gate additionally requires exactly the requested number of distinct worker PIDs, the selected CPU-affinity set in every worker, and all five numerical thread limits equal to one in every worker.

### H0 metadata amendment

The first two GitHub profiles exposed exactly four logical CPUs but did not
mount `/sys/fs/cgroup/cpu.max`; both failed H0 only for that missing file.
Those failed artifacts remain retained. Version 1.1 keeps `cpu.max` as the
primary CPU-allocation evidence. When it is unavailable, H0 accepts only a
strict fallback in which `os.cpu_count()`, the initial and enforced process
affinity, and `/sys/fs/cgroup/cpuset.cpus.effective` all identify the same
exact requested CPU set. The unchanged worker gate must also pass.

This amendment changes metadata availability handling only. It does not alter
the workloads, algorithm, hashes, invariants, serial-parallel comparison or
timing observations, and it does not establish physical-core count, absence of
throttling, controlled clock frequency or a causal GHz effect.

Timing is descriptive and includes the small, fixed cost of computing the V1 verification digest after each trajectory. A throughput ratio is not a claim that one GESMR trajectory scales across cores, and no speed threshold affects H0-H5.

## Hash V1

The domain prefix is `GESMR-HW-V1\0`. Each field is length-prefixed and includes its name, shape and canonical little-endian bytes. The hash covers configuration, seed, evaluation accounting, final population, final fitness, final mutation rates, best-fitness history, geometric and arithmetic mutation-rate histories, and full mutation-rate history.

## Allowed claims

- The locked Python implementation is or is not portable across the tested execution profiles.
- Parallel seed batching does or does not preserve serial results.
- Observed batch throughput and observed CPU-frequency metadata.

The protocol does not establish a published-paper reproduction, MATLAB equivalence, universal hardware scaling, physical-core scaling, or a causal effect of GHz.
