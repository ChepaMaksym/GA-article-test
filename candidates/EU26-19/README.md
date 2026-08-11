# EU26-19 - STLA-style adaptive GA on Robot Execution Failures -> PR8 hybrid

## Goal

Reproduce an applied adaptive-GA feature-selection experiment before any hybridization, then (only after OLD passes) test a hybrid that imports the verified PR #8 `(1+(lambda,lambda))` self-adjusting mutation/crossover search mechanism.

## Applied problem

Robot Execution Failures (UCI/KDD): force/torque time-series classification after detected robot failures. Each observation contains 15 time samples x 6 force/torque channels = **90 raw task variables**, well above the required 15. The five public learning problems contain 88, 47, 47, 117, and 164 observations respectively.

The feature-subset landscape is combinatorial (`2^d` subsets), non-convex/discrete and contains many local optima under wrapper-classifier accuracy.

## Research anchor

Primary methodological anchor: Ooi et al., *Self-Tune Linear Adaptive-Genetic Algorithm for Feature Selection*, IEEE Access 7 (2019), DOI `10.1109/ACCESS.2019.2942962`.

The paper applies an adaptive GA to feature selection and explicitly motivates the method through the exploration/exploitation and premature-convergence problem. Its adaptive mechanism changes mutation probability linearly over the run.

## Evidence freeze

- Original UCI/KDD dataset semantics: 90 numeric raw features per observation, no missing values.
- Pinned public mirror used for byte-addressable fixtures: `Rochy0509/ailab-core`, commit `c02b5e989b3df4fb01fc7829c7737286254e3bff`.
- Dataset file identities at that mirror:
  - LP1 SHA `5a2082daecc1c22c0941a99f35b1fa1ec5615057`
  - LP2 SHA `7e2ca8ebae42545ed4903ffcb62441c3566e1d6f`
  - LP3 SHA `69555cfa0de983c5f8299531b220917c863ad7be`
  - LP4 SHA `5d0369e7a830a2b845ab26b847d8c953e752c232`
  - LP5 SHA `b221d19a782fec996b9baa26d7d9aacb1c54477e`

## OLD/HYBRID hard gate

`old/` must be implemented and verified first. `hybrid/` must contain no executable optimizer until OLD reaches the numerical reproduction gate.

If the exact paper endpoint cannot be reconstructed because a required preprocessing, classifier, split, parameter, seed protocol, or numeric target is absent, the candidate is **REJECTED** rather than silently tuned until it looks good.

## Verification ladder

1. `V0_SOURCE` - DOI, algorithm equations, experimental constants, and evidence identities frozen.
2. `V1_DATA` - parser reproduces published UCI instance counts, 90 variables, class labels, and no missing values.
3. `V2_FEATURES` - any paper-required transformation is independently tested against its definition.
4. `V3_OLD_FORMULA` - adaptive mutation schedule and GA operators pass fixed-tape tests.
5. `V4_CLASSIFIER` - wrapper classifier protocol is deterministic under a frozen split/seed and cannot leak test data.
6. `V5_OLD_NUMERIC` - independent repeated runs reproduce the selected paper table/figure endpoint within a preregistered tolerance.
7. Only after `V5_OLD_NUMERIC=PASS` may executable code be added to `hybrid/`.

## Planned hybrid (not implemented yet)

Preserve the applied feature-selection objective and data protocol from OLD. Replace only the selected GA search-control layer with the PR #8 verified self-adjusting `(1+(lambda,lambda))` mechanism (`p=lambda/n`, `c=1/lambda`, success-based lambda update/reset), adapted to binary feature masks. All classifier/data components remain frozen.

## Current status

`PREREGISTERED_OLD_ONLY`
