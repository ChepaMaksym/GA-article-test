# EU26-01 archive and formula validation contract v1

Frozen: 2026-08-07, before opening or validating the archived outcome member
under this contract.

Status: **`ARCHIVE_AND_FORMULA_VALIDATION_ONLY`**

Eligibility status: **`conditional_noneligible`**

Source-native gate: **`BLOCKED_SOURCE_NATIVE_REPLAY`**

This contract authorizes an authenticated recalculation of one already
published CSV member, independent clean-room formula and transition tests,
and deterministic portability checks of those validation workloads. It does
not authorize a new stochastic outcome run, an equivalence claim for the
authors' executable, or a claim that the paper experiment was reproduced.

## Frozen paper cell and published targets

The single outcome-blind focus cell is:

| Field | Frozen value |
|---|---|
| DOI | `10.1145/3638529.3654073` |
| Algorithm | Paper Algorithm 2, two-rate GSEMO (`TwoRate`) |
| Indicator | hypervolume (`HV`) with reference point `(-1,-1)` |
| Problem | OneMinMax; the archive filename uses `OneMax` |
| Decision dimension | `n=100` bits |
| Offspring population | `lambda=10` |
| Initial mutation strength | `r_init=1` (`p_init=1/n`) |
| Runs | 100 |
| Endpoint | first function evaluation at which all 101 objective pairs `(k,100-k)`, `k=0..100`, have been found |
| Published mean FEs | `61 624` |
| Published variance | `3.271e+08` |

The targets are transcribed from Table 1 before validation. The paper states
that the table reports the mean and variance over 100 runs and identifies
TwoRate+HV as the best tested OneMinMax cell. No other problem, indicator,
algorithm or lambda may be substituted after outcomes are observed.

Mean comparison is the arithmetic mean rounded to the nearest integer, with
half values rounded away from zero. Variance is the population variance
(`ddof=0`), as specified by the pinned notebook's `np.var(runtime)`, rounded
to four significant decimal digits and rendered in scientific notation.
The exact integer sum, rational mean and rational population variance must
also remain in the report. A failed run cannot be silently dropped or
replaced by the notebook's `1,000,000` penalty; this focus cell requires
100/100 complete runs.

## Frozen archive object

- Zenodo record: `https://zenodo.org/records/7880836`.
- Record DOI: `10.5281/zenodo.7880836`; concept DOI:
  `10.5281/zenodo.7880834`.
- Record license: CC BY 4.0.
- File: `csv.zip`, exactly 173,556,521 bytes.
- File MD5 from the Zenodo record:
  `a9970c46812e4cc986595704877bf160`.
- File SHA-256:
  `2d5d3491c23e68bdd6d3c9c9dedfae67c805fa0588a3d443912c0b12c348fe4a`.
- Exact ZIP member: `csv/om/TwoRateL10P1HVOneMaxD100.csv`.
- Member metadata: 102,227 uncompressed bytes, 25,033 compressed bytes,
  CRC32 `6ca56598`.
- Member SHA-256:
  `75a7788105ac9b73f6f4a1baa2a84d5ffb0d13e736da70115319e9eb62eda154`.

The validator must retain one descriptor for the supplied ZIP, copy bytes
from that descriptor into a private authenticated snapshot, and parse only
that snapshot. It must verify size, MD5 and SHA-256 before parsing, reject
duplicate member names, encrypted members, non-regular paths, unsupported
compression, inconsistent ZIP metadata and any exact-member mismatch, and
reauthenticate the retained objects after use. The member is read in memory;
it is never extracted to a filesystem path.

The member contract requires UTF-8 CSV with one header and exactly 101 data
rows. It requires the four metadata columns `pareto`, `algorithm`, `func`,
`dimension`, followed by exactly the 100 pairs `found0`, `First_hit0`, ...,
`found99`, `First_hit99`. The 101 OneMinMax objective pairs must be unique and
exactly `(k,100-k)` for `k=0..100`; metadata must identify the frozen cell.
For each run, every `foundN` must be true and the completion FE is the maximum
of its 101 non-negative integral `First_hitN` values. Missing, duplicate,
non-integral, non-finite or negative fields fail closed.

## Frozen clean-room Algorithm 2 semantics

The independent kernels operate on objective pairs and an explicit random
tape; they do not reproduce the authors' RNG.

1. OneMinMax maps a bit vector `x` to `(sum(x), n-sum(x))` and maximizes both
   coordinates.
2. The current Pareto population contains unique objective pairs. For this
   problem all distinct pairs are mutually non-dominating; an equal pair is
   a duplicate and does not enlarge the population.
3. At each generation, offspring indices `0..4` use
   `Bin>0(n,r/(2n))`; indices `5..9` use
   `Bin>0(n,2r/n)`. A zero-truncated binomial redraws until at least one bit
   is selected. Each child selects a parent uniformly from the pre-generation
   population and flips the selected distinct bit indices.
4. For each child, its score is the exact two-dimensional hypervolume of
   `P union {child}` relative to `(-1,-1)`. The population is sorted by its
   first objective before summing rectangles.
5. The source-faithful tie policy selects the first maximum score. If that
   child's zero-based index is `<5`, set `s=3/4`; otherwise set `s=1/4`.
6. Consume explicit tape value `q` in `[0,1]`. If `q<=s`, update
   `r=max(r/2,1/2)`; otherwise update `r=min(2r,n/4)`.
7. Insert children sequentially in indices `0..9`, rejecting a child if an
   existing point weakly dominates it and otherwise deleting points it
   strictly dominates. Completion is checked after the generation.

The fixed-tape fixture must cover low- and high-group winners, an exact score
tie, `q=s`, both `r` clamps, a duplicate objective, shuffled population input,
sequential insertion and invalid tape values. Python and MATLAB/Octave must
match the fixture exactly without a floating tolerance for all integral or
rational fields.

## Paper/source conflicts frozen before outcomes

- Algorithm 2 numbers offspring from 1 and uses `i < floor(lambda/2)`, which
  is not a 50/50 split for `lambda=10`; the prose says 50/50 and the source
  uses zero-based `i < lambda/2`. The contract freezes the source/prose 5/5
  split and reports the pseudocode ambiguity.
- The paper does not define tie-breaking for `arg max`. The frozen source uses
  `std::max_element`, hence first maximum. This is source-faithful rather than
  uniquely paper-faithful.
- The source's TwoRate adaptation carries the comment that it was changed
  because it was not defined according to the paper. The pinned source
  revision is therefore not treated as proof of the paper's generating
  executable.
- The paper states 100 independent runs. `src/main.cpp` seeds the IOH RNG once
  with `10`, then resets the problem between 100 sequential runs. No 100-seed
  ledger or RNG-state ledger is published.
- A clean checkout has absolute `include` and `external` symlinks into a
  developer IOHexperimenter tree. The dependency revision and build lock are
  absent, `/usr/local/include` is searched, and the repository has no license.
- The historical committed ELF predates later bug fixes and cannot be bound to
  Table 1. It is diagnostic only and cannot close the source-native gate.

The AGSEMO Algorithm 5 target is explicitly outside this contract. Its paper
and source adaptive-state semantics conflict and it cannot be used as a
fallback target.

## Validation gates and permitted labels

| Gate | PASS rule |
|---|---|
| A1 custody | Snapshot and post-use authentication bind the exact ZIP bytes consumed by the parser. |
| A2 member identity | Exact path, size, compressed size, CRC32 and member SHA-256 match. |
| A3 schema | Exact 101-row/204-column schema, metadata and complete OneMinMax front match. |
| A4 completion | Exactly 100 complete runs yield one integral completion FE each. |
| A5 Table 1 | Frozen rounding rules reproduce both published values; exact statistics remain reported. |
| F1 objectives | OneMinMax mapping, dominance and duplicate handling pass unit/property tests. |
| F2 hypervolume | Independent HV matches hand-computed, permutation and adversarial cases. |
| F3 transition | Low/high decisions, first-max ties, `q=s` and both clamps match the fixture. |
| F4 protocol | 5/5 rate assignment, pre-generation parents and sequential insertion match the fixture. |
| F5 cross-language | Python and MATLAB/Octave independently match the same frozen fixture and invalid-input expectations. |
| F6 fail closed | Malformed dimensions, probabilities, fronts, tapes, CSVs and ZIPs are rejected. |
| H0-H5 portability | The separately frozen portability contract passes for archive/formula workloads only. |

Permitted positive labels are `PASS_ARCHIVE_EXACT`, `PASS_FORMULA` and
`PASS_REQUIRED_LOCAL_PAIR`, each limited to its named gate. The offline
comparator cannot authorize H5 portability. The mandatory overall
paper-level label remains `BLOCKED_SOURCE_NATIVE_REPLAY`, and registry
eligibility remains `conditional_noneligible`.

**`PASS_FULL` is forbidden under this contract.**
