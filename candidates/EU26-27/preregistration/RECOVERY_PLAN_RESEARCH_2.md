# RESEARCH_2 - EU26-27 recovery plan

Date frozen: 2026-08-21

## Purpose

This recovery iteration is diagnostic and source-constrained. It must not tune
implementation choices until the result resembles the retained Zenodo data.
The already observed baseline failure remains immutable:

```text
uniform random tie-breaking, balanced 5/5 lower-higher split
raw median FE = 57717.5
independent median FE = 119601.0
median ratio = 2.072179148438515
Kolmogorov distance = 0.74
status = FAIL_OLD_DISTRIBUTIONAL_COMPATIBILITY
```

The recovery question is whether a *pre-specified paper-grounded ambiguity* can
explain the failure. A diagnostic match cannot override the still-mandatory
author-source provenance gate.

## Primary source facts

For the two-rate GSEMO the paper states:

- offspring size `lambda = 10` for the reported cell;
- each offspring independently selects a parent uniformly from the
  pre-generation non-dominated set;
- half use mutation probability `r/(2n)` and half use `2r/n` in the prose;
- Algorithm 2 uses one-based indices and the literal condition
  `i < floor(lambda/2)`;
- the best offspring is selected by `arg max e(y)`;
- if the winner belongs to the lower-rate block, shrink probability is `3/4`,
  otherwise `1/4`;
- `r` is capped to `[1/2, n/4]`;
- all offspring are inserted through the GSEMO dominance update;
- the HV reference point is `(-1,-1)`;
- OneMinMax, `n=100`, 100 independent runs, `lambda=10`.

The paper does not specify tie-breaking for `arg max`.

## Frozen diagnostic factors

Only the following two factors may vary in the recovery campaign.

### Factor A - winner tie policy

`uniform`:
: uniformly sample among all offspring with maximal `e(y)`; this is the
  rejected baseline interpretation.

`first`:
: select the first maximal offspring in generation order. This is a common
  literal array-`argmax` semantics and introduces no extra RNG draw.

The campaign does **not** claim that `first` is the historical author behavior
unless an exact author implementation revision is later found.

### Factor B - lower/higher block split

`balanced`:
: five lower-rate and five higher-rate offspring, matching the prose "50%".

`literal_one_based`:
: lower-rate iff one-based `i < floor(lambda/2)`. With `lambda=10`, this yields
  four lower-rate and six higher-rate offspring and also classifies the winner
  using the same one-based boundary.

This tests a real prose/pseudocode discrepancy rather than an outcome-selected
parameter.

## Frozen 2x2 recovery matrix

```text
R1 = uniform tie + balanced split         [existing failed baseline]
R2 = first tie   + balanced split
R3 = uniform tie + literal_one_based split
R4 = first tie   + literal_one_based split
```

All variants use the same independent seeds `270001..270100`, `n=100`,
`lambda=10`, PCG64DXSM RNG, 2,000,000 FE cap, objective, archive semantics,
conditional non-zero mutation, raw endpoint and statistical gates.

## Diagnostic statistics

For each variant retain:

- 100 run endpoints;
- complete-run count;
- mean, median, standard deviation, quartiles, min/max;
- median ratio versus the exact same retained raw distribution;
- 20,000-resample bootstrap 95% interval for the median ratio;
- empirical Kolmogorov distance;
- lower/higher winner counts;
- final-rate distribution;
- generated-offspring and flipped-bit effort;
- exact campaign digest.

The original compatibility bounds remain unchanged:

```text
median-ratio bootstrap interval fully inside [0.90, 1.10]
Kolmogorov distance <= 0.20
100/100 complete
```

These gates classify `DIAGNOSTIC_DISTRIBUTIONAL_MATCH`; they do not promote
OLD to full reproduction while exact author source provenance is unresolved.

## CI/CD recovery gates

1. Move multiprocessing smoke execution out of `python -` / stdin and into an
   importable module with a guarded `main()`. This specifically addresses
   spawn-mode failures on Windows and macOS.
2. Run unit tests and coverage on Linux, macOS and Windows.
3. Test workers `1/2/4` as isolated factors, not mixed with OS/Python when
   proving worker invariance.
4. Require identical canonical campaign digests across workers for each
   deterministic seed ledger and variant.
5. Build a final binder only from uploaded immutable artifacts.
6. Fail closed on any missing artifact, malformed row, duplicate seed,
   non-finite value, incomplete run, digest mismatch or failed upstream job.
7. Graph generation is downstream of evidence binding and never changes the
   scientific decision.

## Graphs

Generate from immutable JSON/CSV only:

- ECDF of FE for raw + R1..R4;
- box/violin-style summary rendered as boxplots for FE distributions;
- median-ratio with 95% bootstrap interval by variant;
- mutation-rate/final-rate distribution by variant;
- worker digest/status matrix;
- convergence diagnostic from first-hit coverage if available.

All figures must include the source run/commit SHA and data SHA-256 in a
machine-readable sidecar manifest.

## Decision rule

```text
if no R2-R4 variant passes the frozen diagnostic gates:
    EU26-27 remains REJECTED; delete recovery executable files and move on.

if one or more R2-R4 variants pass:
    status = RECOVERY_DIAGNOSTIC_MATCH_ONLY
    continue searching for the exact author implementation/source revision.
    HYBRID remains blocked until source provenance is independently closed.
```

No recovery outcome can retroactively weaken the author-source requirement of
PR #22.
