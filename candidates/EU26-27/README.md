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
OLD 100-run raw replay: CI_RUNNING
HYBRID: BLOCKED_UNTIL_PASS_SOURCE_NATIVE_OLD
PR #19 numerical evidence used: false
```

## One OLD only

This candidate no longer maintains a second clean-room OLD implementation.
The only scientific OLD is the exact public author implementation:

```text
FurongYe/GSEMO
commit fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
message: submission preparation
```

The repository is fetched at that exact SHA in CI. Its critical algorithm
blobs are checked before and after build. Because the frozen upstream tree has
no root license, its source bytes are not copied into this repository as
project-owned code; the pinned checkout is the original code used by the OLD
experiment.

The paper-era GSEMO tree contains absolute developer symlinks to
`/home/jacob/code/IOHexperimenter/include/` and `external/`. CI reconstructs
those dependency paths from the frozen paper-era dependency candidate
`FurongYe/IOHexperimenter@d35fffe510b958aa2658c0b39ed7dd2d84c5553b`
without changing `src/gsemo.hpp`, `src/main.cpp` or `src/problems.cpp`.

## Frozen source-native command

The author's `src/main.cpp` defines

```text
./gsemo problem_id dimension algorithm lambda p adapt_metric budget runs
```

and seeds the global IOHexperimenter RNG once with `10` before the complete run
batch. The OLD command is therefore fixed as

```text
./gsemo 1 100 TwoRate 10 1 1 100000 100
```

which means:

- OneMinMax, `n=100`;
- TwoRate self-adaptation;
- `lambda=10`;
- initial `p=1/n`;
- hypervolume adaptation metric;
- budget `100000` FE per run;
- 100 sequential runs from the author's single `seed(10)` RNG stream.

The generated experiment prefix is `TwoRateL10P1HV`, matching the authenticated
Zenodo member `csv/om/TwoRateL10P1HVOneMaxD100.csv`.

## OLD pass rule

`PASS_SOURCE_NATIVE_OLD` requires all of:

1. exact upstream commit and critical blob hashes;
2. successful build of unchanged author algorithm source;
3. exactly 100 complete source-native runs;
4. exact 101×100 first-hit matrix equality with the Zenodo raw artifact;
5. exact 100-run endpoint-vector equality;
6. the Zenodo raw mean agrees with the published rounded mean `61618 FE`;
7. evidence JSON and SVG figures are bound by SHA-256.

The build is smoke-tested on Ubuntu, macOS and Windows. The historical OLD
batch itself is intentionally **not parallelized across workers** because the
author seeds one global RNG stream before the 100 runs; worker parallelization
would change the algorithm being reproduced.

## Professor boundary

CI success alone is not a scientific PASS. If the exact source-native replay
does not match Zenodo, the dependency revision or historical environment is
still unresolved and HYBRID remains prohibited. No tolerance may be widened
after observing the result.

If `PASS_SOURCE_NATIVE_OLD` is reached, the next stage is a separately frozen
HYBRID change to this one baseline, followed by equal-budget experiments,
graphs, load tests and a professor red-team review.
