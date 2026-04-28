# Irrigation Network GA Replication Project

MATLAB replication package for:

**Synchronization Optimization of Pipe Diameter and Operation Frequency in a Pressurized Irrigation Network Based on the Genetic Algorithm**

## Structure
- `article/article.xml` - bundled JATS XML article.
- `main.m` - root entry point.
- `src/data/` - article-backed metadata and Tables 1-6.
- `src/models/` - simplified annual-cost and surrogate fitness logic.
- `src/optimization/` - executable GA sandbox.
- `src/replication/` - consistency checks and report generation.
- `src/io/` - XML path helper.
- `docs/deep-research-report.md` - formal article and replication overview.
- `sandbox/results/` - generated reports and MATLAB result objects.

## Commands
Run from the project root in MATLAB:

```matlab
main
run_replication_study
run_ga_irrigation_sandbox
```

## Scope
This project encodes the article tables and runs a real GA sandbox. The sandbox uses a simplified surrogate cost model because the article XML does not include the original MATLAB code or the full Figure 5 network geometry/length dataset required for full hydraulic reproduction.
