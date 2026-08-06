# USA26-01 — GESMR clean-room scaffold

This folder implements the within-run adaptive **Group Elite Selection of
Mutation Rates (GESMR)** kernel for direct analytic minimization. It is a
prospective formula-validation artifact, not a published-result
reproduction.

| Item | Status |
|---|---|
| Direct optimization / no inversion | `PASS` |
| Python formula kernel | Implemented and unit-tested |
| MATLAB/Octave formula kernel | Implemented; runtime test pending |
| Fixed-random-tape Python micro-oracle | `PASS` |
| Cross-environment execution | Pending MATLAB/Octave runtime |
| Full 40-seed experiment matrix | Not run |
| Published Table 1 gate | `BLOCKED_INCONCLUSIVE` |
| Reproduction outcome | **Not claimed** |

Source: Kumar et al., “Effective Mutation Rate Adaptation through Group
Elite Selection,” GECCO 2022,
[`10.1145/3512290.3528706`](https://doi.org/10.1145/3512290.3528706),
[arXiv:2204.04817](https://arxiv.org/abs/2204.04817).

## Implemented update cycle

For every generation, both implementations:

1. sort solutions by ascending objective and preserve one elite;
2. sample \(N\) parents with replacement from the best
   \(m=\eta_xN\) solutions;
3. partition those parents into \(K\) equal groups and apply each group’s
   current Gaussian mutation rate;
4. score an MR by the best child-minus-parent objective change in its
   group;
5. preserve the best MR, sample the remaining MR parents from the best
   \(l=\eta_\sigma K\), and mutate them with
   \(\sigma'=\sigma\tau^u\), \(u\sim U[-1,1]\).

There is no crossover, boundary clipping, surrogate, forward model,
observed-data fit, source reconstruction, or hidden-state estimation.

## Layout

- `environments/python/gesmr/` — independent NumPy reference;
- `environments/matlab/` — toolbox-free MATLAB/GNU Octave implementation;
- `fixtures/cross_env_step.json` — shared 12-D fixed-random-tape oracle;
- `config/` — five-function subset freeze, 40 configurations, seeds 0–39;
- `tests/` — unit, property, determinism, accounting, and protocol tests;
- `source_manifest/` — hashes, legal sources, revision and conflict audit;
- `preregistration/` — frozen formula-validation gates and claim limits.

## Run the Python tests

From the repository root:

```bash
python3 candidates/USA26-01/tests/run_python_tests.py
```

A short diagnostic run (not a published gate):

```bash
python3 candidates/USA26-01/environments/python/run_experiment.py \
  --function sphere --dimension 30 --initial-std 1 --seed 0 --generations 3
```

The pinned tested Python dependency is in
`environments/python/requirements.txt`.

## Run the MATLAB or GNU Octave tests

MATLAB:

```matlab
addpath('candidates/USA26-01/tests/matlab')
run_matlab_tests
```

GNU Octave:

```bash
octave --quiet --eval "addpath('candidates/USA26-01/tests/matlab'); run_matlab_tests"
```

The MATLAB/Octave tests load the same JSON tape used by Python and assert
the same one-generation population, objective values, group scores, and
MR population to absolute tolerance `1e-12`.

The branch workflow
`.github/workflows/cohort-2026-formula-validation.yml` runs the Python
suite and the MATLAB-compatible suite under GNU Octave as separate jobs.
Those jobs validate formulas only; a green workflow is not a published-
result reproduction.

## Scientific limitation

The audited sources disagree on `d=10` versus `d=30`, five versus 40
seeds, and dimension-dependent versus constant generation budgets. The
tracked upstream table contains preliminary generation-500 values, not
the exact camera-ready result revision; its five `d=100`, initial-std-10
GESMR cells differ from the final Table 1, so it cannot serve as a
like-for-like gate. These conflicts are itemized with exact numbers and
hashes in `source_manifest/audit_notes.md`. Until the exact camera-ready
driver/result revision, raw runs, RNG/dependency lock, and discriminating
numerical gate are available, this candidate remains
`FORMULA_VALIDATION_ONLY` and cannot produce `PASS_FULL`.
