# EU26-20 - CMF-AGAwER -> PR8 hybrid

## Candidate

Hossein Nematzadeh, José García-Nieto, Ismael Navas-Delgado, José F. Aldana-Montes, **Feature selection using a classification error impurity algorithm and an adaptive genetic algorithm improved with an external repository**, Knowledge-Based Systems 301 (2024) 112345, DOI `10.1016/j.knosys.2024.112345`.

Authors are based at Universidad de Málaga / IBIMA, Spain. The paper is open access and the authors publish the implementation and all benchmark datasets in `KhaosResearch/CMF-AGAwER`.

## Why this candidate fits

- Applied problem: high-dimensional biomedical feature selection.
- Explicit local-optimum/premature-convergence motivation.
- Adaptive GA: crossover probability and mutation probability change after stagnation.
- External repository adds diverse candidate solutions to improve exploration.
- Task dimensionality is far above 15: Colon alone has **2,000 input features**; other paper datasets reach 22,283.
- Exact public paper endpoint for Colon: decision-tree accuracy **0.69 before**, **0.94 after CMF-AGAwER**, average selected subset length **6**.
- Public author code and data make OLD reproduction materially auditable.

## Frozen OLD target

Primary target: **Colon** dataset.

Paper constants:

- samples: 62;
- raw features: 2,000;
- classes: 2 (22 / 40);
- top 50 CEI + top 50 MI + top 50 Fisher Ratio, unique concatenation defines AGAwER search space;
- `nPop = 10`;
- initial `Pc = 0.9`, `Pm = 0.4`;
- no improvement for 5 consecutive iterations -> `Pc -= 0.3`, `Pm += 0.2`;
- improvement -> reset to `Pc=0.9`, `Pm=0.4`;
- stop after 20 iterations without improvement, 100 maximum iterations, or fitness 1;
- external-repository diversity radius `max_distance / beta`, beta=2;
- initial solution length: 1..10 features;
- decision-tree classifier, random_state=42;
- paper reports 5-fold stratified CV for evaluation.

Author-source identities at the screened `main` snapshot:

- `CMF-AGAwER.py` blob `80ebd0599ac328e09373f21d3c61bb86004d184a`;
- `Datasets/Colon.xlsx` blob `0c02aa35b606e433079e4e858f091624f9ab05ab`;
- Colon `features.npy` blob `5ea58b5418a235ff1afcea97f76df81a07d9b1db`.

Before final numerical claims the workflow must additionally freeze an upstream commit SHA rather than rely on moving `main`.

## Hard OLD/HYBRID gate

Directory policy:

- `old/` contains the independent paper reproduction and verification.
- `hybrid/` is documentation-only until OLD passes.

No executable PR8 hybrid is permitted before `V5_OLD_NUMERIC=PASS`.

If the OLD result cannot reproduce the paper endpoint within the preregistered acceptance rule, this candidate is rejected and no hybrid result may be claimed.

## Verification ladder

1. `V0_SOURCE`: paper, source, data, feature-list identities and constants frozen.
2. `V1_DATA`: Colon = 62 x (2000 features + label), two classes with 22/40 distribution.
3. `V2_OPERATORS`: variable-length crossover, replacement mutation, RWS, repository distance and radius match paper/source.
4. `V3_ADAPTATION`: exact Pc/Pm schedule and reset semantics pass fixed-tape tests.
5. `V4_PROTOCOL`: decision-tree and CV protocol is frozen; stochastic seed ledger is explicit.
6. `V5_OLD_NUMERIC`: repeated OLD campaign targets paper accuracy 0.94 and subset length 6. Acceptance is based on confidence intervals / repeated-run distribution, not one lucky seed.
7. Only after V5 passes: implement `hybrid/` using PR #8 control.

## Hybrid hypothesis - frozen but not implemented

Keep the biomedical dataset, CMF feature pool, classifier, fitness and external-repository machinery unchanged. Replace only AGAwER's hand-stepped `(Pc,Pm)` stagnation controller with the verified PR #8 self-adjusting `(1+(lambda,lambda))` search-control layer adapted to variable-length feature subsets. Compare OLD vs HYBRID under equal fitness-evaluation budgets.

## Current status

`OLD_IMPLEMENTATION_IN_PROGRESS`
