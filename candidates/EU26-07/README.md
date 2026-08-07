# EU26-07 — resetting self-adjusting `(1+(lambda,lambda))` GA

Paper: Mario Alejandro Hevia Fajardo and Dirk Sudholt, *Theoretical and
Empirical Analysis of Parameter Control Mechanisms in the
`(1+(lambda,lambda))` Genetic Algorithm*, ACM TELO 2(4), Article 13,
DOI [`10.1145/3564755`](https://doi.org/10.1145/3564755).

Author artifacts:

- [open paper PDF](https://mhevia.com/assets/pdf/journal_oplclga.pdf);
- [implementation and result repository](https://github.com/mariohevia/Parameter-Control-Mechanisms-Genetic-Algorithm),
  pinned to `49949a55208359ac93b7110afb23ed276bda158d`.

Frozen target: the resetting self-adjusting Algorithm 3 profile on
`Jump_4`, `n=20`, with `lambda_0=1`, `lambda_max=20`, `F=1.5`, and 500
published runs from base seed `816114841`. The author processed result reports
mean `108964.48`, median `84730`, Q1 `32787`, and Q3 `150829` logical
evaluations.

Artifact status: **`PASS_TARGET_ARTIFACT_REPLAY`**.

All 500 source-native rows and all 500 independent compatibility rows matched
the authenticated author ledger exactly for every frozen field. The canonical
row digest is
`6e5b6b6da38d0c2d846b3379150532667447a0ff38fb64aae3148149db41d176`.
The retained report is in [`results/formal-full-replay.json`](results/formal-full-replay.json).
The separate GNU Octave H7 formula gate remains a CI/runtime check because
Octave was unavailable in the local replay environment.

## Three explicitly separate semantics

| Profile | Rounding | Final selection pool | Purpose |
|---|---|---|---|
| `paper_algorithm3` | nearest, half up | selected best mutant + crossovers | Formula verification |
| `artifact_generic` | Python ties to even | all mutants + crossovers | Generic source diagnostics |
| `artifact_jump_optimized` | Python ties to even | all mutants + crossovers, with Jump shortcuts | Exact raw-ledger replay |

The paper and author source are not interchangeable. The printed Algorithm 3
orders acceptance before its strict-success comparison, the source retains all
mutants in the final pool, and their rounding rules differ at exact halves.
The published raw ledger also comes from a Jump-specialized shortcut class.
Those facts permanently block `PASS_FULL`; a successful run can establish only
the named paper-formula and target-artifact profiles.

No GPL source or raw result file is vendored. The independent compatibility
implementation discloses the source-specific behavior it mirrors; this is a
scientific provenance description, not a legal originality conclusion. The
source adapter loads a separate external checkout only after verifying its
commit, tree, nine byte counts and nine SHA-256 values.

## Local verification

The source-native/raw replay requires Linux, macOS, or WSL with a
POSIX-compatible filesystem: the frozen upstream filename contains colon
characters and cannot be checked out on native Windows/NTFS. Formula tests do
not depend on that external filename.

```bash
python -m pip install -r candidates/EU26-07/environments/python/requirements.txt
export EU2607_UPSTREAM=/path/to/pinned/author/checkout
python candidates/EU26-07/tests/run_python_tests.py
python candidates/EU26-07/environments/python/run_full_verification.py \
  --upstream "$EU2607_UPSTREAM" \
  --workers 4 \
  --output /tmp/eu26-07-full-replay.json
```

For the cross-language formula gate:

```bash
octave --quiet --eval \
  "addpath('candidates/EU26-07/tests/matlab'); run_matlab_tests"
```

The author repository has no dependency lock or container. The replay
environment is therefore recorded as a verification environment, not
misrepresented as the original environment.
