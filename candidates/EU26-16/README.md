# EU26-16 — G3P-kEMLC source-transition validation

Paper: Jose M. Moyano and Sebastian Ventura, *Auto-adaptive
Grammar-Guided Genetic Programming algorithm to build Ensembles of
Multi-Label Classifiers*, Information Fusion 78 (2022), 1–19, DOI
[`10.1016/j.inffus.2021.07.005`](https://doi.org/10.1016/j.inffus.2021.07.005).

Status: **`FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY`**

Readiness: **`CONDITIONAL_NONELIGIBLE`**

This bounded study authenticates the authors' `v3.0` source revision and
independently implements the within-generation update of crossover and
mutation probabilities. It also checks the four-decimal best-fitness
comparison, the ordering of the ten-generation early stop, and the shape of
the shipped Yeast fold-1 data.

It is not a replay of Table 7. In particular:

- the paper says that Table 7 averages random five-fold cross-validation over
  ten seeds, but it does not enumerate those ten seeds;
- `cfg/Yeast.xml` lists only seeds `10`, `20`, and `100`, references only folds
  1 and 2, and the repository contains only fold 1;
- the repository does not contain the complete 20-dataset, 5-fold experiment
  manifest or raw 50-run ledger; and
- the legal provenance/license of the redistributed Yeast input bytes has not
  been established independently of the repository's code license.

Consequently, `PASS_FULL`, `PASS_TABLE_7_REPLAY`, and any empirical
reproduction claim are forbidden even when every candidate-local test passes.

## What is verified

The source transition begins at `pc = pm = 0.5`. After a generation has been
evaluated, its mean fitness is compared strictly with the historical best
population mean. Improvement updates the historical mean and attempts
`pc += 0.02`, `pm -= 0.02`; equality or deterioration attempts the inverse.
The source uses guards, not clamps. On the publication lattice reached from
`0.5` by steps of `0.02`, the endpoints are `0.04` and `0.96`. They are not
global hard bounds: an off-lattice state `(0.95, 0.05)` passes the improvement
guard and becomes `(0.97, 0.03)`.

The source updates `bestAvgFitness` before checking whether a probability
change is blocked. It rounds the generation-best fitness to four decimal
places before comparing it to the historical best, then performs the
probability transition, and only then evaluates the stop condition.

The independent ARFF/XML parser establishes that the shipped Yeast fold 1 has
103 numeric inputs, 14 binary labels, 1,933 training rows, and 484 test rows.
Those structural facts do not supply the missing folds, seed ledger, or data
license.

## Local commands

Prepare a clean upstream checkout:

```bash
git clone https://github.com/kdis-lab/G3P-kEMLC.git /tmp/g3p-kemlc
git -C /tmp/g3p-kemlc checkout --detach \
  a800162492ee8ccb4e20f692b879610cb607db07
```

Run the fail-closed checks:

```bash
EU2616_UPSTREAM=/tmp/g3p-kemlc PYTHONDONTWRITEBYTECODE=1 \
  python candidates/EU26-16/tests/run_python_tests.py
EU2616_UPSTREAM=/tmp/g3p-kemlc \
  octave --quiet --eval \
  "addpath('candidates/EU26-16/tests/matlab'); run_matlab_tests"
python candidates/EU26-16/environments/python/run_verification.py \
  --checkout /tmp/g3p-kemlc --output /tmp/eu26-16-report.json
```

Reports are formula/source-transition evidence only. The verifier refuses to
overwrite an existing report.
