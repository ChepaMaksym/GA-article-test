# EU26-21 pinned author-source status

Status: `PASS_SOURCE_NUMERIC_ALIGNMENT`.

This is a necessary OLD milestone, not `PASS_OLD_FULL`, and it does not authorize HYBRID.

## Provenance

Repository: `Ghaith81/Fast-Genetic-Algorithm-For-Feature-Selection`.

Commit: `6ac5a7ec77f8a7c096ab4d019254fcc897988fd6`.

Exact `Dataset.py`, `Evolution.py`, `Example.ipynb`, Census-Income data, and result-file blobs passed the fail-closed audit. The executed notebook endpoint was also authenticated.

## Frozen campaign

- Census-Income: 199,523 observations, 41 feature variables, two classes.
- Contiguous author split: 119,713 train / 39,905 validation / 39,905 test.
- Normalization, label encoding, and Decision Tree follow the pinned source.
- Source CHC-QX parameters: `population=50`, `f=10`, `q=10`, outer no-change limit `2`.
- Auditor seeds: `1..10` plus an exact repeated seed 1.
- Python 3.9 with frozen NumPy, pandas, SciPy, scikit-learn, matplotlib, DEAP, and PySwarms versions.

## Numerical result

| Metric | Paper target | Observed | Gate |
|---|---:|---:|---|
| Baseline test accuracy | 92.87% | 92.8681% | PASS |
| CHC-QX median test accuracy | 94.94% | 94.9455% | PASS |
| CHC-QX sample SD | 0.07 percentage points | 0.0336 | PASS |
| Runs at or above 94.75% | at least 8/10 | 10/10 | PASS |
| Runs improving at least 1.50 points | at least 8/10 | 10/10 | PASS |
| Completed runs | 10/10 + repeat | 10/10 + repeat | PASS |

All S0-S6 gates from `NUMERIC_GATE.md` passed.

Per-seed test accuracy (%):

`94.8528, 94.9204, 94.9555, 94.9580, 94.9130, 94.9405, 94.9480, 94.9655, 94.9500, 94.9650`.

Selected feature counts:

`3, 6, 9, 13, 7, 9, 5, 13, 7, 14`.

Selected meta-model sample sizes:

`7482, 7482, 14964, 7482, 14964, 14964, 7482, 14964, 7482, 14964`.

The repeated seed 1 matched exactly for all algorithm/result fields excluded from wall-clock time.

## Notebook artifact comparison

Authenticated notebook example:

- sample size 14,964;
- validation fitness 0.9491;
- test accuracy 94.96%;
- features `[12, 16, 17, 19, 40]`.

Auditor seed 1:

- sample size 7,482;
- validation fitness 0.9489;
- test accuracy 94.8528%;
- features `[15, 16, 17]`.

The notebook seed is not published, so this difference is expected and was not used as a literal seed-replay requirement.

## Artifact

GitHub Actions workflow run: `31509431617`.

Campaign artifact SHA-256: `4b27a86ecb3bdd8f9ff10ae865a9c8ea529c59b846a5b04c27d88fb76800d35c`.

## Remaining OLD blocker

The printed paper and public source are materially non-interchangeable. In particular, the paper describes an instance-mask CHC active-sampling GA with `q=20`, while the executed public implementation uses progressive sample halving and `q=10`. Other differences include restart rate, convergence semantics, preprocessing shuffle, and source HUX details.

Therefore the next stage is an independent clean-room implementation plus an explicit paper/source reconciliation. No executable file may be added to `hybrid/` before that work reaches `PASS_OLD_FULL`.
