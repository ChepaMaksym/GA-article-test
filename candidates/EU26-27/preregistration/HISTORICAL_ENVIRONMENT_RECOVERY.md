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
exact raw replay: NOT PASS
```

The source-native OLD is therefore still `NOT PASS`; HYBRID remains
`BLOCKED_NOT_AUTHORIZED`.

## Why compiler/runtime is a source-grounded variable

The frozen GSEMO source calls `std::binomial_distribution<>` directly using
the IOHexperimenter global `std::mt19937`. The public IOHexperimenter
`random.hpp` uses `std::uniform_int_distribution`, `std::uniform_real_distribution`
and the same global generator. Distribution-to-engine mapping is a standard-library
implementation detail that can vary across libstdc++ generations even when the
engine seed is identical.

The final GSEMO repository records its historical dependency path under
`/home/jacob/code/IOHexperimenter/`, and public IOHexperimenter history is
Jacob de Nobel's development tree. Therefore compiler/libstdc++ version is a
historically evidenced missing environment variable, not an algorithm parameter.

## Primary compiler probe (frozen before its outcomes)

The first compiler recovery was frozen as:

```text
GCC7
GCC8
GCC9
GCC10
```

Each environment used the unchanged GSEMO source, unchanged v0.3.9 dependency,
unchanged command, seed, budget, and exact Zenodo comparison. GCC7 and GCC8
proved build-incompatible; GCC9 and GCC10 executed but did not exactly replay
Zenodo. Those outcomes do not authorize any algorithm or threshold change.

## Secondary compiler provenance addendum — frozen before GCC11–13 outcomes

This addendum is **not** retroactively part of the primary preregistration.
It is a second, provenance-driven recovery stage frozen after the GCC7–10 stage
failed and before any GCC11–13 outcome is inspected.

Rationale independent of numerical outcomes:

1. the algorithm/data were developed and prepared for submission during 2023;
2. GCC11 (2021), GCC12 (2022) and GCC13 (2023) are therefore plausible Linux
   research-workstation libstdc++ generations for that period;
3. the frozen code uses standard-library random distributions whose realization
   is runtime/library-sensitive;
4. extending only forward to GCC13 closes the historically plausible GNU
   compiler window through the paper-era date without testing post-paper GCC14+.

The frozen secondary matrix is exactly:

```text
GCC9   # repeated control
GCC10  # repeated control
GCC11
GCC12
GCC13
```

The repeated GCC9/10 jobs are controls for workflow equivalence. No result may
be selected by closeness of aggregate mean. The only positive recovery outcome
is exact raw equality.

## Common requirements for every compiler job

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
10. publish SHA-256-bound JSON and raw IOH logger output;
11. record the exact compiler container digest.

A compiler image that cannot build is recorded as `BUILD_INCOMPATIBLE`, not
silently replaced.

## Dependency-recovery evidence boundary

A separate source-grounded dependency probe is allowed only because the GSEMO
repository contains absolute symlinks to an unpinned local IOHexperimenter
checkout. It must not alter GSEMO source or the numerical gate.

The compatible January-06 IOHexperimenter core state
`8d21f4f6b46844d037c6a8740db2a56a1c940e0f` was tested under GCC10 and gave
0/100 complete runs. This rules out that early core state as the historical
dependency. The public v0.3.9 state gives near-complete behavior but still not
exact raw replay. Intermediate dependency revisions may be investigated only
when selected from public provenance/code-change evidence, never by optimizing
agreement with Zenodo.

## Decision rule

```text
one or more historically justified environments gives:
    exact 101x100 first-hit matrix match
    exact 100-run endpoint-vector match
        -> HISTORICAL_ENVIRONMENT_MATCH
        -> freeze the matching source/dependency/compiler tuple
        -> rerun strict source-native OLD on a new immutable head

no historically justified environment matches
        -> FAIL_HISTORICAL_ENVIRONMENT_RECOVERY
        -> do not tune algorithm or thresholds
        -> OLD remains NOT PASS
        -> HYBRID remains BLOCKED_NOT_AUTHORIZED
```

If multiple environments match exactly, record all of them; use the lowest GCC
major only as a reproducible containerization target, not as a scientific
selection criterion.

An aggregate-only match is insufficient. The gate remains exact raw replay.

## Explicitly forbidden

- increasing the 100000 FE budget;
- dropping incomplete runs;
- changing seed 10 or splitting the 100-run global RNG stream;
- changing TwoRate 5/5 semantics, tie behavior, archive update, objectives or
  evaluation counting;
- selecting compiler/runtime merely because its mean is near the publication;
- changing the published tolerance after seeing outcomes;
- treating GCC11–13 as if they had been in the original GCC7–10 freeze;
- starting HYBRID before strict `PASS_SOURCE_NATIVE_OLD`.
