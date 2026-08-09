# EU26-16 source-transition contract v1

Frozen: 2026-08-09, before candidate-local implementation.

Status: **`FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY`**

Readiness: **`CONDITIONAL_NONELIGIBLE`**

Paper mapping: **`TABLE_7_NOT_REPLAYABLE_FROM_SHIPPED_ARTIFACTS`**

## Frozen identities

- DOI: `10.1016/j.inffus.2021.07.005`.
- Institutional full text: 1,429,980 bytes, SHA-256
  `20868324adba7cbfadc004afa0624503ead29f4406701aca6f5650862cbdb517`,
  CC BY 4.0.
- Repository: `https://github.com/kdis-lab/G3P-kEMLC.git`.
- Tag: `v3.0`.
- Commit: `a800162492ee8ccb4e20f692b879610cb607db07`.
- Tree: `8377a7be53e33bc6759cf079f22f30126dd50f83`.
- Root license: GPL-3.0, SHA-256
  `8646559c866597b7bf28d110cde63de18f6d97354bf22559053301bc3ca492c5`.
- `Alg.java`: SHA-256
  `5581a346307475f090fde878fe5c089602bde6308adba7df0016a343b191b388`.

The complete required-member inventory is machine-readable in
`config/verification_contract.json` and `source_manifest/sources.csv`.
Candidate code does not vendor upstream source or data.

## Frozen transition

Initial state:

```text
pc = 0.5
pm = 0.5
bestAvgFitness = Java float(0)
bestFitness = Java float(-1)
lastIterBestFitness = 0
step = Java float(0.02)
```

For generation `g`, first round the current best fitness using the exact
positive-fitness Java-float sequence in the source:

```text
x = Java float(current_best)
x = Java float(x * 10000)
x = Java Math.round(x)
x = Java float(x / 10000)
```

Update `bestFitness` and `lastIterBestFitness` only if the rounded value is
strictly greater. Cast the current population average to Java `float` and then:

```text
if avgFitness > bestAvgFitness:
    bestAvgFitness = avgFitness
    if pc < 1 - 2*step and pm >= 2*step:
        pc = pc + 0.02
        pm = pm - 0.02
else:
    if pm < 1 - 2*step and pc >= 2*step:
        pc = pc - 0.02
        pm = pm + 0.02
```

Only after those operations:

```text
stop = ((g >= lastIterBestFitness + 10 and bestFitness > 0)
        or g >= maxOfGenerations)
```

The verifier must preserve the absence of clamping. `[0.04, 0.96]` is a
publication-lattice property, not a global range. Both languages must test the
off-lattice transitions `.95/.05 -> .97/.03` and `.05/.95 -> .03/.97`.

## Structural data target

The only accepted data claim is structural:

| Item | Frozen value |
|---|---:|
| Yeast inputs | 103 |
| Yeast labels | 14 |
| fold-1 train rows | 1,933 |
| fold-1 test rows | 484 |
| fold-1 total rows | 2,417 |
| config seeds | 3 (`10`, `20`, `100`) |
| config fold references | 2 |
| materialized folds | 1 |
| paper-required folds | 5 |
| paper-required seeds | 10, identities unreported |

No metric, runtime, or Table 7 cell is an acceptance target.

## Gates

| Gate | Requirement |
|---|---|
| S1 source identity | Clean exact commit/tree; tag target; byte size, Git blob, and SHA-256 of every required member match before and after use. |
| S2 token probe | Required `Alg.java` tokens exist and their order proves rounding, historical-best updates, guarded probability changes, then stopping. |
| T1 Python transition | Standard-library implementation passes all frozen and adversarial fixtures. |
| T2 MATLAB/Octave transition | Independent implementation passes the same semantic cases and source-order assertions. |
| T3 invariants | `pc + pm = 1` on all valid fixtures; lattice endpoints and off-lattice non-clamping are distinguished. |
| D1 fold-1 structure | Exact authenticated ARFF/XML files parse as 103 inputs, 14 labels, and 2,417 rows. |
| D2 incompleteness detection | Missing fold 2 and deficient paper seed/fold manifest are detected and a Table 7 readiness assertion fails closed. |
| B1 claim boundary | Every report retains conditional noneligibility and all forbidden claims. |

Allowed success labels are `PASS_SOURCE_IDENTITY`,
`PASS_SOURCE_TRANSITION`, `PASS_DATASET_STRUCTURE`, and
`PASS_MATLAB_OCTAVE_INDEPENDENT`. The aggregate report status may be only
`PASS_FORMULA_AND_SOURCE_TRANSITION_ONLY` or `FAIL_OR_INCOMPLETE`.

`PASS_FULL`, `PASS_TABLE_7_REPLAY`, `PASS_EMPIRICAL_REPRODUCTION`, and
`DATASET_LICENSE_RESOLVED` are forbidden.
