# Scientific novelty and claim limits

## What is not new

The project does not claim invention of genetic algorithms, min-max mTSP, dynamic Split, adaptive roulette local search, STX-style crossover, the `(1+(lambda,lambda))` GA, one-fifth-style parameter control, or failure-at-cap reset.

## Defensible novelty

The incremental scientific contribution is the controlled transfer and verification of a reset self-adjusting lambda mechanism into a permutation-coded min-max mTSP HGA that already adapts local-operator selection.

The two controllers act at different levels:

```text
OLD roulette: adapts WHICH local move is selected
HYBRID lambda: adapts HOW MUCH exploration, mutation strength, crossover bias,
               and candidate multiplicity are used
```

The methodological contribution combines:

1. clean-room objective, Split and permutation operators;
2. an OLD-first numerical compatibility gate;
3. paired seeds and byte-identical initial populations;
4. exact logical evaluation accounting;
5. preregistered quality, coverage and efficiency criteria;
6. worker-invariance checks;
7. low/medium/high NFE load profiles;
8. a reset/no-reset mechanism stress profile;
9. a Linux/macOS/Windows CI matrix with Python 3.11-3.13 and 1/2/4 workers.

## Why the new formula can improve efficiency

The OLD controller reinforces successful local moves but retains fixed search effort. It can therefore spend many evaluations even after a useful direction is found, while it has no independent mechanism for increasing global exploration after repeated failures.

The lambda controller creates a feedback loop:

- after strict success, lambda shrinks, reducing candidate count and mutation strength;
- after failure, lambda grows, increasing exploration and producing more candidates;
- crossover bias `1/lambda` changes in the opposite direction, balancing inherited and mutated structure;
- failure at the cap resets lambda to avoid remaining permanently in an expensive regime.

This explanation predicts fewer evaluations in easy phases and broader search during stagnation. The confirmatory result is consistent with that prediction: quality was preserved, target coverage increased, and median logical NFE fell by 49.66%.

## Allowed thesis statement

> The work proposes and reproducibly evaluates a dual-level adaptive HGA for min-max mTSP. The original success-weighted roulette adapts local-operator choice, while a transferred reset self-adjusting lambda formula adapts exploration strength and candidate multiplicity. On the frozen 50-node, 10-salesman, 30-seed profile, the hybrid preserved final objective quality, increased target coverage from 16/30 to 28/30, and reduced median capped logical evaluations from 1432.5 to 423.5. The result is limited to the preregistered profile and does not establish universal or reset-only superiority.

## Forbidden claims

Do not claim:

- “first in the world” without a systematic review;
- exact reproduction of the paper's Set-I seed ledger;
- statistically preregistered final-quality superiority;
- proportional wall-clock acceleration;
- reset-only causality;
- universal performance across mTSP instances;
- source-native equivalence to the unlicensed Julia repository;
- that PR #19 supplied any USA26-09 numerical evidence.
