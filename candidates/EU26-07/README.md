# EU26-07 - resetting self-adjusting `(1+(lambda,lambda))` GA

Paper: Mario Alejandro Hevia Fajardo and Dirk Sudholt, *Theoretical and
Empirical Analysis of Parameter Control Mechanisms in the
`(1+(lambda,lambda))` Genetic Algorithm*, ACM TELO 2(4), Article 13,
DOI [`10.1145/3564755`](https://doi.org/10.1145/3564755).

Author artifacts:

- [open paper PDF](https://mhevia.com/assets/pdf/journal_oplclga.pdf);
- [implementation and result repository](https://github.com/mariohevia/Parameter-Control-Mechanisms-Genetic-Algorithm),
  pinned to `49949a55208359ac93b7110afb23ed276bda158d`.

## Recommended language split

The scientific algorithm is specified by mathematics and pseudocode, not by a
required programming language. This candidate therefore uses:

- **MATLAB/GNU Octave as the primary independent paper reproduction**;
- **Python only as an authenticated author-source and raw-artifact reference**.

The MATLAB implementation is not a transliteration of the Python shortcut
class. It implements the paper's Algorithm 3 with bit-vector chromosomes and
supports dimensions above the binary64 encoded-integer limit, including the
paper's `n=60` and `n=160` Jump experiments.

## MATLAB paper-profile implementation

Primary files:

- `environments/matlab/eu2607_run_paper_algorithm3.m` - complete stochastic
  Algorithm 3 run;
- `environments/matlab/eu2607_run_paper_batch.m` - multi-run seed ledger,
  summaries, quantiles, standard deviations and optional CSV output;
- `environments/matlab/eu2607_jump_fitness_bits.m` - vectorized `Jump_k`
  objective for logical bit-vector rows;
- the existing formula functions for controls, half-up rounding, exact
  mutation, crossover, reset and fixed-random-tape checks.

The full MATLAB runner freezes these paper semantics:

1. initialize a uniformly random bit string and `lambda=1`;
2. derive `p=lambda/n`, `c=1/lambda`, and use nearest rounding with exact
   halves rounded upward;
3. sample one `L ~ Bin(n,p)` per generation;
4. create `round(lambda)` mutants, each flipping exactly `L` distinct positions;
5. select one best mutant uniformly among ties;
6. create `round(lambda)` biased-uniform crossover offspring;
7. select from the best mutant plus crossover offspring, excluding copies of
   the current parent;
8. compare strict success with the **pre-replacement parent**;
9. shrink, grow, or reset `lambda` according to Algorithm 3.

The pre-replacement comparison is an explicit repair of the printed line-order
ambiguity: Algorithm 3 replaces `x` before the following line tests whether
`f(y)>f(x)`. The surrounding analysis defines success as leaving the current
fitness level, so the implementation retains the old fitness for this test.

### One MATLAB run

```matlab
addpath('candidates/EU26-07/environments/matlab')
config = struct( ...
    'n', 60, ...
    'k', 4, ...
    'update_factor', 1.5, ...
    'seed', 1, ...
    'max_evaluations', 1e7, ...
    'record_trace', true);
result = eu2607_run_paper_algorithm3(config);
```

### Batch experiment

```matlab
addpath('candidates/EU26-07/environments/matlab')
config = struct( ...
    'n', 20, ...
    'k', 4, ...
    'update_factor', 1.5, ...
    'runs', 500, ...
    'base_seed', 1, ...
    'max_evaluations', 2.1e9, ...
    'output_csv', 'eu26-07-matlab-runs.csv');
report = eu2607_run_paper_batch(config);
```

The batch seed ledger is auditor-defined until a publication-specific seed
mapping is authenticated. Incomplete runs never receive an unqualified mean or
quantile summary.

### MATLAB/GNU Octave verification

```bash
octave --quiet --eval \
  "addpath('candidates/EU26-07/tests/matlab'); run_matlab_tests"
```

The tests cover the complete paper runner, `n=60` bit vectors, half-up versus
Python ties-to-even rounding, exact mutation, crossover, final-pool isolation,
pre-replacement success, reset delay, accounting, batch CSV output and negative
fail-closed cases.

## Authenticated Python artifact profile

Frozen artifact target: the resetting self-adjusting profile on `Jump_4`,
`n=20`, with `lambda_0=1`, `lambda_max=20`, `F=1.5`, and 500 published runs
from base seed `816114841`. The author processed result reports mean
`108964.48`, median `84730`, Q1 `32787`, and Q3 `150829` logical evaluations.

Artifact status: **`PASS_TARGET_ARTIFACT_REPLAY`**.

All 500 source-native rows and all 500 independent compatibility rows matched
the authenticated author ledger exactly for every frozen field. The canonical
row digest is
`6e5b6b6da38d0c2d846b3379150532667447a0ff38fb64aae3148149db41d176`.
The retained report is in [`results/formal-full-replay.json`](results/formal-full-replay.json).

Python remains necessary for this narrow evidence because the historical
artifact and author implementation are Python files. It is no longer the
recommended language for the independent paper reproduction.

## Three explicitly separate semantics

| Profile | Rounding | Final selection pool | Purpose |
|---|---|---|---|
| `paper_algorithm3_fixed_order` | nearest, half up | selected best mutant + crossovers | Primary MATLAB paper reproduction |
| `artifact_generic` | Python ties to even | all mutants + crossovers | Generic source diagnostics |
| `artifact_jump_optimized` | Python ties to even | all mutants + crossovers, with Jump shortcuts | Exact raw-ledger replay |

The paper and author source are not interchangeable. Their rounding rules,
final pools, update ordering and Jump shortcuts differ. A successful MATLAB
run therefore cannot be compared row-for-row with the author artifact unless a
separate compatibility profile is explicitly selected.

## Claim boundary

The current strongest claims are:

- `PASS_TARGET_ARTIFACT_REPLAY` for the authenticated Python artifact profile;
- `PASS_PAPER_FORMULA_PROFILE` for independent formula and fixed-tape checks;
- a full MATLAB paper runner is implemented and testable, but published MATLAB
  result reproduction requires a separately frozen experiment cell, seed
  protocol and acceptance rule.

`PASS_FULL` remains forbidden while the printed paper, generic source and
Jump-specialized artifact have unresolved semantic differences. No GPL source
or raw result file is vendored.
