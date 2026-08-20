# EU26-27 two-rate GSEMO OLD endpoint freeze

Date frozen: 2026-08-21

## Outcome-exposure statement

This endpoint definition was committed before opening or aggregating the numeric values of the selected raw result member. Earlier schema-only jobs inspected the archive inventory, member names, row/column counts, header tokens and token classes, but did not retain the scientific outcome values.

## Selected paper/artifact profile

- Paper: Ye, Neumann, de Nobel, Neumann and Bäck, *What Performance Indicators to Use for Self-Adaptation in Multi-Objective Evolutionary Algorithms*, GECCO 2024, DOI `10.1145/3638529.3654073`.
- Preprint: arXiv `2303.04611`.
- Artifact: Zenodo record `7880836`, DOI `10.5281/zenodo.7880836`.
- Authenticated outer member: `csv.zip`.
- Frozen outer SHA-256: `2d5d3491c23e68bdd6d3c9c9dedfae67c805fa0588a3d443912c0b12c348fe4a`.
- Selected raw member: `csv/om/TwoRateL10P1HVOneMaxD100.csv`.
- Algorithm: two-rate GSEMO.
- Performance indicator: hypervolume (`HV`).
- Problem: OneMinMax (`OneMax` naming in the artifact), dimension `n=100`.
- Offspring population: `lambda=10`.
- Initial mutation-strength parameter: `r=1` (`P1` in the artifact name).
- Historical artifact runs: 100, indexed `0..99`.

## Frozen raw schema

The member must contain exactly 204 columns:

```text
pareto, algorithm, func, dimension,
found0, First_hit0, ..., found99, First_hit99
```

The data part must contain exactly 101 distinct Pareto-objective rows, corresponding to the complete OneMinMax front for `n=100`. The parser must reject duplicate run columns, duplicate Pareto rows, malformed booleans, non-integral first-hit values, negative counts, non-finite numbers, wrong dimensions, wrong algorithm/profile labels, extra columns and truncated rows.

## Frozen artifact endpoint

For historical run `s` and Pareto point `j`, let `H_s(j)` be the exact integer token in `First_hit{s}`. A run is complete only if every one of its 101 `found{s}` values is true.

The run-level full-front endpoint is

```text
E_s = max_j H_s(j)
```

No missing or unsuccessful run is silently censored or assigned the budget cap.

The primary artifact statistic is

```text
median(E_0, ..., E_99)
```

Secondary retained statistics are the mean, Q1, Q3, minimum, maximum, completion count, all 100 run endpoints in artifact order and a canonical SHA-256 digest of those endpoints.

## Printed-paper semantics gate

Before an independent OLD run is allowed, one written state-transition specification must resolve and test all of the following from the printed paper/source package:

1. uniform initialization and initial population content;
2. uniform parent selection from the current GSEMO population;
3. exact conditional standard-bit mutation semantics;
4. lower- and higher-rate offspring group sizes;
5. performance-indicator scoring and reference point;
6. winner and tie-breaking semantics used to update `r`;
7. rate update probabilities and clipping bounds;
8. whether population update processes the winner only or all generated offspring;
9. dominance/equality handling and update order;
10. first-hit and evaluation accounting;
11. termination at complete Pareto-front discovery.

An unresolved item is a hard blocker, not permission to choose the variant closest to the artifact after viewing results.

## Independent OLD campaign

If the printed-paper semantics gate passes, the clean-room implementation uses the immutable fresh seed ledger:

```text
2727001..2727100
```

The independent environment uses a declared deterministic RNG and a maximum of `2,000,000` logical objective evaluations per run. Incomplete runs remain incomplete.

## OLD acceptance rule

The strongest allowed result is distributional paper/artifact compatibility, not historical seed equality, because the historical RNG seed ledger is not published.

All gates are required:

1. exact replay of the selected raw artifact member and its 100 endpoints;
2. formula/fixed-random-tape and population-state-transition tests pass;
3. independent completion is `100/100` within the frozen cap;
4. the 90% paired-independent bootstrap interval for the log median-runtime ratio lies wholly inside `log([0.80, 1.25])`;
5. artifact and independent medians differ by at most 20%;
6. Q1 and Q3 ratios each lie within `[0.75, 4/3]`;
7. exact scientific digests match for workers `1`, `2` and `4` on the same runtime;
8. quantized scientific summaries agree across the declared Linux/macOS/Windows and Python matrix.

Failure of any required gate rejects EU26-27 before HYBRID. The margins may not be widened after outcome inspection.

## HYBRID prohibition

No executable PR #8 HYBRID and no positive novelty claim are permitted until the full OLD decision is `PASS_OLD_DISTRIBUTIONAL_COMPATIBILITY`. PR #19 results are excluded from this candidate.
