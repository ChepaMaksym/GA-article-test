# EU26-09 source and provenance audit

Audit date: 2026-08-09. No source-native command was run before the contract
was frozen.

## Revision and non-vendoring policy

The official repository's publication-era commit
`49949a55208359ac93b7110afb23ed276bda158d` has tree
`a9d1a04fbbafbb114585ff7caf10bddc6381755a` and commit date
2021-01-05. The paper and README identify the repository but not this commit,
tag, or a dependency lock. Candidate-local code therefore calls the pin
auditor-selected and never claims historical execution provenance.

The root GPL-3.0 license permits inspection and execution. Nevertheless, this
study vendors none of the paper, source, raw, processed, or graph bytes. A
caller supplies a clean upstream checkout; verification authenticates required
members before and after use.

## Endpoint provenance

The README explicitly gives the selected OneMax command. The frozen raw member
contains exactly 500 run rows and the four exact mean footers. Its companion
processed result repeats the raw content and independently reports mean and
quantiles for evaluations; it is corroborating provenance, not the target
input.

The paper states that its OneMax comparison uses 500 runs and displays average
fitness evaluations in Figure 5. It does not print the frozen raw endpoint or
identify this result filename. The study consequently retains
`PAPER_FIGURE_CONTEXT_ONLY` and cannot claim a literal paper replay.

## Audited source semantics

`master.py` seeds both `numpy.random` and Python `random` with
`base_seed + run_id` for runs 1 through 500. The reset class starts at real
`lambda=1`, records pre-generation mutation probability and rounded lambda,
samples mutation strength from a binomial distribution, performs rounded
mutation and crossover populations, applies random tie selection, counts
`2*round(lambda)` evaluations, and then updates lambda.

The source appends mutation offspring and crossover offspring to the same
selection pool, excludes exact parent duplicates in final selection, and does
not count initial-parent evaluation. At a failed generation whose real lambda
equals the cap exactly it resets lambda to one.

Two conflicts are material: paper pseudocode uses `ceil(lambda)` while Python
source uses ties-to-even `round(lambda)`, and no historical dependency versions
are locked. Candidate-local code implements and reports both rounding profiles
but accepts only the authenticated artifact/source profile for this endpoint.
