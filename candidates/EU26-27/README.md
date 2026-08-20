# EU26-27 - self-adaptive GSEMO OLD-first candidate

## Current status

```text
candidate identity: PASS_PRELIMINARY
EU affiliation: PASS_LEIDEN_UNIVERSITY_NETHERLANDS
dimension: PASS_N_100
adaptive formulas: PASS_PRINTED_ALGORITHMS
Zenodo record: AUDIT_RUNNING
author source revision: NOT_YET_PINNED
OLD numeric profile: BLOCKED_BY_ARTIFACT_AUDIT
HYBRID: BLOCKED_BY_OLD
PR #19 numerical evidence used: false
```

## Candidate

Furong Ye, Frank Neumann, Jacob de Nobel, Aneta Neumann and Thomas Bäck,
*What Performance Indicators to Use for Self-Adaptation in Multi-Objective
Evolutionary Algorithms*, GECCO 2024, DOI
`10.1145/3638529.3654073`. The open preprint is arXiv `2303.04611`.

The study evaluates 100-dimensional binary multi-objective problems
OneMinMax, LOTZ and COCZ in 100 independent runs. Jacob de Nobel and Thomas
Bäck are affiliated with Leiden University, Netherlands.

## Paper formulas admitted for audit

Static GSEMO uses conditional standard bit mutation

```text
ell ~ Bin_{>0}(n, p), p = 1/n.
```

Two-rate GSEMO samples half of the offspring with `r/(2n)` and half with
`2r/n`, then updates

```text
winner from lower-rate half:
    r <- max(r/2, 1/2) with probability 3/4
    r <- min(2r, n/4) otherwise

winner from higher-rate half:
    r <- max(r/2, 1/2) with probability 1/4
    r <- min(2r, n/4) otherwise
```

Log-normal GSEMO samples, for every offspring,

```text
p' = (1 + ((1-p)/p) * exp(0.22 * N(0,1)))^(-1)
p' in [1/(4n), 1/2],
```

and inherits the rate of the best offspring.

Variance-controlled GSEMO samples

```text
ell ~ min{N_{>0}(r, F^c r(1-r/n)), n}, F = 0.98,
```

sets `r` to the winning mutation strength and increments `c` while `r`
remains unchanged.

The paper's final AGSEMO combines problem-extreme and non-extreme adaptation.
Its complete source transition and raw labels must be authenticated before
choosing a numerical OLD profile.

## Candidate admission rule

The candidate is admitted to implementation only if the Zenodo record
`10.5281/zenodo.7880836` and an author source provide all of:

1. machine-readable per-run results for an exact `n=100`, 100-run cell;
2. unambiguous algorithm/problem/offspring-size labels;
3. a legal file license and immutable checksums;
4. sufficient source semantics to implement the selected algorithm without
   outcome-informed assumptions;
5. a numerical endpoint recomputable from raw rows;
6. a frozen seed or run-order policy for independent OLD verification.

If any mandatory item fails, executable files are not added and EU26-27 is
rejected before HYBRID.

## HYBRID boundary

No executable HYBRID exists. After a full OLD pass, a separately preregistered
comparison may transfer the verified reset self-adjusting
`(1+(lambda,lambda))` control from PR #8. It must use identical objective
budgets and record objective evaluations, offspring evaluations, cache
statistics, mutation/crossover work, workers, machine profile and wall-clock
diagnostics. The exact mapping is frozen only after the OLD source semantics
are authenticated and before any HYBRID outcome is viewed.
