# EU26-16 eligibility audit

Audit date: 2026-08-09. The claim boundary and source identities below were
frozen before implementing the candidate-local transition verifier.

## Candidate facts

- Jose M. Moyano and Sebastian Ventura, *Auto-adaptive Grammar-Guided Genetic
  Programming algorithm to build Ensembles of Multi-Label Classifiers*,
  Information Fusion 78 (2022), DOI `10.1016/j.inffus.2021.07.005`.
- Both authors are affiliated with the University of Cordoba / Andalusian
  Research Institute in Data Science and Computational Intelligence, Spain.
- The article is open access under CC BY 4.0. The audited institutional copy
  has SHA-256
  `20868324adba7cbfadc004afa0624503ead29f4406701aca6f5650862cbdb517`.
- The method is a grammar-guided genetic-programming member of the GA family.
  Its source directly changes the probabilities of its crossover and mutation
  operators during one run.
- The paper reports real multi-label learning applications. Its Yeast case has
  103 input attributes and 14 output labels; the shipped fold-1 ARFF/XML bytes
  independently expose the same dimensions.
- The authors' repository has a root GPL-3.0 license and a publication-era
  `v3.0` tag at commit
  `a800162492ee8ccb4e20f692b879610cb607db07`.

These facts are sufficient for a bounded source/formula study. They are not
sufficient for an empirical published-result reproduction.

## Adaptation audit

In `src/g3pkemlc/Alg.java`, `doControl()` executes in this order:

1. select the current best individual and round its fitness to four decimals;
2. update `bestFitness` and `lastIterBestFitness` on strict improvement;
3. cast the current population mean to Java `float`;
4. compare it strictly with `bestAvgFitness`;
5. on improvement, assign `bestAvgFitness = avgFitness` before the guard and
   attempt `pc += 0.02`, `pm -= 0.02`;
6. otherwise, including equality, attempt `pc -= 0.02`, `pm += 0.02`; and
7. evaluate the ten-generation and maximum-generation stop condition.

The guards are strict source predicates:

```text
improvement:     pc < 1 - 2*step and pm >= 2*step
non-improvement: pm < 1 - 2*step and pc >= 2*step
step = Java float(0.02)
```

There is no clamp. The commonly observed `[0.04, 0.96]` range is valid only
for the lattice generated from the paper/config initial state `0.5, 0.5`.
Off-lattice inputs can cross it; `(0.95, 0.05)` becomes `(0.97, 0.03)` on an
improving average.

## Admission decision

Status: **`FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY`**

Readiness: **`CONDITIONAL_NONELIGIBLE`**

The candidate is admitted only to:

- authenticate the exact tagged source and required members;
- probe the published transition, rounding, and stop-ordering tokens;
- compare independent Python and MATLAB/Octave transition fixtures; and
- prove the structural dimension of the available Yeast fold-1 data while
  detecting the incomplete experiment manifest.

It is not admitted to the ranked empirical reproduction queue.

## Mandatory blockers

1. The paper specifies ten random seeds but does not enumerate them.
2. The paper specifies random five-fold cross-validation, while the shipped
   Yeast configuration names two folds and only fold 1 is present.
3. The shipped seed list (`10`, `20`, `100`) is not the paper's complete
   ten-seed ledger.
4. No raw 50-run Table 7 ledger or exact publication driver is shipped.
5. The exact Table 7 variants (`AG3P-k3`, `AG3P-ku`, and `AG3P-kg`) are not
   fully bound to the available `cfg/Yeast.xml`, whose `min-k` and `max-k` are
   both 3.
6. The upstream license/provenance of the redistributed Yeast dataset bytes is
   unresolved. The repository's GPL-3.0 license establishes code permission;
   it does not, by itself, prove the dataset provider had authority to
   relicense the inputs.
7. Table 7 values are 50-run averages. A fold-1 smoke run with seed 10 has no
   literal single-run paper comparator.

Passing source, transition, and dimension checks cannot clear any blocker.
The forbidden claims are `PASS_FULL`, `PASS_TABLE_7_REPLAY`,
`PASS_EMPIRICAL_REPRODUCTION`, and `DATASET_LICENSE_RESOLVED`.
