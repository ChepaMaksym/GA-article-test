# EU26-27 historical-environment recovery freeze

Date: 2026-08-21
Research tag: `RESEARCH_2`

## Immutable state entering this recovery

The exact paper-era GSEMO source is fixed at:

```text
FurongYe/GSEMO
fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
2023-05-01, submission preparation
```

The source-native command remains exactly:

```text
./gsemo 1 100 TwoRate 10 1 1 100000 100
```

No GSEMO algorithm source, seed, budget, problem, lambda, mutation formula,
adaptation metric, run count, reference data, or PASS criterion may be changed
by this recovery.

The modern-run baseline with `IOHprofiler/IOHexperimenter@f223c682...`
(v0.3.9) established:

```text
exact author source builds: PASS
Ubuntu/macOS/Windows smoke: PASS
100 sequential source-native runs execute: PASS
Zenodo csv.zip authenticated: PASS
complete Pareto fronts by FE 100000: 96/100
incomplete runs: 46, 55, 68, 76
exact raw replay: NOT PASS
```

The source-native OLD is therefore still `NOT PASS`; HYBRID remains
`BLOCKED_NOT_AUTHORIZED`.

## Why compiler/runtime is a source-grounded variable

The frozen GSEMO source calls `std::binomial_distribution<>` directly using
the IOHexperimenter global `std::mt19937`. The public IOHexperimenter
`random.hpp` blob is identical between the latest public master immediately
before the first GSEMO repository commits in January 2023 and release v0.3.9,
so changing those two revisions does not change the mt19937 wrapper itself.

More importantly, the public `FurongYe/IOHexperimenter` history contains a
2022-09-28 commit named `gsemo`, authored by Jacob de Nobel, and its frozen
Ubuntu workflow explicitly tests C++ with:

```text
g++-7, g++-8, g++-9, g++-10
```

The final GSEMO repository also records its historical dependency path under
`/home/jacob/code/IOHexperimenter/`. Therefore GCC/libstdc++ version is a
historically evidenced missing environment variable, not an outcome-informed
algorithm parameter.

## Frozen compiler probe

Before viewing any compiler-probe outcome, run the unchanged GSEMO source with
the unchanged v0.3.9 headers/external dependencies under the official Docker
GCC major-version images in this fixed order:

```text
GCC7
GCC8
GCC9
GCC10
```

Each compiler job must:

1. fetch the exact GSEMO and IOHexperimenter SHAs;
2. verify the same critical GSEMO blob hashes and IOH version;
3. build without modifying algorithm source;
4. execute the same 100-run global-stream command;
5. authenticate the same Zenodo `csv.zip` and selected raw member;
6. retain incomplete runs rather than aborting diagnostics;
7. report exact 101x100 first-hit matrix equality;
8. report exact 100-run endpoint equality;
9. report source completeness, censored mean/median, and observed-cell mismatch;
10. publish SHA-256-bound JSON and raw IOH logger output.

A compiler image that cannot build is recorded as `BUILD_INCOMPATIBLE`, not
silently replaced.

## Decision rule

```text
exactly one GCC7..GCC10 environment gives:
    100/100 complete
    exact 101x100 first-hit matrix match
    exact 100-run endpoint-vector match
    Zenodo raw mean aligns with published 61618 FE
        -> HISTORICAL_ENVIRONMENT_MATCH
        -> freeze that compiler/runtime
        -> rerun strict source-native OLD on a new immutable head

zero environments match
        -> FAIL_HISTORICAL_COMPILER_RECOVERY
        -> do not tune algorithm or thresholds
        -> investigate only new independent provenance evidence

multiple environments match exactly
        -> choose the lowest GCC major in the preregistered order
           solely as a reproducible containerization target;
           record all exact matches
```

An aggregate-only match is insufficient. The gate remains exact raw replay.

## Explicitly forbidden

- increasing the 100000 FE budget;
- dropping incomplete runs;
- changing seed 10 or splitting the 100-run global RNG stream;
- changing TwoRate 5/5 semantics, tie behavior, archive update, objectives or
  evaluation counting;
- selecting compiler/runtime merely because its mean is near 61618;
- changing the published tolerance after seeing outcomes;
- starting HYBRID before strict `PASS_SOURCE_NATIVE_OLD`.
