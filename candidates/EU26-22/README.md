# EU26-22 - MOEA-ISa OLD-first audit

## Current decision

`CONDITIONAL_OLD_FORMULA_PASS / NUMERIC_REPRODUCTION_NOT_YET_PASSED / HYBRID_BLOCKED`

This is a new candidate cycle based directly on
`research/EU26-07-reset-jump-verification`. No result from PR #19 is reused.

## Candidate

Yu Xue, Xu Cai and Ferrante Neri, *A multi-objective evolutionary algorithm
with interval based initialization and self-adaptive crossover operator for
large-scale feature selection in classification*, Applied Soft Computing 127
(2022) 109420, DOI `10.1016/j.asoc.2022.109420`.

The publisher-linked source is `xueyunuist/MOEA-ISa`, frozen at commit
`e0f2f2312d18b9dccde5f707ea84b10a6c030a02`.

The study uses 15 real classification datasets with 100 to 7,129 feature
variables. Ferrante Neri is affiliated with the University of Surrey, UK.
The paper states 30 independent runs and the released `run.m` requests
population 100 and 10,000 evaluations.

## OLD formula verified so far

The clean-room kernel independently implements the deterministic control
semantics visible in the paper-linked MATLAB source:

- Jaccard parent similarity;
- 20 states at `0.05:0.05:1`;
- 10 crossover actions at `0.1:0.1:1`;
- MATLAB non-negative half-up rounding for crossover cardinality;
- five initialization intervals with probabilities
  `[0.6571, 0.1664, 0.0872, 0.0539, 0.0354]`;
- zero-probability roulette floor `0.03`;
- adaptive success table update
  `P_new=(1-alpha)P_old+alpha(NSC/NAC)`, `alpha=0.3`.

Local result: `8 passed`.

## Mandatory blockers before OLD numeric PASS

1. Released `run.m` calls `str2func(FS1)` instead of `str2func(FS)`.
2. Its loop variable `r` is not passed through `-run`, so there is no released
   immutable seed ledger.
3. The repository contains no retained 30-run raw result arrays.
4. The repository root exposes no explicit project-wide license; PlatEMO
   headers apply to inherited platform files, but do not automatically resolve
   reuse terms for every candidate-specific file or copied dataset.
5. The implementation requires MATLAB/PlatEMO and `relieff`; exact historical
   MATLAB/toolbox versions are not published.
6. A literal paper-table acceptance target and tolerance must be frozen before
   running a final campaign. It may not be chosen after seeing our results.

Until these are resolved, this branch may claim formula/source-transition
validation only. It may not claim paper reproduction or improvement.

## HYBRID gate

No executable HYBRID optimizer is present. It remains prohibited until an OLD
published-result cell passes a preregistered numeric rule. After that gate, the
data, split, objectives, population, evaluation budget and seed ledger stay
fixed; only the search-control layer may be replaced by the verified PR #8
reset self-adjusting `(1+(lambda,lambda))` control.

See `SCIENTIFIC_NOVELTY_PLAN.md` for the planned comparison.
