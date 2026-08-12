# EU26-21 - CHC-QX Census-Income plus Hybrid 1

## Current status

- `old/`: `PASS_SOURCE_NUMERIC_ALIGNMENT` for the pinned public CHC-QX implementation;
- literal paper/source reconciliation: still documented as incomplete;
- `hybrid/`: retired documentation-only placeholder retained for provenance;
- `hybrid_1/`: user-authorized Step 2 implementation and experiment;
- applied Census improvement: not yet claimed until the paired campaign passes.

Paper used for the applied OLD baseline:

Mohammed Ghaith Altarabichi, Sławomir Nowaczyk, Sepideh Pashami, and Peyman Sheikholharam Mashhadi, **Fast Genetic Algorithm for feature selection - A qualitative approximation approach**, Expert Systems with Applications 211 (2023) 118528, DOI `10.1016/j.eswa.2022.118528`.

Parameter-control paper used for Hybrid 1:

Mario Alejandro Hevia Fajardo and Dirk Sudholt, **Theoretical and Empirical Analysis of Parameter Control Mechanisms in the `(1+(lambda,lambda))` Genetic Algorithm**, ACM Transactions on Evolutionary Learning and Optimization 2(4), DOI `10.1145/3564755`.

## Applied problem

- Census-Income income classification;
- 199,523 observations;
- 41 task features;
- binary search space of `2^41` feature masks;
- Decision Tree evaluation under the frozen author-source 60/20/20 protocol.

## Frozen OLD evidence

Repository: `Ghaith81/Fast-Genetic-Algorithm-For-Feature-Selection`.

Commit: `6ac5a7ec77f8a7c096ab4d019254fcc897988fd6`.

Pinned blobs:

- `code/Dataset.py`: `18c8d417f7236ef0af3c8a35279a1914679cac74`;
- `code/Evolution.py`: `05b0d8afc02faee688e5d1ff8e24531ae41307c7`;
- `code/Example.ipynb`: `87d2ea5caada5278853553de2c73d2ec6083f9b6`;
- `data/census-income.data`: `e780a25c2dec3f1a10d65cca9ea05001a77b37b6`.

The ten-seed source campaign reproduced:

- all-feature baseline: `92.8681%`;
- CHC-QX median test accuracy: `94.9455%`;
- sample standard deviation: `0.0336` percentage points;
- 10/10 completed runs plus an exact repeat of seed 1.

Detailed OLD evidence remains in `old/SOURCE_STATUS.md` and
`old/PAPER_SOURCE_DIVERGENCES.md`.

## Hybrid 1 intervention

Hybrid 1 preserves the applied data, split, normalization, active sample,
classifier, validation objective, and held-out test. It replaces only the
feature-mask search layer with reset self-adjusting `(1+(lambda,lambda))`:

- `m = round_half_up(lambda)`;
- mutation probability `p=lambda/41`;
- crossover probability `c=1/lambda`;
- strict-success shrink;
- failure growth by `F^(1/4)`;
- failure at `lambda=41` resets lambda to 1.

Fitness is lexicographic:

```text
(validation accuracy, - selected_feature_fraction)
```

Thus accuracy always dominates sparsity.

## Verification strategy

1. exact control/formula and fixed-tape tests;
2. Jump local-optimum reset-vs-no-reset confirmation;
3. OneMax no-regression control;
4. exact 1/2/4 evaluation-worker invariance;
5. exact 1/2/4 process-worker campaign invariance;
6. Census data-boundary and held-out-test smoke;
7. paired Census reset-vs-no-reset pilot;
8. final ten-seed applied campaign for H1-H3.

The complete hypotheses and pass thresholds are frozen in
`hybrid_1/HYPOTHESES.md`.

## Claim boundary

A passing Jump result proves that the transferred reset controller improves the
selected local-optimum control problem. It does not prove an applied Census
improvement. That conclusion requires the frozen paired Census campaign.
