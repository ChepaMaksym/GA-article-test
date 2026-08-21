# Source Amendment 001 - IOHprofiler TwoRateEA evidence

Date: 2026-08-21
Research tag: `RESEARCH_2`

This amendment was committed while the frozen R1-R4 full recovery campaigns
were still running and before any R2-R4 numerical outcome was inspected. It
does not change the recovery matrix, seeds, endpoint or acceptance gates.

## Newly located upstream evidence

The public `IOHprofiler/IOHalgorithm` repository is an algorithm repository
from the same IOHprofiler ecosystem used by Furong Ye and Jacob de Nobel.
Its `master` branch currently resolves to commit
`bd2ec13068536ce49ee0864acb86d6f7272aca54`, authored by Furong Ye and merged
on 2023-09-04 with message `add lognormal GA`. The parent revision
`7944c068ca6a8db811cbda883c574562504f39b5` already contains the same
`include/ga/instance/twoRateEA.hpp` blob
`1f9392a2cd3613108ea35ec5233f99c13d078f4b`.

The source is a single-objective `TwoRateEA`, not the exact multi-objective
GSEMO implementation used for the paper. It therefore does **not** close the
mandatory author-implementation provenance gate by itself.

## Semantics supported by the upstream code

The retained `TwoRateEA` source implements:

```cpp
for (size_t i = 0; i < lambda; ++i) {
    if (i < floor(lambda / 2.0)) {
        // lower-rate offspring
    } else {
        // higher-rate offspring
    }

    if (f_x > best_f_x) {
        best_f_x = f_x;
        best_x_index = i;
    }
}
```

For `lambda=10`, this is a **5 lower / 5 higher** split under zero-based C++
indexing. The strict `>` comparison preserves the **first** maximal offspring
rather than drawing uniformly among ties.

This makes frozen recovery variant

```text
R2 = first tie + balanced 5/5 split
```

the variant most strongly supported by currently available implementation
provenance. R3/R4 remain in the matrix because the printed paper pseudocode is
one-based and literally uses `i < floor(lambda/2)`, while the prose says 50/50.
No variant is removed after launch.

## Important differences from the paper profile

The single-objective source also differs from the paper's multi-objective
algorithm, including:

- one fixed parent rather than uniform selection from a non-dominated archive;
- scalar objective fitness rather than `e(y)` based on a multi-objective metric;
- default `init_r=2.0` in this class;
- lower clamp `r>=2.0` in this class, whereas the paper states `[1/2,n/4]`;
- a different but algebraically related stochastic update implementation.

Therefore these differences must **not** be copied into the current recovery
without a separately frozen, source-justified amendment. The current R1-R4
campaign continues unchanged.

## Decision effect

This evidence strengthens the interpretation of R2 if R2 improves numerical
compatibility. It cannot by itself promote a diagnostic match to `PASS_OLD`.
The exact paper-generating multi-objective source revision remains required
under the original eligibility contract.
