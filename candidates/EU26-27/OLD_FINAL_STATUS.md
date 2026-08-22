# EU26-27 OLD final status

## Decision

```text
PASS_SOURCE_NATIVE_OLD
HYBRID_AUTHORIZED_FOR_SEPARATE_PREREGISTERED_STAGE
```

The unchanged paper-era author implementation exactly reproduces the authenticated
Zenodo raw trajectory when it is executed according to the paper's reported stop
semantics: function evaluations until the entire Pareto front is obtained.

The earlier 100000-FE replay is retained only as a diagnostic reconstruction error.
It is not the canonical OLD because the paper's experimental setup does not state a
100000-FE cap and the authenticated raw data contain endpoints above 100000 FE.

## Canonical profile

- author source: `FurongYe/GSEMO@fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380`;
- dependency: `IOHprofiler/IOHexperimenter@f223c682dff0749067d00b870f83ad754f7d96f5` (`v0.3.9`);
- problem: OneMinMax, `n=100`;
- algorithm: TwoRate GSEMO;
- `lambda=10`;
- initial mutation rate: `1/100`;
- adaptation metric: hypervolume;
- runs: 100 sequential runs;
- author RNG semantics: one global stream seeded once with `10`;
- paper stop quantity: FEs until the entire Pareto front is obtained;
- replay safety ceiling: `10000000 FE`, explicitly non-binding and not claimed as a paper parameter;
- authenticated reference member: `csv/om/TwoRateL10P1HVOneMaxD100.csv`;
- authenticated raw mean: `61623.78 FE`;
- paper Table-1 display: `61624 FE`;
- maximum authenticated endpoint: `131875 FE`.

Canonical replay command:

```text
./gsemo 1 100 TwoRate 10 1 1 10000000 100
```

The `10000000` argument exists only because the author executable requires a budget
argument. The author implementation terminates each run as soon as the complete
Pareto front has been found, so this ceiling does not determine any observed endpoint.

## Exact replay result

GitHub Actions run `32565217851` produced:

```text
decision: PASS_PAPER_FAITHFUL_OLD
complete source runs: 100/100
incomplete source runs: []
paper/Zenodo mean FE: 61623.780000
source mean FE: 61623.78
max Zenodo endpoint FE: 131875
non-binding safety cap FE: 10000000
exact first-hit matrix: True
matrix mismatches: 0
exact endpoint vector: True
endpoint mismatches: 0
```

This result is now promoted into the canonical `PASS_SOURCE_NATIVE_OLD` gate.
The canonical workflow and comparator use that decision name directly.

## Why the earlier 100k replay failed

The earlier command was:

```text
./gsemo 1 100 TwoRate 10 1 1 100000 100
```

Runs before the first binding truncation followed the authenticated endpoint vector.
At run 46 the Zenodo endpoint is `131875 FE`, which cannot be produced under a
100000-FE ceiling. Because the author seeds one global RNG stream once before all
100 sequential runs, truncating one run changes the RNG state entering later runs and
therefore creates a cascade of later trajectory mismatches.

The compiler/dependency/source-recovery matrices generated under that artificial cap
remain useful forensic evidence, but they do not contradict the canonical exact replay.

## PASS gate satisfied

All mandatory conditions are met:

1. exact frozen GSEMO source identity;
2. exact frozen paper-era IOHexperimenter identity;
3. unchanged author algorithm source before and after build;
4. 100/100 sequential runs complete;
5. exact authenticated 101×100 first-hit matrix equality;
6. exact 100-run endpoint-vector equality;
7. authenticated raw mean `61623.78 FE` aligns with paper Table 1 `61624 FE`;
8. comparator negative controls pass;
9. the safety ceiling is proven non-binding against the authenticated endpoint vector.

## Claim boundary

Permitted:

- `PASS_SOURCE_NATIVE_OLD`;
- exact source-native reproduction of the authenticated Zenodo trajectory for the frozen
  OneMinMax TwoRate+HV profile;
- use of this OLD as the baseline for a separately preregistered HYBRID stage;
- reporting the 100k experiment only as diagnostic evidence explaining the previous false rejection.

Still forbidden:

- claiming the 10,000,000 FE safety ceiling is a published budget;
- claiming cross-platform raw stochastic equality from build/smoke checks alone;
- splitting the historical 100-run global RNG stream across workers and calling it the same experiment;
- claiming HYBRID improvement before the HYBRID experiment itself passes its quality and efficiency gates;
- treating OLD reproduction itself as the master's scientific novelty.
