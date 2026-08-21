# EU26-27 - self-adaptive GSEMO OLD-first candidate

Research tag: `RESEARCH_2`

## Final audited status

```text
candidate identity: PASS
EU affiliation: PASS_LEIDEN_UNIVERSITY_NETHERLANDS
dimension: PASS_N_100
printed adaptive formulas: PASS
Zenodo artifact authentication: PASS
selected schema/parser mapping: PASS
100-run raw endpoint availability: PASS
independent clean-room OLD distributional compatibility: FAIL
mandatory exact author implementation revision: FAIL
OLD: REJECTED
HYBRID: BLOCKED_NOT_AUTHORIZED
PR #22: CLOSED_NOT_MERGED
PR #19 numerical evidence used: false
```

This README supersedes the earlier `AUDIT_RUNNING` wording. The final decision is fail-closed.

## Candidate

Furong Ye, Frank Neumann, Jacob de Nobel, Aneta Neumann and Thomas Bäck,
*What Performance Indicators to Use for Self-Adaptation in Multi-Objective
Evolutionary Algorithms*, GECCO 2024, DOI `10.1145/3638529.3654073`, open
preprint `arXiv:2303.04611`.

The study evaluates 100-dimensional binary multi-objective problems OneMinMax,
LOTZ and COCZ in 100 independent runs. The EU-affiliation gate is satisfied by
Leiden University, Netherlands.

## What passed

- Zenodo record `7880836` and the selected raw-result member were authenticated;
- selected result schema and parser mapping passed;
- the frozen two-rate GSEMO / OneMinMax / `n=100` / `lambda=10` profile exposes
  100 complete raw runs;
- formula, OneMinMax objective, hypervolume, archive, negative-control,
  effort-accounting and deterministic test kernels were implemented;
- several Linux/macOS/Windows smoke jobs completed successfully;
- the raw endpoint recomputes to mean `61623.78` and median `57717.5` function
  evaluations in the audited workflow.

These facts do not establish OLD reproduction.

## Decisive OLD failures

### 1. Independent distributional compatibility failed

The full OLD workflow run `32413804943` reported for workers=1:

```text
raw runs: 100
raw median FE: 57717.5
independent runs: 100
independent median FE: 119601.0
median ratio: 2.072179148438515
95% interval for ratio: [1.9015896717026757, 2.3347756733466567]
empirical Kolmogorov distance: 0.74
ratio gate: FAIL
Kolmogorov gate: FAIL
status: FAIL_OLD_DISTRIBUTIONAL_COMPATIBILITY
```

The 100-run campaign therefore does not reproduce the selected raw-result
distribution under the clean-room implementation. Proximity of the raw mean to
a paper-level displayed value is not used to override this failure.

### 2. Preregistered source-provenance gate failed

Before outcomes were read, the eligibility contract required either algorithm
source-code members in the artifact or an exact author implementation revision.
The retained audit found result artifacts but no exact implementation revision
that can close this gate. Weakening this requirement after seeing results would
be post-hoc criterion modification.

Either failure is sufficient to reject OLD. Together they make the decision
unambiguous.

## OLD formulas retained as research context

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

Log-normal and variance-controlled variants are retained only as literature and
formula context; no positive OLD claim is derived from them in this branch.

## HYBRID status

No valid executable HYBRID result exists for EU26-27. The project rule is:

```text
PASS_OLD -> preregister HYBRID -> run paired evidence
FAIL_OLD -> HYBRID remains blocked
```

Because OLD failed, transferring the PR #8 reset self-adjusting
`(1+(lambda,lambda))` controller is not scientifically authorized for this
candidate. There is no HYBRID quality, iteration, NFE, worker or wall-clock
improvement claim.

## Scientific novelty boundary - Research 2

`RESEARCH_2` identifies the second thesis research line / candidate-improvement
cycle, not a positive result label.

The intended novelty hypothesis was to compare an OLD self-adaptive
multi-objective mutation-control mechanism with a separately preregistered
reset self-adjusting search-control layer under equal objective and effort
budgets. EU26-27 does not validate that hypothesis because OLD did not pass.

The defensible contribution of EU26-27 is methodological: it demonstrates an
artifact-first, outcome-blind rejection workflow that prevents a numerically or
conceptually attractive hybrid from being promoted when source provenance or
independent reproduction fails.

## Repository decision

PR #22 is closed without merge. The next candidate must branch directly from
`research/EU26-07-reset-jump-verification`, not from EU26-27.

See `SCIENTIFIC_NOVELTY_AND_PLAN.md` for the Research-2 plan and the comparison
with PR #17 and PR #19.
