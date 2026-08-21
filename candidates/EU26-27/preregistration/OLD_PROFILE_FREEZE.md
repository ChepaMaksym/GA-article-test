# EU26-27 OLD profile freeze — single source-native author baseline

Date revised: 2026-08-21
Research tag: `RESEARCH_2`

This freeze supersedes the earlier independent-reimplementation profile after
the exact public author repository was discovered. There is now **one OLD
implementation only**: the unchanged paper-era author code.

## Frozen source

```text
repository: FurongYe/GSEMO
commit: fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
message: submission preparation
```

Critical source blobs:

```text
CMakeLists.txt     1e2cb211fc0cc36f9837232b0dee69aa5c1dab9c
src/gsemo.hpp      2693144bcfccff902343a02c6c8e48d7dd263257
src/main.cpp       22025e4680da85c98e3bb5ea30db8334ca25dff3
src/problems.cpp   cd9b520253e3b0b0390e35bf4fb86d4249c204de
```

The upstream repository has no root license in the frozen tree, so its source
is fetched at the exact SHA in CI rather than copied into this project as
project-owned code.

## Historical dependency candidate

The author tree contains absolute symlinks to a local IOHexperimenter checkout.
CI reconstructs these paths from

```text
FurongYe/IOHexperimenter
d35fffe510b958aa2658c0b39ed7dd2d84c5553b
```

without modifying the GSEMO algorithm source. This dependency identity is
accepted only if the resulting source-native batch exactly reproduces Zenodo;
a build alone is insufficient.

## Frozen experiment command

From the author's `src/main.cpp`:

```text
./gsemo problem_id dimension algorithm lambda p adapt_metric budget runs
random::seed(10)  # once before all runs
```

The selected OLD is exactly

```text
./gsemo 1 100 TwoRate 10 1 1 100000 100
```

Configuration:

```text
problem: OneMinMax
n: 100
algorithm: TwoRate
lambda: 10
initial mutation probability: 1/100
adaptation metric: hypervolume contribution
budget: 100000 FE per run
runs: 100 sequential runs
RNG: author's IOHexperimenter global stream seeded once with 10
```

No run is split across workers. Parallelizing the batch would alter the frozen
source semantics and is therefore forbidden in OLD.

## Reference artifact

```text
Zenodo record: 7880836
archive: csv.zip
member: csv/om/TwoRateL10P1HVOneMaxD100.csv
front rows: 101
runs: 100
published rounded mean endpoint: 61618 FE
```

For each run, the endpoint is the maximum `First_hit_j` across all 101 Pareto
front rows. The comparison also retains the complete 101×100 first-hit matrix.

## PASS gate

`PASS_SOURCE_NATIVE_OLD` requires:

1. exact GSEMO commit and critical source blob hashes before and after build;
2. successful source build with the frozen dependency candidate;
3. 100/100 complete source-native runs;
4. exact equality of the generated 101×100 first-hit matrix with Zenodo;
5. exact equality of all 100 run endpoints with Zenodo;
6. raw Zenodo mean within ±1 FE of the published rounded value 61618;
7. generated report and SVG evidence bound by SHA-256;
8. professor fail-closed review passes.

There is no adjustable statistical tolerance for the source-native raw replay.
A mismatch of even one first-hit cell means `FAIL_SOURCE_NATIVE_OLD` and the
dependency/environment remains unresolved.

## Portability CI

Ubuntu, macOS and Windows jobs compile the same frozen author source and perform
a one-run smoke. These jobs test build portability only. Exact raw equality is
judged on the canonical Ubuntu source-native 100-run batch because the
historical experiment is a single sequential RNG stream.

## HYBRID prohibition

HYBRID remains `BLOCKED_NOT_AUTHORIZED` until the current commit reaches
`PASS_SOURCE_NATIVE_OLD`. No HYBRID code, improvement percentage or positive
novelty claim may use the rejected independent reconstruction from PR #22/early
PR #23.
