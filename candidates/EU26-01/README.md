# EU26-01 — TwoRate+HV archive and formula verification

Paper: *What Performance Indicators to Use for Self-Adaptation in
Multi-Objective Evolutionary Algorithms*, DOI
[`10.1145/3638529.3654073`](https://doi.org/10.1145/3638529.3654073).

Scope: **`ARCHIVE_AND_FORMULA_VALIDATION_ONLY`**

Paper-level status: **`BLOCKED_SOURCE_NATIVE_REPLAY`**

Registry status: **`conditional_noneligible`**

`PASS_FULL` is forbidden.

Research selection milestone, comparison of PR #2-#6, and the reusable
Protocol v2:
[`RESEARCH_MILESTONE_2026-08-07_UA.md`](../../registry/cohort_2026_12/RESEARCH_MILESTONE_2026-08-07_UA.md).

## What is frozen

The only admitted paper cell is Algorithm 2 TwoRate using hypervolume on
OneMinMax, `n=100`, `lambda=10`, `r_init=1`, 100 runs. Table 1 prints mean
completion FEs `61624` and population variance `3.271e+08`.

The exact Zenodo `csv.zip` is pinned at 173,556,521 bytes, MD5
`a9970c46812e4cc986595704877bf160`, SHA-256
`2d5d3491c23e68bdd6d3c9c9dedfae67c805fa0588a3d443912c0b12c348fe4a`.
The parser reads only
`csv/om/TwoRateL10P1HVOneMaxD100.csv`, SHA-256
`75a7788105ac9b73f6f4a1baa2a84d5ffb0d13e736da70115319e9eb62eda154`.
The large archive is never vendored.

Authenticated recalculation gives 100/100 complete runs, minimum `30344`,
maximum `131875`, sum `6162378`, exact mean `61623.78`, and exact population
variance (`ddof=0`) `327085104.6716`. These round to the two printed targets.

## Claim limit that must travel with every result

Literal one-based Algorithm 2 uses `i < floor(lambda/2)`, which gives **4 low
and 6 high** offspring at `lambda=10`. Paper prose says half/half and source
uses zero-based **5 low and 5 high**. The clean-room transition freezes the
source/prose 5/5 interpretation. Paper `arg max` ties are unspecified; frozen
source selects the first maximum.

The source seeds the IOHexperimenter RNG once with `10` and then resets the
problem over 100 sequential runs. There is no per-run seed or RNG-state
ledger. Paper `flip_l` flips `l` distinct bits, but source calls an unpinned
IOHexperimenter integer-vector API that may sample positions with replacement
and cancel repeated flips. Clean checkout also has absolute developer
symlinks, no IOHexperimenter revision/build lock, and no code license. A
historical ELF predates fixes and cannot be bound to the table. Consequently,
archive and formula success do not establish author-executable identity or
stochastic trajectory replay.

The exact machine-readable conflict marker is:

`literal_one_based_pseudocode_4_low_6_high_vs_prose_and_source_5_low_5_high`

## Independent implementations

- `environments/python/tworateverify/` is a standard-library Python
  implementation of OneMinMax, exact 2-D HV, source/prose TwoRate transition,
  strict CSV aggregation and descriptor/snapshot ZIP authentication.
- `environments/matlab/` independently implements OneMinMax, HV, Pareto
  insertion and explicit-tape transition without calling Python.
- `fixtures/tworate_fixed_tape.json` covers low/high winners, first-max ties,
  `q=s`, both strength clamps, zero-truncation, duplicate insertion, the exact
  5/5 rate schedule, pre-generation parents, and the discriminating rejection
  of repeated flip indices that an iid-with-replacement dependency can emit.
- `tests/hardware/` runs deterministic Work4, Work8 and GitHub4 H0-H5
  portability gates. Timing is descriptive only.

## Local checks

```bash
PYTHONDONTWRITEBYTECODE=1 \
  python candidates/EU26-01/tests/run_python_tests.py
python registry/cohort_2026_12/validate_registry.py
python registry/cohort_2026_12/tests/run_registry_tests.py
octave --quiet --eval \
  "addpath('candidates/EU26-01/tests/matlab'); run_matlab_tests"
```

The Python environment has no third-party dependency. If MATLAB/Octave is not
installed locally, that gate is `NOT_RUN`, never inferred from Python; the
candidate workflow installs GNU Octave and executes it independently.

## Exact archive report

Formal outputs must be new paths outside the repository:

```bash
python candidates/EU26-01/environments/python/run_archive_validation.py \
  --archive /tmp/eu26-01-csv.zip \
  --output /tmp/eu26-01-archive-report.json
```

A valid report may say `PASS_ARCHIVE_EXACT`, but its paper-level status remains
`BLOCKED_SOURCE_NATIVE_REPLAY`.

## Work4 and Work8 profiles

Run only from a committed clean HEAD. Each command performs one warm-up and
five retained batches and authenticates the archive before and after them:

```bash
python candidates/EU26-01/tests/hardware/run_portability_suite.py \
  --profile-role work4 --label work-vm-4 \
  --workers 4 --logical-cpus 4 --timing-repeats 5 \
  --archive /tmp/eu26-01-csv.zip \
  --output /tmp/eu26-01-work4.json \
  --hashes /tmp/eu26-01-work4-hashes.tsv

python candidates/EU26-01/tests/hardware/run_portability_suite.py \
  --profile-role work8 --label work-vm-8 \
  --workers 8 --logical-cpus 8 --timing-repeats 5 \
  --archive /tmp/eu26-01-csv.zip \
  --output /tmp/eu26-01-work8.json \
  --hashes /tmp/eu26-01-work8-hashes.tsv

python candidates/EU26-01/tests/hardware/compare_portability_reports.py \
  /tmp/eu26-01-work4.json /tmp/eu26-01-work8.json \
  --output /tmp/eu26-01-work-pair.json
```

The local pair can report `PASS_REQUIRED_LOCAL_PAIR`; H5 remains
`NOT_EVALUATED_MISSING_GITHUB4`. A third, matching `github4.json` is still only
self-asserted context. It can establish a pairwise content match, but yields
`CONTENT_MATCH_EXTERNAL_AUTH_REQUIRED` with H5
`NOT_EVALUATED_EXTERNAL_GITHUB_AUTH_REQUIRED`:

```bash
python candidates/EU26-01/tests/hardware/compare_portability_reports.py \
  /tmp/eu26-01-work4.json /tmp/eu26-01-work8.json /tmp/github4.json \
  --output /tmp/eu26-01-all-profiles.json
```

No caller-supplied JSON, digest or in-workflow environment field can authorize
H5. A trusted reviewer must fetch the completed run and artifact through an
authenticated GitHub API client, authenticate the downloaded artifact bytes,
and bind the exact `github4.json` member. That external adjudication is not
implemented by this offline comparator. Duplicate JSON keys, explicit
non-finite constants and overflow such as `1e9999` fail closed.

No formal result or timing report is committed by these commands. Evidence
must be reviewed separately before any later evidence commit.
