# EU26-12 eligibility audit

Audit date: 2026-08-09. This record was frozen before candidate-local
verifier implementation and before any source-native execution.

## Candidate and eligibility

- Diederick Vermetten, Fabio Caraffini, Anna V. Kononova, and Thomas Bäck,
  *Modular Differential Evolution*, GECCO 2023, DOI
  `10.1145/3583131.3590417`.
- Qualifying European affiliation: Vermetten, Kononova, and Bäck are
  affiliated with Leiden Institute for Advanced Computer Science, the
  Netherlands. Caraffini is affiliated with Swansea University, United
  Kingdom.
- Direct optimization: Experiment 1 directly minimizes the 24 noiseless BBOB
  functions at dimensions `D in {5, 10, 20}`. The selected endpoint is at
  `D=20`, above the minimum 11 decision variables. This is not inversion,
  parameter estimation, or surrogate-only optimization.
- Full evolutionary algorithm: L-SHADE is instantiated as a complete
  population-based Differential Evolution algorithm with mutation, binomial
  crossover, bound correction, parent-offspring replacement, an external
  archive, and termination by objective state or evaluation budget.
- Within-run adaptation: the selected L-SHADE run adapts mutation scale `F`,
  crossover rate `CR`, and population size. Successful offspring update the
  `F`/`CR` memories; fresh parameters are sampled from those memories; linear
  population-size reduction changes `lambda` throughout the run.
- Legal artifacts: an arXiv full manuscript is available. The paper cites the
  immutable Zenodo record `10.5281/zenodo.7624677`, whose record license is
  CC-BY-4.0. The static `ModDE.zip` additionally contains an MIT license.
- Numeric evidence: the Zenodo `raw_data.zip` contains seed-addressable IOH
  JSON and DAT members. The exact selected JSON member can be authenticated
  and extracted by HTTP range requests without vendoring the 4.8-GB archive.

All subject, year, geography, direct-objective, dimension, full-EA,
within-run-control, legal-full-text, pinned-code, licensed-data, seed, and
exact-numeric-evidence gates pass for a bounded artifact study.

## Admission decision

Status: **`ADMITTED_TARGETED_ARTIFACT`**

Study status: **`TARGETED_ARTIFACT_REPLAY_ONLY`**

Paper mapping: **`PAPER_EXPERIMENT_ARTIFACT_MAPPING`**

The paper explicitly identifies the Zenodo repository as the scripts, raw IOH
verification runs, analysis, and visualization material for its experiments.
The paper specifies Experiment 1, the L-SHADE configuration, dimensions, run
count, instances, and budget. The selected single-run double-precision value
is present in the cited artifact but is not printed literally in the paper.

## Mandatory conflicts and hard stops

1. The paper does not print the selected run's exact objective value. A
   successful replay is an authenticated paper-experiment artifact result, not
   a literal paper table cell.
2. `requirements.txt` gives only lower bounds: `ioh>=0.3.5`,
   `numpy>=1.18.5`, `scipy>=1.9.1`, and `numba>=0.55.1`. The artifact does not
   freeze the authors' exact NumPy, SciPy, Numba, or Python patch versions.
3. The runner calls legacy global `np.random.seed(seed)` and `np.random.*`.
   The seed schedule and RNG API are explicit, but exact dependency provenance
   and every library-level tie/order behavior are not.
4. Population ordering uses default `np.argsort`; equal-fitness ordering is
   not explicitly stabilized. Replacement selects the offspring on equality,
   but equality is not treated as an improvement for memory adaptation.
5. The source's `F` memory update is a weighted arithmetic mean, not the
   canonical SHADE weighted Lehmer mean. Verification must preserve the
   released implementation rather than silently substitute the literature
   formula.
6. Initialization evaluations bypass `parameters.used_budget`, while the IOH
   stop condition is checked after a complete generation. For the selected
   run this turns a requested budget of 50,000 into 50,002 logged evaluations.
7. The DAT member prints objective values to ten decimal places and ends at
   `0.0000000000`; it cannot replace the exact JSON double
   `1.698652750709869e-14`.
8. The full `raw_data.zip` MD5 is declared by immutable Zenodo metadata but is
   not recomputed by the range-only verifier. Authentication is bounded to
   frozen archive structure and exact member bytes.

No candidate-local check may clear these conflicts. `PASS_FULL`,
`PASS_LITERAL_PAPER_ENDPOINT`, `HISTORICAL_DEPENDENCY_ENVIRONMENT_PROVEN`, and
`FULL_ARCHIVE_MD5_RECOMPUTED` are forbidden.

## Timing disclosure

Candidate triage inspected the legal manuscript, paper experiment description,
Zenodo metadata, static source archive, official runner, ZIP64 directory, and
the first eligible L-SHADE `D=20` run before this freeze. The endpoint was
selected lexicographically—common variant L-SHADE, BBOB F1, dimension 20,
instance 0, seed 0—rather than by outcome magnitude. No candidate-local
verifier or independent control implementation existed at selection time, and
no tolerance was chosen from a replay deviation. Exact identity and exact
decimal equality are required.
