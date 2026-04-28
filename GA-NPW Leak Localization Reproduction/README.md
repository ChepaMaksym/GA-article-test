# GA-NPW Leak Localization Reproduction

MATLAB reproduction package for the article:

**Genetic algorithm optimization of negative pressure wave method for robust real time leak detection in long distance pipelines**

Source: https://www.nature.com/articles/s41598-025-20525-5

This project is intentionally conservative. It reproduces the article's GA-NPW structure with article-reported GA settings and synthetic validation scenarios. It does not use SAA or any optimizer that is not part of the article.

## Structure
- `article/` - local research reference document.
- `docs/` - article summary, project notes, and verification guide.
- `docs/GA-NPW Research Verification Report.docx` - Word report: what was reproduced, missing inputs, and verified checks.
- `docs/GA-NPW Project Workflow Explanation.docx` - Word explanation of how the project works and how to verify it.
- `main.m` - full workflow entry point.
- `run_*.m` - root-level command wrappers.
- `src/data/` - `article_reported` facts and `synthetic_reproduction` scenarios.
- `src/models/` - NPW equations, observation builder, and GA-NPW fitness.
- `src/optimization/` - article-configured GA and reproduction/sandbox runners.
- `src/metrics/` - localization error metrics.
- `src/replication/` - structure verification.
- `tests/` - deterministic unit tests.
- `sandbox/results/` - generated reports and MAT result files.

## MATLAB Commands
Run from this folder:

```matlab
main
run_ga_npw_reproduction
run_sandbox_deviation_check
run_unit_tests
```

## Scope
The real field pressure time series and Pipeline Studio model from the article are not public in this workspace. Therefore, this project separates:

- `article_reported`: values and claims directly reported by the paper.
- `synthetic_reproduction`: deterministic or seeded scenarios used only to verify the GA-NPW workflow.

Generated sandbox results must not be presented as field-test results from the authors.
