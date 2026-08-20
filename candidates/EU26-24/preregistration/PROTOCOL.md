# EU26-24 outcome-blind OLD-first protocol

Date frozen: 2026-08-20

## 1. Purpose

The first purpose is to decide whether the released Preferendus min-max genetic
algorithm can reproduce the published floating-wind endpoint without tuning to
our observed results. The second purpose, conditional on OLD PASS, is to test a
single frozen PR #8-based hybrid under paired initial conditions and a matched
logical-evaluation budget.

No result from PR #19 is admissible as evidence. PR #19 may be consulted only
after a new HYBRID PASS for document structure and audit methodology.

## 2. Frozen source identities

- paper DOI: `10.1080/15732479.2023.2297891`
- arXiv: `2304.07168v3`
- upstream repository: `TUDelft-Odesys/Preferendus`
- upstream commit: `5b2e5c337b0b06cd4cf1c208de4c0679d64a2fe4`
- application blob: `40c93570741e41a9d7dd4b1030a1cb03f4582471`
- GA blob: `52cd003b1d1d2ab765d49a2937ad44b1db64c519`
- next-generation blob: `acf6cc3a68ed59f5212896e3d3280e4b450de9b0`
- decoder blob: `e00be76755dc9ee1b30d13ee419b0278924d484d`
- constraint blob: `e3aefd560e5c5e92f373c12717baa19c804fc010`
- weighted-minmax blob: `6318da4d2e198bdc8e1af2b3c5dd630b2c8efc83`

No upstream source byte is copied into this repository. The implementation is a
clean-room profile whose formulas are checked against the frozen blobs.

## 3. Frozen OLD profiles

### 3.1 Primary source-compatible profile

- problem: floating-wind installation min-max MODO;
- chromosome: 3 integer loci and two 24-bit real variables, 51 mutable loci;
- decoded bounds: `[0,3]`, `[0,2]`, `[0,2]`, `[1.5,4]`, `[2,8]`;
- population: 1500;
- maximum generations: 400;
- maximum stall: 20;
- crossover probability: 0.8;
- mutation-rate order: 4;
- elitism percentage: 10;
- constraint handler: released CND semantics;
- objective weights: `[0.30,0.35,0.15,0.20]`;
- fleet objective: released-code `prod_i p_i^(x_i^2)`;
- real decoding denominator: `2^24`, not `2^24-1`.

### 3.2 Printed-formula sensitivity profile

This profile changes only fleet utilisation to the printed
`prod_i p_i^x_i`. It is descriptive and cannot rescue a failed primary OLD
result.

## 4. Seed custody

The following seed sets are non-overlapping:

- implementation/unit fixtures: fixed tapes only;
- OLD pilot/debug seeds: `101..110`;
- HYBRID exploratory/training seeds, only after OLD PASS: `1001..1020`;
- final paired confirmatory seeds: `2001..2030`.

A seed may not move between sets. Confirmatory acceptance criteria may not be
changed after any confirmatory row is inspected.

## 5. OLD acceptance gates

### G0 - source and license

All identities in Section 2 must match. Apache-2.0 must be present at the frozen
upstream commit.

### G1 - formula micro-oracles

The test suite must cover at least:

- min-max aggregation;
- PCHIP preference anchors and clipping;
- project-duration discrete-event calculations;
- cost, fleet and emissions objectives;
- both constraints at feasible and infeasible boundary points;
- 24-bit decoding endpoints and midpoint;
- tournament, crossover and mutation boundary behavior;
- log-normal mutation update on a fixed Gaussian tape;
- paper/source fleet-formula divergence.

### G2 - deterministic engineering oracle

An independent enumeration over all 36 vessel combinations plus bounded
one-dimensional feasibility searches for anchor diameter/length must recover the
published source-compatible basin:

```text
vessels = [1,0,2]
diameter rounds to 2.2 m
length rounds to 8.0 m
```

### G3 - stochastic OLD campaign

The OLD campaign passes only if all are true:

1. at least 24 of 30 confirmatory runs are complete and feasible;
2. at least 24 of 30 return vessels `[1,0,2]`;
3. at least 24 of 30 have `2.15 <= diameter < 2.25` and `length >= 7.95`;
4. median project duration is within `91 +/- 0.5` days;
5. median cost is within `10.45E6 +/- 0.05E6` EUR;
6. median fleet objective is within `0.04375 +/- 0.005`;
7. median emissions are within `7135 +/- 25` t;
8. median preference scores are each within 2 points of `[43,38,97,15]`.

Failure of any numbered rule gives `REJECTED_OLD_REPRODUCTION`. HYBRID remains
forbidden.

### G4 - execution invariance

For identical seeds and initial populations, canonical scientific rows must be
identical for serial, 1-worker, 2-worker and 4-worker objective evaluation. Wall
clock time is excluded from the canonical digest.

## 6. Conditional HYBRID protocol

HYBRID may be developed only after G0-G4 PASS. Exploratory work may compare a
small bounded family of search-control placements using seeds `1001..1020`:

1. direct replacement of OLD mutation control;
2. stagnation-triggered PR #8 intensification;
3. generation-level PR #8 control of mutation/crossover intensity.

The family is declared before exploration. One and only one variant is frozen
for seeds `2001..2030`. No confirmatory retuning is permitted.

The PR #8 equations are:

```text
p_g = lambda_g / n
c_g = 1 / lambda_g
lambda_{g+1} = max(lambda_g/F, 1)                       on strict success
lambda_{g+1} = 1                                       on failure at cap with reset
lambda_{g+1} = min(lambda_g * F^(1/4), n)               otherwise
```

`F` and the placement rule must be frozen in a HYBRID amendment before the
first confirmatory run.

## 7. HYBRID success criterion

A positive thesis-level result requires all of the following on paired
confirmatory seeds:

- quality: Hybrid is non-inferior to OLD for final min-max objective with a
  predeclared relative margin of 0.5%;
- endpoint coverage: Hybrid reaches the published Table 3/4 basin in at least as
  many pairs as OLD;
- efficiency: the lower endpoint of a paired 95% BCa interval for median logical
  NFE reduction is at least 15%;
- robustness: no worker-dependent scientific digest and no increase in failed or
  infeasible runs;
- iteration result: median first-hit generation is lower than OLD.

Logical NFE counts calls at the min-max objective boundary. It is not treated as
equal to CPU time.

## 8. Environments and load profiles

The repository must contain:

- frozen Python requirements;
- Linux, macOS and Windows CI jobs;
- Python 3.11, 3.12 and 3.13 coverage where supported;
- workers 1, 2 and 4;
- smoke, medium and full logical-load profiles;
- exact seed, configuration and source digests in each retained result.

The expensive 30-seed campaign may run once in a canonical Linux environment.
Cross-platform jobs verify formula, serialization, workers and fixed-tape
scientific equivalence rather than claiming equal wall-clock performance.

## 9. Failure and cleanup rule

If OLD fails, executable candidate files are removed and only the rejection
ledger, source identities and reason remain. The next candidate starts from the
PR #8 base, not from the rejected branch.

If HYBRID fails, the negative result is retained. A different hybrid cannot be
silently selected using the confirmatory seeds.

## 10. Thesis gate

A new master thesis may be created only after a new candidate obtains OLD PASS
and HYBRID PASS. Until then, thesis material based on PR #19 is not a deliverable
for this cycle.
