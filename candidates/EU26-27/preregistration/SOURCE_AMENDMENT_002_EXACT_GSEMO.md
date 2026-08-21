# Source Amendment 002 - exact author GSEMO repository discovered

Date: 2026-08-21
Research tag: `RESEARCH_2`

This amendment is frozen before inspecting any completed R2-R4 recovery
outcome. It does not change the already launched 2x2 diagnostic matrix or its
acceptance bounds. Instead, it establishes a stronger primary recovery route:
source-native replay of the exact public author repository followed by an
independent clean-room implementation of the same source semantics.

## Exact author repository

Public repository:

```text
https://github.com/FurongYe/GSEMO
```

Frozen paper-era revision:

```text
commit: fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380
commit author: Furong Ye
commit date: 2023-05-01
commit message: submission preparation
```

This revision predates the 2023 conference publication and contains the
multi-objective GSEMO experiment implementation, plotting notebook and command
runner. The repository was created in January 2023 and the frozen revision is
its final public paper-era commit.

Critical tracked blobs at the frozen revision:

```text
src/gsemo.hpp   git blob 2693144bcfccff902343a02c6c8e48d7dd263257
src/main.cpp    git blob 22025e4680da85c98e3bb5ea30db8334ca25dff3
src/problems.cpp git blob cd9b520253e3b0b0390e35bf4fb86d4249c204de
figures.ipynb   git blob 13f3b1d13391da94e45a081127df1d5fe6a0d4af
```

The repository has no root license in the frozen tree. It is therefore used as
authenticated evidence and for source-native execution only; no upstream code
is copied into this project as project-owned source.

## Source resolves the main OLD ambiguities

The exact multi-objective source implements `adaptation::TwoRate` as follows.

### Offspring split

```cpp
if (i < lambda / 2)
    pm = r / 2 / n;
else
    pm = 2 * r / n;
```

With zero-based C++ indices and `lambda=10`, this is exactly five lower-rate
and five higher-rate offspring. Therefore the source-native interpretation is
`balanced 5/5`, not the naive one-based 4/6 reading of the printed pseudocode.

### Winner tie semantics

The source computes a metric for every offspring and then uses
`std::max_element`. C++ `max_element` returns the first maximal element.
Therefore source-native tie semantics are deterministic first maximum, not a
uniform random draw among tied maxima.

The source contains the comment:

```text
TODO: this is was not defined according to the paper, I changed it.
```

This explicitly confirms that implementation semantics resolve an ambiguity in
the printed description.

Consequently frozen diagnostic variant

```text
R2 = first tie + balanced 5/5 split
```

is the unique R1-R4 variant matching the exact public multi-objective author
source on these two factors. R1/R3/R4 remain in the already frozen sensitivity
matrix and are not removed after launch.

## Exact source execution semantics

The frozen `src/main.cpp` states the command schema:

```text
./main problem_id dimension algorithm lambda p adapt_metric budget runs
```

and performs:

```text
pm = p / dimension
random::seed(10)   # once before the complete run batch
```

For the selected profile the source-side configuration is therefore:

```text
problem: OneMinMax
n: 100
algorithm: TwoRate
lambda: 10
p: 1 -> pm0 = 1/100
adapt_metric: 1 -> HV
runs: 100
RNG stream: IOHexperimenter global RNG seeded once with 10
```

The generated experiment-name prefix is:

```text
TwoRateL10P1HV
```

which matches the retained Zenodo naming convention for the selected raw
profile.

Inside each generation the source:

1. samples each offspring parent uniformly from the pre-generation Pareto set;
2. obtains `pm` from the source TwoRate strategy;
3. samples a positive mutation strength through the IOHexperimenter RNG;
4. mutates and evaluates all offspring;
5. computes the selected adaptation metric for each `P union {offspring}`;
6. applies the TwoRate update before archive insertion;
7. inserts offspring sequentially through source dominance semantics;
8. stops after the complete known Pareto front has been found or the budget is
   exhausted.

## Historical dependency boundary

The GSEMO tree contains developer symlinks pointing to:

```text
/home/jacob/code/IOHexperimenter/include/
/home/jacob/code/IOHexperimenter/external/
```

The exact local dependency commit is not encoded in the GSEMO tree. A public
Furong Ye fork of IOHexperimenter exists at paper-development time; its current
paper-era candidate revision is:

```text
FurongYe/IOHexperimenter
d35fffe510b958aa2658c0b39ed7dd2d84c5553b
2022-11-16, author jacobdenobel, message: update submodules
```

This commit is a strong historical dependency candidate but is not yet asserted
as byte-identical to the developer's local checkout. Dependency identity is a
separate provenance gate to be audited by source compatibility and exact
source-native output reproduction.

## Revised primary OLD recovery tracks

### Track S - exact source-native replay

Authenticate the frozen author commit and source blobs, build it against an
authenticated paper-era IOHexperimenter dependency candidate without modifying
algorithm semantics, execute the selected 100-run command with the source RNG
seed 10, and compare generated endpoint rows with the retained Zenodo raw
profile.

Strongest possible result:

```text
PASS_SOURCE_NATIVE_RAW_REPLAY
```

requires exact or explicitly preregistered canonical raw-row equivalence, not
only a nearby aggregate mean.

### Track C - independent source-semantic clean-room OLD

After Track S defines the exact source transition and RNG/accounting semantics,
implement the same algorithm independently without copying upstream source.
Use a separately frozen independent seed/run protocol and compare its
distribution with the author raw rows.

Strongest possible result:

```text
PASS_INDEPENDENT_OLD_DISTRIBUTIONAL_ALIGNMENT
```

### Existing Track D - R1-R4 ambiguity diagnostics

The already launched PCG64DXSM R1-R4 matrix remains a diagnostic sensitivity
study. It may explain how much of the original two-fold discrepancy came from
tie/split semantics. It is no longer the primary route to `PASS_OLD` because a
paper-era author implementation has now been found.

## HYBRID gate remains unchanged

HYBRID remains prohibited until the project has defensible evidence for:

```text
source-native OLD replay
AND independent OLD validation
AND exact evaluation/accounting semantics
AND worker/machine reproducibility for the independent implementation
AND professor red-team acceptance
```

No numerical evidence from PR #19 is admissible in these decisions.
