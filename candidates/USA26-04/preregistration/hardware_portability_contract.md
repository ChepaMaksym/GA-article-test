# USA26-04 formula portability contract v1

Frozen: 2026-08-07, before implementation or execution.

Scope: **formula portability, not paper reproduction**. The paper-level status
is permanently frozen for this contract as `BLOCKED_G5_G9` /
`INCONCLUSIVE_PUBLISHED_RESULT`.

## Profiles and workload

- Work VM with affinity restricted to four logical CPUs and four workers.
- Work VM with affinity restricted to eight logical CPUs and eight workers.
- GitHub-hosted `ubuntu-24.04` with exactly four visible logical CPUs and four
  workers.
- Matrix: exactly `config/hardware_formula_matrix.csv`.
- Each trajectory is a self-contained deterministic formula case; only
  independent cases are parallelized.
- One untimed warm-up and five retained parallel timing batches. No timing
  observation may be removed.
- `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`,
  `NUMEXPR_NUM_THREADS`, and `VECLIB_MAXIMUM_THREADS` are fixed to `1`.

CPU model and MHz are observational metadata. This protocol cannot establish
physical-core scaling, a causal GHz effect, or general performance scaling.

## Gates

| Gate | Frozen rule |
|---|---|
| H0 provenance | Git HEAD is clean for all hashed sources; Git SHA, source hashes, OS, CPU allocation, Python, and numerical-library metadata are present; the absence manifest retains every required missing fact. |
| H1 formula | Every matrix case passes its objective/reward/update/ambiguity oracle. |
| H2 fixed tape | The fixed controller tape yields the frozen canonical transition and matches the MATLAB/Octave fixture report when supplied. |
| H3 adversarial | Invalid domains/states are rejected and the boundary/tie witnesses remain `AMBIGUITY_CONFIRMED`, never resolved. |
| H4 batch | Serial and parallel canonical case records and their aggregate digest are byte-identical; all five retained repeats match the warm-up digest and use exactly the requested worker count/affinity. |
| H5 cross profile | `PASS_FORMULA_PORTABILITY` only if Work-4, Work-8, and authenticated GitHub-4 have identical case IDs, source hashes, protocol ID, and aggregate digest. Otherwise fail closed as `INCONCLUSIVE_*`. |

A single profile reports H5 as `NOT_EVALUATED_SINGLE_PROFILE`. H5 never means
the Table 1 result was reproduced. The report and comparator must always retain
`paper_level_status=BLOCKED_G5_G9` and
`published_result_status=INCONCLUSIVE_PUBLISHED_RESULT`.

## Canonicalization

Protocol ID: `USA26-04-FORMULA-PORTABILITY-v1`.

Hash domain: the UTF-8 bytes `USA26-04-FORMULA-V1\0` followed by canonical
JSON (`sort_keys=true`, separators `(',', ':')`, `allow_nan=false`, one record
per case). Floating values are finite IEEE-754 binary64 values serialized by
the language-neutral fixture/report schema. Source files are hashed as bytes.

Timing values and hardware metadata are outside the correctness digest.
