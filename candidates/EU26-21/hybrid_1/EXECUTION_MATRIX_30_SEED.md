# Seed-parallel execution amendment

Status: `EXECUTION_ONLY_NO_SCIENTIFIC_CHANGE`.

The corrected v2 protocol initially executed all 30 paired seeds sequentially
inside one GitHub Actions job. Since each seed is statistically and
computationally independent, this wastes runner wall-clock time without adding
a reproducibility benefit.

The campaign is therefore executed as a GitHub Actions matrix:

- one isolated runner process per seed;
- the same pinned source commit and Python dependencies in every job;
- the same seed-specific active sample and initial masks as v2;
- the same OLD and Hybrid code, budgets, targets, margins, and stopping rules;
- Hybrid H3 remains `workers=1` inside every seed for exact objective-call
  order;
- Hybrid H1 remains `workers=4`, whose final-result invariance was already
  tested;
- one deterministic aggregation job validates the complete `1..30` ledger and
  computes the frozen BCa decisions.

Parallelizing different seeds does not change random streams or within-seed
scientific outputs. The abandoned sequential v2 run was cancelled before final
aggregation; its partial rows are not used.
