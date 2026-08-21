# EU26-27 — source-native OLD for TwoRate GSEMO

Research tag: `RESEARCH_2`

## Current scientific status

```text
candidate identity: PASS
EU affiliation: PASS_LEIDEN_UNIVERSITY_NETHERLANDS
dimension: PASS_N_100
Zenodo raw data: PASS_AUTHENTICATED
author repository: PASS_FurongYe/GSEMO
paper-era author commit: PASS_fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
OLD implementation: SINGLE_SOURCE_NATIVE_AUTHOR_CODE
IOHexperimenter dependency: PINNED_OFFICIAL_v0.3.9_f223c682
publication anchor: CORRECTED_TABLE1_TWORATE_HV_61624
OLD 100-run raw replay: CI_RUNNING
HYBRID: BLOCKED_UNTIL_PASS_SOURCE_NATIVE_OLD
PR #19 numerical evidence used: false
```

## One OLD only

The only scientific OLD is the exact public author implementation:

```text
FurongYe/GSEMO
commit fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
2023-05-01, message: submission preparation
```

The repository is fetched at that exact SHA in CI. Critical algorithm blobs are
checked before and after build. Because the frozen upstream tree has no root
license, its source bytes are not copied into this repository as project-owned
source; the pinned checkout is the original code executed by OLD.

## Historical dependency resolution

The GSEMO tree contains absolute developer symlinks to a local
IOHexperimenter checkout but does not record its commit. The first candidate,
`FurongYe/IOHexperimenter@d35fffe...`, was rejected before any OLD outcome was
produced because it failed source compatibility: it no longer exposed the
`IntegerSingleObjective`/legacy `wrap_function` API required by GSEMO.

The replacement was selected from release chronology and API compatibility,
not numerical outcomes:

```text
IOHprofiler/IOHexperimenter
release: v0.3.9
commit: f223c682dff0749067d00b870f83ad754f7d96f5
release date: 2023-03-13
GSEMO commit date: 2023-05-01
```

`v0.3.9` is the latest public IOHexperimenter release before the frozen GSEMO
submission commit. CI reconstructs GSEMO's historical `include` and `external`
paths from that exact release without modifying `src/gsemo.hpp`, `src/main.cpp`
or `src/problems.cpp`.

## Frozen source-native command

The author's `src/main.cpp` defines

```text
./gsemo problem_id dimension algorithm lambda p adapt_metric budget runs
```

and seeds the global IOHexperimenter RNG once with `10` before the complete run
batch. The OLD command is fixed as

```text
./gsemo 1 100 TwoRate 10 1 1 100000 100
```

meaning OneMinMax `n=100`, TwoRate, `lambda=10`, initial `p=1/n`, hypervolume
adaptation, a 100000-FE budget and 100 sequential runs from the author's single
`seed(10)` RNG stream. The generated prefix `TwoRateL10P1HV` matches the
authenticated Zenodo member `csv/om/TwoRateL10P1HVOneMaxD100.csv`.

## Correct publication anchor

The paper's Table 1 reports, for the profile matching this OLD:

```text
OneMinMax / two-rate GSEMO / HV / lambda=10: 61 624 FE
```

The authenticated Zenodo raw endpoint mean is `61623.78 FE`, which rounds to
`61624 FE`.

A previous freeze incorrectly used `61618 FE`. That value belongs to **AGSEMO
in Table 2**, a different algorithm. The correction changes only the mislabeled
publication anchor. It does not change source code, data, seed, budget, command,
raw matrix, or the exact-replay pass criterion.

## OLD pass rule

`PASS_SOURCE_NATIVE_OLD` requires all of:

1. exact upstream commits and critical blob hashes;
2. successful build of unchanged author algorithm source;
3. exactly 100 complete source-native runs;
4. exact 101×100 first-hit matrix equality with Zenodo;
5. exact 100-run endpoint-vector equality;
6. Zenodo raw mean consistent with the matching paper Table 1 value `61624 FE`;
7. SHA-256-bound JSON, raw logger output and SVG evidence;
8. professor fail-closed review.

The build is smoke-tested on Ubuntu, macOS and Windows. The historical OLD
batch is intentionally not parallelized because splitting the author's single
global RNG stream across workers would change the experiment rather than
reproduce it.

## Recovery results already established

The recovery process is fail-closed and is not allowed to optimize numerical
agreement:

- nine distinct paper-era GSEMO source generations were checked; none exactly
  reproduced the Zenodo raw trajectory;
- a January-2023 compatible IOHexperimenter core state was checked and produced
  0/100 complete runs, ruling out that early dependency state;
- GCC9 and GCC10 both execute the final source but do not exactly reproduce the
  Zenodo matrix;
- the secondary, provenance-frozen GCC11–GCC13 matrix is the remaining compiler
  recovery check; exact raw equality is the only positive outcome.

## Professor boundary

CI execution success alone is not a scientific PASS. If exact source-native
replay does not match Zenodo after the justified recovery axes are exhausted,
the historical environment remains unresolved and HYBRID is prohibited. No
tolerance, seed, aggregation or subset may be changed after observing the
result.

If `PASS_SOURCE_NATIVE_OLD` is reached, Stage 2 may introduce the separately
preregistered HYBRID modification to this single baseline and then test
equal-budget quality, efficiency, load profiles, graphs and academic claim
boundaries.

If it is not reached, the thesis-ready result is a reproducibility limitation,
not a fabricated HYBRID performance claim: public source, public data and the
published profile can be authenticated, while the exact historical stochastic
trajectory cannot be reconstructed from the publicly preserved environment
information.
