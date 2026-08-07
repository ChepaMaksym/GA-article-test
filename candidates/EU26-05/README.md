# EU26-05 — adaptive crossover formula validation

Paper: José Ferreira, Mauro Castelli, Luca Manzoni and Gloria Pietropolli,
*A Self-Adaptive Approach to Exploit Topological Properties of Different GAs'
Crossover Operators*, EuroGP 2023, DOI
[`10.1007/978-3-031-29573-7_1`](https://doi.org/10.1007/978-3-031-29573-7_1).

Scope: **`FORMULA_AND_TRANSITION_VALIDATION_ONLY`**

H0: **`PASS_METADATA_ONLY / BLOCKED_SOURCE_BYTE_FREEZE`**

Paper result:
**`BLOCKED_MISSING_AUTHOR_CODE_RAW_SEEDS_AND_COMPLETE_SEMANTICS`**

The University of Trieste ArTS record identifies the lawful exact-title
2,921,299-byte author postprint, but both official bitstream routes returned a
Cloudflare challenge on the freeze host and ArTS OAI exposes no checksum. The
postprint is therefore pinned by handle/component/length with
`SHA256_UNRESOLVED`; no report in this directory may claim byte-level H0.

## What is validated

- the four-type contribution update with 10% floors, 60% competitive mass and
  equal all-zero reset, only when all four crossover denominators are positive;
- explicit-convention binary decode anchors for the published 30-by-20-bit
  representation;
- one-point crossover at explicit frozen interior cuts;
- the thesis maximum-binary extension-ray profile in both directions, whose
  stated construction algebraically produces the complement of each ray
  origin;
- a 600-bit, 30-coordinate injected toy-objective interface that rejects an
  authenticated-CEC claim; and
- exact fixed-tape and property payloads across Work4, Work8 and GitHub4.

The extension oracle is a **thesis-profile** micro-oracle. It is not a claim
about missing paper-author code. A zero crossover denominator always rejects;
it is never silently imputed.

## What is not validated

There is no CEC-2017 implementation or full GA runner here. P/P' mate
selection, minimization sign, ties, replacement, success classification,
decode conventions, RNG mapping and the full stochastic pipeline are not
invented. The published `27/30` sentence is frozen as descriptive metadata and
is never executed. `PASS_FULL`, `CEC2017_REPRODUCED`,
`PUBLISHED_27_OF_30_REPRODUCED` and `AUTHOR_CODE_REPLAYED` are forbidden.

## Local gates

```bash
python registry/cohort_2026_12/validate_registry.py
python registry/cohort_2026_12/tests/run_registry_tests.py
python candidates/EU26-05/tests/run_python_tests.py
octave --quiet --eval \
  "addpath('candidates/EU26-05/tests/matlab'); run_matlab_tests"
```

The shared Python and MATLAB/Octave-shaped reports are compared as parsed
objects and by their frozen semantic digest. The offline result is only
`PASS_H3_PAYLOAD_FORMULA_EQUIVALENCE_ONLY`; runtime execution remains
`NOT_EVALUATED_EXTERNAL_EXECUTION_AUTH_REQUIRED`. A runtime string and source
hashes do not authenticate which executable emitted an envelope.

```bash
python candidates/EU26-05/environments/python/run_formula_report.py \
  --output /tmp/eu26-05-python.json
octave --quiet --eval \
  "addpath('candidates/EU26-05/environments/matlab'); \
   run_shared_fixture_report('/tmp/eu26-05-octave.json')"
python candidates/EU26-05/tests/compare_fixture_reports.py \
  /tmp/eu26-05-python.json /tmp/eu26-05-octave.json
```

Formal Work reports must start from the same clean commit and write evidence
to new, distinct paths outside the repository. Each profile requires five
repeats, an exact affinity mask and barrier-confirmed distinct worker PIDs with
deterministic case shards. The strict comparator returns
`NOT_RUN_MISSING_PROFILES` until all three real profiles exist; a GitHub report
cannot be relabelled from a Work run.

Even three equal profile JSON files cannot authorize H5 offline. The optional
`build_github_content_match.py` helper checks only coherence among
caller-supplied GitHub-shaped metadata and a local report. It explicitly does
not authenticate API acquisition or artifact membership. After that check the
offline status remains `NOT_EVALUATED_EXTERNAL_GITHUB_AUTH_REQUIRED`, with
`offline_authorizes_h5=false`. A reviewer must separately verify the real API
objects, jobs, downloaded artifact and member bytes.

```bash
taskset -c 0-3 python candidates/EU26-05/tests/hardware/run_portability_suite.py \
  --label work-4 --workers 4 --logical-cpus 4 --timing-repeats 5 \
  --require-clean --require-exact-visible-cpus \
  --output /tmp/eu26-05-work-4.json --hashes /tmp/eu26-05-work-4-hashes.tsv
taskset -c 0-7 python candidates/EU26-05/tests/hardware/run_portability_suite.py \
  --label work-8 --workers 8 --logical-cpus 8 --timing-repeats 5 \
  --require-clean --require-exact-visible-cpus \
  --output /tmp/eu26-05-work-8.json --hashes /tmp/eu26-05-work-8-hashes.tsv
python candidates/EU26-05/tests/hardware/compare_portability_reports.py \
  /tmp/eu26-05-work-4.json /tmp/eu26-05-work-8.json \
  --allow-incomplete --output /tmp/eu26-05-work-partial.json
```

An optional non-authorizing offline content check is:

```bash
python candidates/EU26-05/tests/hardware/build_github_content_match.py \
  --workflow-run-json /tmp/workflow-run.json \
  --artifact-json /tmp/artifact.json --report /tmp/github-4.json \
  --output /tmp/github-content-match.json
python candidates/EU26-05/tests/hardware/compare_portability_reports.py \
  /tmp/eu26-05-work-4.json /tmp/eu26-05-work-8.json /tmp/github-4.json \
  --github-content-match /tmp/github-content-match.json \
  --allow-incomplete --output /tmp/eu26-05-offline-comparison.json
```

This command cannot emit `PASS_H5_PORTABILITY`.

The H0-H5 contract and every unresolved semantic boundary are frozen in
[`preregistration/formula_transition_contract.md`](preregistration/formula_transition_contract.md).
The post-freeze authentication correction is recorded in
[`preregistration/amendment-001-offline-evidence-boundary.md`](preregistration/amendment-001-offline-evidence-boundary.md).
