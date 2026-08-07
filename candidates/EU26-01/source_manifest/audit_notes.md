# EU26-01 source audit

Audit frozen: 2026-08-07. The focus policy and published targets were selected
before validating the archived outcome member under the preregistered
contract.

## Admission decision

EU26-01 is admitted only for a narrow archive-and-formula validation. It
remains `conditional_noneligible`: the paper has unusually strong raw-data
availability, but the paper experiment cannot be replayed from an identified,
licensed and dependency-complete source environment.

The frozen target is Table 1 TwoRate+HV on 100-bit OneMinMax with `lambda=10`,
`r_init=1` and 100 runs. The published mean is `61 624` function evaluations
and the published population variance is `3.271e+08`. The AGSEMO Table 2 row
previously highlighted by the registry is not used.

## Paper Algorithm 2 versus frozen source

The independent implementation follows the source where the paper is
ambiguous, while retaining an explicit claim limit:

- paper one-based `i < floor(lambda/2)` conflicts with its own 50/50 prose;
  source zero-based `i < lambda/2` gives five low-rate and five high-rate
  children for `lambda=10`;
- paper `arg max` does not define ties; source `std::max_element` selects the
  first maximum;
- both use zero-truncated binomial mutation, `q<=s`, low/high probabilities
  `s=3/4` and `s=1/4`, and the mutation-strength clamps `[1/2,n/4]`;
- source computes each indicator on the pre-generation Pareto population plus
  one child, adapts once, and only then inserts all children sequentially;
- source itself marks the TwoRate adaptation with a comment saying it was
  changed because it was not defined according to the paper.

For OneMinMax, the source maps a bit string to `(ones,zeros)`. Every distinct
objective pair is non-dominated. Its two-dimensional hypervolume sorts by the
first objective and sums rectangles relative to `(-1,-1)`; duplicates
contribute zero width. The clean-room kernels encode these mathematical facts,
not copied upstream code.

## RNG and run-protocol limitation

The paper calls the 100 observations independent. At the frozen source head,
`src/main.cpp` calls `ioh::common::random::seed(10)` once before a loop of 100
runs and calls `problem->reset()` between runs. The resulting continuous RNG
stream may produce separate trajectories, but there is no published 100-seed
or RNG-state ledger. The archive contains first-hit traces, not the random
choices needed to reproduce those trajectories.

The formal workload therefore recalculates the stored Table 1 statistic and
checks transition formulas on explicit fixed tapes. It does not launch a new
outcome run or claim distributional reproduction.

## Source-native replay blocker

At commit `fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380`, `include` and
`external` are absolute symlinks to paths under
`/home/jacob/code/IOHexperimenter`. No IOHexperimenter revision, dependency
lock, build image or repository license is provided, and CMake also searches
`/usr/local/include`. `run.py` contains developer-specific paths and is not a
portable run ledger.

A 21,850,120-byte x86-64 debug ELF was committed briefly at
`2d1fdfe59d20da71e26beee0d03e4d8d464bfbea` and removed in the next commit.
It predates later fixes and the submission head. Its Git blob is
`9fee9992434522ce6fec64edf27e7253062a570b`; SHA-256 is
`e9bf0e6d91209e645ad568c11d830134d0e77fb6183a37c083fb2f00ae4c777d`.
No evidence binds it to the Zenodo CSV, so executing it would be diagnostic
only and cannot clear `BLOCKED_SOURCE_NATIVE_REPLAY`.

## Archive custody and license

Zenodo record 7880836 describes the authors' dataset and licenses it CC BY
4.0. The exact `csv.zip` and exact focus member are pinned by multiple
digests in `sources.csv` and `config/frozen_protocol.json`. Validation must
authenticate the bytes actually parsed and must not trust a filename, a
freshly reopened path, the member CRC alone, or a recompressed derivative.

The upstream code repository has no license. No upstream implementation is
vendored or copied. All executable validation code in this candidate is an
independent standard-library implementation of paper/source formula facts.

## Claim boundary

Success can establish only that:

1. the exact pinned Zenodo member contains 100 complete first-hit traces whose
   frozen aggregation reproduces the two printed Table 1 values;
2. independent Python and MATLAB/Octave kernels agree on frozen OneMinMax,
   hypervolume and TwoRate transition cases; and
3. these deterministic validation outputs are portable across the declared
   profiles.

It cannot establish native trajectory replay, author-executable identity,
the paper's unspecified tie behavior, 100-seed independence, or correctness
of other Table 1/2 cells. `PASS_FULL` is forbidden.
