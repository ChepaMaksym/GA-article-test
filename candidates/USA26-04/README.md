# USA26-04 — bandit mutation-rate formula and ambiguity validation

This candidate is deliberately limited to
**`FORMULA_AND_AMBIGUITY_VALIDATION_ONLY`**. It independently ports the six
Appendix A objectives and the article's local reward/tile/Nesterov equations,
then demonstrates the source conflicts with deterministic witnesses. It does
not contain a genetic algorithm, continuous mutation reconstruction, Table 1
replay, or published-result acceptance test.

The scientific status is immutable within this protocol:

- paper level: `BLOCKED_G5_G9`;
- published result: `INCONCLUSIVE_PUBLISHED_RESULT`;
- cohort: `conditional_noneligible`;
- `PASS_FULL`: forbidden.

All Table 1 numbers are descriptive metadata. The primary descriptive cell is
Rastrigin/Bandit, d=100, initialization SD 10, population `100 + 1 elite`,
truncation size 10, 1000 generations, 50 reported runs, printed mean `3686`.
It is never passed to an experiment runner.

## What is validated

- independent Python and MATLAB/GNU Octave objective formulas;
- three separately named reward meanings: P1 direct function-minimization
  improvement, P2 Eq. (2) sign, and P3 Algorithm 2's opposite sign;
- the printed Nesterov value/momentum update;
- the `[99.98,100]` upper-boundary gap/overshoot conflict;
- equal-weight `argmax` tie ambiguity and the inconsistent SD derivation;
- an interior fixed-tape controller transition whose complete initial state is
  synthetic and always labeled `synthetic_fixture_not_article_state`;
- H0-H4 source/formula/batch checks on Work-4, Work-8, and GitHub-4, followed
  by a strict H5 formula-digest comparison.

Passing these checks means only that the clean-room formula ports agree on the
tested fixtures. It cannot establish the missing mutation transition,
controller initial state, tie/boundary behavior, RNG/seed protocol, raw runs,
or paper endpoint.

## Layout

- `preregistration/`: outcome-blind scientific and hardware contracts;
- `source_manifest/`: official source identities, licenses, and absence audit;
- `fixtures/`: formula oracles, descriptive Table 1 metadata, and synthetic
  fixed tape;
- `environments/python/banditverify/`: standard-library clean-room formulas;
- `environments/matlab/`: toolbox-free MATLAB/Octave formulas;
- `tests/python/` and `tests/matlab/`: unit, property, and adversarial checks;
- `tests/hardware/`: H0-H5 profile runner and strict comparator.

## Local formula checks

```bash
python candidates/USA26-04/tests/run_python_tests.py
octave --quiet --eval \
  "addpath('candidates/USA26-04/tests/matlab'); run_matlab_tests"
python registry/cohort_2026_12/validate_registry.py
python registry/cohort_2026_12/tests/run_registry_tests.py
```

## Frozen Work profiles

Write all generated artifacts outside the repository. First produce the
independent MATLAB/Octave fixed-tape report:

```bash
octave --quiet --eval \
  "addpath('candidates/USA26-04/environments/matlab'); \
   write_fixed_tape_report('/tmp/usa26-04-matlab-fixed-tape.json')"
```

Then run exactly five retained timing repeats per profile:

```bash
python candidates/USA26-04/tests/hardware/run_portability_suite.py \
  --label work-4core --workers 4 --logical-cpus 4 --timing-repeats 5 \
  --matlab-report /tmp/usa26-04-matlab-fixed-tape.json \
  --require-matlab-report \
  --output /tmp/usa26-04-work4.json \
  --hashes /tmp/usa26-04-work4-hashes.tsv

python candidates/USA26-04/tests/hardware/run_portability_suite.py \
  --label work-8core --workers 8 --logical-cpus 8 --timing-repeats 5 \
  --matlab-report /tmp/usa26-04-matlab-fixed-tape.json \
  --require-matlab-report \
  --output /tmp/usa26-04-work8.json \
  --hashes /tmp/usa26-04-work8-hashes.tsv
```

If MATLAB/Octave is unavailable, omitting its report is permitted only for a
diagnostic Work run. Such a report is explicitly
`INCONCLUSIVE_H2_MATLAB_NOT_EVALUATED`, never a complete profile.

The comparator accepts two profiles for a fail-closed partial check, but H5
remains `INCOMPLETE_REQUIRED_PROFILE` until an authenticated GitHub-4 artifact
is included:

```bash
python candidates/USA26-04/tests/hardware/compare_portability_reports.py \
  /tmp/usa26-04-work4.json /tmp/usa26-04-work8.json \
  --output /tmp/usa26-04-work-partial-comparison.json
```

The candidate workflow generates the required GitHub-4 profile and preserves
all status and provenance fields in its uploaded artifact.
