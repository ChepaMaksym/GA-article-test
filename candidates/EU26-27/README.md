# EU26-27 — source-native OLD for TwoRate GSEMO

Research tag: `RESEARCH_2`

## Final scientific status

```text
candidate identity: PASS
EU affiliation: PASS_LEIDEN_UNIVERSITY_NETHERLANDS
dimension: PASS_N_100
Zenodo raw data: PASS_AUTHENTICATED
author repository: PASS_FurongYe/GSEMO
paper-era author commit: PASS_fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
OLD implementation: SINGLE_SOURCE_NATIVE_AUTHOR_CODE
publication anchor: PASS_TABLE1_TWORATE_HV_61624
historical environment recovery: EXHAUSTED_JUSTIFIED_AXES
OLD: FAIL_SOURCE_NATIVE_OLD
HYBRID: BLOCKED_NOT_AUTHORIZED
PR #19 numerical evidence used: false
```

## Frozen OLD

The scientific OLD is the exact public author implementation:

```text
FurongYe/GSEMO
commit fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
2023-05-01, message: submission preparation
```

Frozen command:

```text
./gsemo 1 100 TwoRate 10 1 1 100000 100
```

This is OneMinMax `n=100`, TwoRate, `lambda=10`, initial `pm=1/100`,
hypervolume adaptation, 100000 FE and 100 sequential runs from the author's
single global IOHexperimenter RNG stream seeded once with `10`.

The matching publication anchor is paper Table 1:

```text
OneMinMax / two-rate GSEMO / HV / lambda=10: 61624 FE
Authenticated Zenodo raw endpoint mean:             61623.78 FE
```

The earlier `61618 FE` value belongs to AGSEMO in Table 2 and is not used by
this OLD.

## Preregistered pass rule

`PASS_SOURCE_NATIVE_OLD` required all of:

1. exact upstream source identity;
2. successful build of unchanged author algorithm source;
3. exactly 100 complete source-native runs;
4. exact 101x100 first-hit matrix equality with authenticated Zenodo data;
5. exact 100-run endpoint-vector equality;
6. matching paper Table-1 endpoint alignment;
7. fail-closed evidence and review.

No tolerance, subset, seed, aggregation, source revision, compiler or dependency
was selected because it happened to move an aggregate closer to Zenodo.

## Final recovery audit

The publicly recoverable historical axes were exhausted without an exact raw
replay.

| Recovery axis | Result | Complete runs | Censored mean FE | Exact matrix | Exact endpoint |
|---|---|---:|---:|---|---|
| final GSEMO + IOH v0.3.9 + GCC9 | NO_EXACT_MATCH | 97/100 | 58909.58 | false | false |
| final GSEMO + IOH v0.3.9 + GCC10 | NO_EXACT_MATCH | 97/100 | 58909.58 | false | false |
| final GSEMO + IOH v0.3.9 + GCC11 | NO_EXACT_MATCH | 96/100 | 59467.99 | false | false |
| final GSEMO + IOH v0.3.9 + GCC12 | NO_EXACT_MATCH | 96/100 | 59467.99 | false | false |
| final GSEMO + IOH v0.3.9 + GCC13 | NO_EXACT_MATCH | 96/100 | 59467.99 | false | false |
| early compatible IOH core `8d21f4f...` + GCC10 | NO_EXACT_MATCH | 0/100 | 100001.00 | false | false |
| nine unique paper-era GSEMO source generations | NO_EXACT_MATCH | varied | varied | false | false |

For GCC9/GCC10 the incomplete runs are `[16, 56, 80]`. For GCC11-GCC13
they are `[46, 55, 68, 76]`. The early compatible IOH state leaves all 100
runs incomplete. GCC7/GCC8 are source-build incompatible and therefore cannot
serve as historical executable environments.

The source-generation sweep covered the distinct paper-era `src/gsemo.hpp`
generations rather than repeatedly testing commits with identical algorithm
blobs. None reproduced the authenticated Zenodo trajectory.

## Evidence workflows

```text
paper-era source recovery:        run 32476003177
final-head source recovery:       run 32480506999
historical dependency recovery:   run 32480506993
historical compiler recovery:     run 32480506994
canonical source-native OLD:      run 32480506997 (scientific gate failed)
```

A green recovery job means the diagnostic executed and retained its evidence;
it does not mean scientific equality. The scientific decision is determined by
exact raw equality.

## Final decision

```text
EU26-27 = FAIL_SOURCE_NATIVE_OLD
HYBRID = BLOCKED_NOT_AUTHORIZED
```

The public paper profile, author source and Zenodo data are identifiable, but
the exact historical stochastic trajectory cannot be reconstructed from the
publicly preserved source/dependency/compiler information under the frozen
gate. Running a HYBRID against a baseline that failed this gate would invalidate
the OLD -> HYBRID comparison, so no EU26-27 HYBRID result is created.

This rejection does not alter the project-level HYBRID hypothesis. The next
candidate must start from the verified PR #8 base, pass an independent OLD gate,
and only then receive the preregistered PR #8 reset self-adjusting controller.
