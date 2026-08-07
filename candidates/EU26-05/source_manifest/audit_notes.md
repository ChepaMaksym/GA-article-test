# EU26-05 source and admission audit

Audit date: 2026-08-07. No CEC-2017 outcome or published-result replay was
run during this audit.

## Decision

Retain **`conditional_noneligible`** and authorize only
**`FORMULA_AND_TRANSITION_VALIDATION_ONLY`**.

EU26-05 is stronger than EU26-04 and EU26-06 for a narrow validation PR:
the exact-title chapter postprint is lawfully listed by the University of
Trieste, the selected chromosome has 600 binary loci for 30 decision
coordinates, the adaptive object is genuinely a crossover/operator-selection
control, and the probability/crossover core admits discriminating
hand-computable tests in both Python and MATLAB/Octave.

This does not make the study eligible for numerical reproduction. The exact
postprint bytes cannot yet be SHA-256 frozen from the audit host; no author
code, raw outputs or seeds are available; the CEC implementation/license is
unfrozen; and the sources contain material ambiguities in minimization,
preference indexing, zero-denominator handling, success equality, decode,
selection and replacement.

## Primary-source findings

The Springer record identifies the chapter, DOI, four authors, publication
date 2023-03-29, pages 3-18 and LNCS 13986. ArTS handle `11368/3046333`
identifies the same title/authors/DOI. Its OAI DIDL record declares open access
and exposes a 2,921,299-byte postprint component. The repository page says the
postprint has been open since 2024-03-30.

The postprint reports the following selected `d=30` protocol: 600-bit
chromosome, population 400, 200 generations/80,000 evaluations, 30 independent
runs, crossover probability 100%, mutation 0%, tournament size 3 and four
preference levels `0..3`. It states the literal endpoint that at least one P/P'
variant improves fitness on 27 of 30 functions.

The NOVA thesis gives additional probability-boundary and extension-ray prose:
four 10% floors leave 60% to normalized contributions, all-zero successful
contributions reset to equal, the maximum binary extension complements common
loci after copying the second parent, and the operation is applied in both
directions. These details are thesis-grounded, not silently promoted to
chapter code provenance.

## Gate corrections

- C1 stays unresolved at byte level: exact lawful metadata/full text is
  established, but the PDF SHA-256 is not.
- C2, G3 and G4 pass.
- G5 changes from `pass` to `unresolved`: `tau_max` is used inconsistently,
  minimization selection is not executable as printed, and `#Cross=0` is
  unspecified.
- G6 changes from `pass` to `unresolved`: binary decode, sampling/ties,
  P' removal duration and full replacement/evaluation order are missing.
- G7 stays unresolved because no exact licensed CEC input implementation is
  frozen.
- G8 stays unresolved for reproduction: 27/30 is literal, but the per-function
  values, tie rule and executable aggregation are absent.
- G9 stays unresolved: 30 runs are stated, while seeds/RNG/raw provenance are
  absent.
- G10 passes for a clean-room formula kernel. No source-native artifact was
  claimed, so source-native replay is not waived into existence.

The contract's probability oracle deliberately rejects a zero denominator,
and its transition oracle starts after parent/preference selection. Those
fail-closed boundaries prevent a formula pass from being mistaken for a full
paper pipeline.
