# EU26-15 — GARBO fuzzy-transition validation

**Candidate status:** `CONDITIONAL_NONELIGIBLE`

**Permitted scope:** `FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY`

**`PASS_FULL`:** forbidden

This package freezes and independently checks the fuzzy state transition in
GARBO, the adaptive feature-selection GA described by Fortino et al. It does
not reproduce an empirical run, the paper's Table 2, or a biomarker panel.

## What is bound

- Paper: V. Fortino et al., *Feature set optimization in biomarker discovery
  from genome-scale data*, Bioinformatics 36(10), 2020,
  <https://doi.org/10.1093/bioinformatics/btaa144>.
- Author-linked repository: <https://github.com/Greco-Lab/GARBO>.
- Licensed revision:
  `9727e017371484dd5837a0859b41c195a87fd8d0`, tree
  `995ee6c51315ea52d0e82211fb708e32b45800bb`.
- Paper-era source revision:
  `1854385ffb0be85ef8deeeda45980aaed6e50207`. Its `GARBO.py` and
  `runGARBO.py` bytes are identical to the licensed revision. The GPL-3.0
  file itself was added later, on 2024-11-05.

The verifier covers the sampled fuzzy universes, membership interpolation,
all 9-rule crossover/mutation/insertion/deletion and feature-rank branches,
piecewise-area centroid defuzzification, the strict `ssc > 0.75` override,
and the population statistics `fv`, `ft`, `mlc`, and `ssc`.

One upstream quirk is intentionally preserved: `mutationFLRules(ft, mlc)`
classifies `ft` with `intFV`, not `intFT`. Treating that call as a typo would
validate a different algorithm.

## Claim boundary

Allowed claims are limited to source identity and deterministic transition
agreement for frozen synthetic fixtures. In particular:

- no source-native stochastic GARBO run is executed;
- no Table 2 value is replayed or treated as reproduced;
- no dataset redistribution or dataset-license claim is made;
- no result may be labelled `PASS_FULL`.

The repository CSV was observed to have 1,600 columns: 1,599 candidate
predictors plus `class`. That is decision-dimension evidence only. Its lawful
reuse provenance is unresolved, so the data are neither copied here nor part
of the mandatory test path.

## Blockers

1. `runGARBO.py` seeds Python's `random` module, while `GARBO.py` also uses
   unseeded `numpy.random` calls in initialization and operators.
2. Paper split identities, exact stochastic seeds, and raw run ledgers are
   absent.
3. The bundled CSV has no complete dataset-level lawful provenance manifest.
4. The source targets Python 2.7 and lists dependencies without versions.
5. There is no paper-specific tag or release.

See the [eligibility audit](preregistration/eligibility_audit.md), frozen
[verification contract](preregistration/verification_contract.md), and exact
[source manifest](source_manifest/sources.csv) before interpreting any test.

## Verification commands

After the implementation commit:

```bash
python candidates/EU26-15/tests/run_python_tests.py
octave --quiet --eval "addpath('candidates/EU26-15/tests/octave'); run_octave_tests"
```

An exact upstream checkout can additionally be probed without importing its
Python-2 stack:

```bash
python candidates/EU26-15/environments/python/verify_source.py \
  --source-dir /path/to/GARBO-at-9727e017
```

The optional `--data-csv` probe reports only row/column structure and does not
change the unresolved data-license status.
