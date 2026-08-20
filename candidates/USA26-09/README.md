# USA26-09 - adaptive HGA for min-max mTSP, OLD first

## Final status

```text
OLD compatibility gate: PASS_OLD_COMPATIBILITY
HYBRID joint gate: PASS_HYBRID
worker invariance 1/2/4: PASS
reset stress mechanism: PASS_RESET_EXERCISED
cross-machine GitHub matrix: PENDING_CURRENT_HEAD_CI
master-thesis evidence status: READY_AFTER_CI
```

This branch is a new candidate cycle created directly from the verified PR #8 base. No numerical row, figure, implementation, or scientific decision from PR #19 is used as evidence.

## Candidate

Sasan Mahmoudinazlou and Changhyun Kwon, *A hybrid genetic algorithm for the min-max Multiple Traveling Salesman Problem*, Computers & Operations Research 162 (2024) 106455, DOI `10.1016/j.cor.2023.106455`.

The study satisfies the candidate filter:

- 2024 journal publication;
- qualifying United States affiliation at the University of South Florida;
- 49 decision loci in the frozen 50-node instance, well above the >10 requirement;
- non-physical, combinatorial min-max routing;
- synthetic uniform benchmarks and public TSPLIB families;
- an explicit in-run adaptive local-search controller;
- author-linked Julia source at commit `7d9fa1f63dfae44506f33a43aaa812793bebc065`.

The upstream repository has no project-wide license file. Therefore this branch contains an independent clean-room Python implementation and no copied upstream source or data bytes.

## Problem and objective

For a customer set partitioned into `m` depot-returning tours, the objective is

```text
minimize max_r C(T_r)
```

where `C(T_r)` is the length of route `r`. A permutation chromosome is evaluated by an exact dynamic split that finds the best contiguous `m`-route partition for that permutation.

## OLD adaptive formula

The published HGA selects one of four intra-route moves using improvement counts:

```text
w_i(0) = 100
p_i(g) = w_i(g) / sum_j w_j(g)
w_i(g+1) = w_i(g) + 1  if move i produces a strict improvement
w_i(g+1) = w_i(g)      otherwise
```

The four frozen moves are Reinsert, Exchange, Or-opt2, and Or-opt3. Thus OLD adapts **which local operator** is used, while its search effort per generated child remains fixed.

## HYBRID formula

HYBRID retains the OLD adaptive roulette and adds the verified reset self-adjusting `(1+(lambda,lambda))` control:

```text
p_g = lambda_g / n
c_g = 1 / lambda_g
offspring_g = round_half_up(lambda_g)

strict success: lambda_{g+1} = max(lambda_g / F, 1)
failure:        lambda_{g+1} = min(lambda_g * F^(1/4), n)
failure at cap: lambda_{g+1} = 1
F = 1.5
```

In the permutation domain, `p_g` controls the number of exact permutation edits, `c_g` controls biased order mixing, and `round(lambda_g)` controls the candidate count. This transfer preserves valid permutations and leaves the objective, instance, initial population, seed ledger, and logical evaluation budget unchanged.

## Frozen protocol

- instance: 50 nodes, 49 customers, 10 salesmen;
- coordinates: uniform `[0,1]^2`, seed `20240809`;
- instance SHA-256: `ff4bab102b3587246c5d8df898232939f9ea9a77e25e582fda906b32c47bf8d6`;
- pilot seeds: `1001..1005`, excluded from inference;
- confirmatory seeds: `2001..2030`;
- budget: 1500 logical split evaluations per method and seed;
- matched target: `1.830`;
- same initial-population digest within every OLD/HYBRID pair.

The paper reports `1.82` for the Set-I `N=50, m=10` HGA average. Exact historical replay is impossible because the 100 instance seeds and ten per-instance search seeds are not published. The OLD decision is therefore explicitly a **published-cell compatibility gate**, not an exact author-seed replay.

## Results

```text
OLD median final objective:       1.8290005
HYBRID median final objective:    1.8288548
paired median HYBRID - OLD:      -0.0001457
95% paired bootstrap:            [-0.0020580, 0.0000000]

OLD target coverage:             16/30
HYBRID target coverage:          28/30

OLD median capped logical NFE:   1432.5
HYBRID median capped logical NFE: 423.5
paired median NFE reduction:     49.6597%
95% paired bootstrap:            [34.3333%, 72.7667%]
```

Final preregistered decision:

```text
quality non-inferiority: PASS
coverage:                PASS
logical-NFE efficiency:  PASS
joint HYBRID gate:       PASS_HYBRID
```

## Claim boundary

The supported claim is a paired improvement in **search efficiency with preserved final quality on one frozen synthetic 50-node profile**. The branch does not claim:

- exact historical Table-2 reproduction;
- global superiority over all mTSP algorithms;
- wall-clock speedup from logical NFE alone;
- that reset alone caused the primary improvement;
- transfer to all instance sizes, salesmen counts, or TSPLIB families;
- permission to reuse unlicensed upstream source code.

See `SCIENTIFIC_NOVELTY_AND_CLAIMS.md`, `HYBRID_RESULTS.md`, and `PROFESSOR_FORTIFICATION_UA.md`.

The complete executable source, tests, retained rows, tables, and figures are preserved in the SHA-authenticated `usa26-09-reproducibility-bundle.zip`; see `BUNDLE_MANIFEST.md`.
