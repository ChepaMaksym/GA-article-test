# EU26-27 OLD final status

## Decision

```text
FAIL_SOURCE_NATIVE_OLD
HYBRID_BLOCKED_NOT_AUTHORIZED
```

The preregistered exact-replay gate was not met after exhausting the justified
public recovery axes. This is a scientific mismatch, not merely a CI failure.

## Canonical profile

- author source: `FurongYe/GSEMO@fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380`;
- problem: OneMinMax, `n=100`;
- algorithm: TwoRate GSEMO;
- `lambda=10`;
- initial mutation rate: `1/100`;
- adaptation metric: hypervolume;
- budget: 100000 FE;
- runs: 100 sequential runs;
- author RNG semantics: one global stream seeded once with `10`;
- authenticated reference member: `csv/om/TwoRateL10P1HVOneMaxD100.csv`;
- authenticated raw mean: `61623.78 FE`;
- paper Table-1 display: `61624 FE`.

## Recovery ledger

| Environment/source | Complete | Mean FE | Raw first-hit matrix | Endpoint vector | Decision |
|---|---:|---:|---|---|---|
| final source + IOH v0.3.9 + GCC9 | 97/100 | 58909.58 | mismatch | mismatch | NO_EXACT_MATCH |
| final source + IOH v0.3.9 + GCC10 | 97/100 | 58909.58 | mismatch | mismatch | NO_EXACT_MATCH |
| final source + IOH v0.3.9 + GCC11 | 96/100 | 59467.99 | mismatch | mismatch | NO_EXACT_MATCH |
| final source + IOH v0.3.9 + GCC12 | 96/100 | 59467.99 | mismatch | mismatch | NO_EXACT_MATCH |
| final source + IOH v0.3.9 + GCC13 | 96/100 | 59467.99 | mismatch | mismatch | NO_EXACT_MATCH |
| early compatible IOH `8d21f4f...` + GCC10 | 0/100 | 100001.00 | mismatch | mismatch | NO_EXACT_MATCH |
| paper-era GSEMO source generations S01-S09 | varied | varied | mismatch | mismatch | NO_EXACT_MATCH |

Additional facts:

- GCC9/GCC10 incomplete runs: `[16, 56, 80]`;
- GCC11-GCC13 incomplete runs: `[46, 55, 68, 76]`;
- GCC7/GCC8: build-incompatible with the frozen final source;
- no tested environment achieved exact matrix or endpoint equality;
- no post-hoc tolerance, seed deletion, subset selection or aggregate-only pass
  was introduced.

## GitHub Actions evidence

- paper-era source matrix: `32476003177`;
- source recovery on final head: `32480506999`;
- historical dependency recovery: `32480506993`;
- historical compiler recovery: `32480506994`;
- canonical source-native OLD: `32480506997`.

Recovery workflows deliberately return execution success for scientific
mismatches so every environment retains artifacts. Their job color is not the
OLD decision. The exact-replay binder is the scientific gate.

## Claim boundary

Permitted:

- the public source/data/profile can be authenticated;
- the public information is insufficient to reconstruct the exact historical
  stochastic trajectory under the frozen gate;
- this candidate fails the project OLD prerequisite.

Forbidden:

- `PASS_SOURCE_NATIVE_OLD`;
- any EU26-27 HYBRID quality/efficiency result;
- choosing a recovery environment because its mean is closer to 61623.78;
- treating a green diagnostic workflow as scientific reproduction;
- using PR #19 numerical evidence to repair the failure.
