# NMGA Strong Source Location Reproduction

MATLAB replication package for:

**Application of New Modified Genetic Algorithm in Inverse Calculation of Strong Source Location**

Source: https://www.mdpi.com/2073-4433/14/1/89  
DOI: `10.3390/atmos14010089`

This project reproduces the article's workflow structure: Gaussian plume forward model, MGA/NMGA inverse source calculation, deterministic tests, and synthetic sandbox scenarios. Raw field/simulation monitoring data from the article are not available in this workspace, so generated runs are clearly labeled `synthetic_reproduction`.

## Structure
- `main.m` - full workflow entry point.
- `run_article_exact_reproduction.m` - public-text exact Table 1 protocol runner with raw-data limitation labels.
- `run_nmga_reproduction.m` - root command for article-aligned MGA/NMGA comparison.
- `run_nmga_adaptive_audit.m` - root command for scheduled-adaptive control audit scenarios.
- `run_sandbox_deviation_check.m` - root command for stress-case sandbox.
- `run_unit_tests.m` - deterministic test command.
- `docs/` - article summary, project notes, replication audit, and verification guide.
- `docs/NMGA Research Completion Report.docx` - Word report: what was completed, what is missing, and what was verified.
- `docs/NMGA Algorithm Technical Explanation.docx` - Word explanation of the inverse problem, NMGA algorithm, and technical workflow.
- `src/data/` - article-reported values and synthetic scenarios.
- `src/models/` - Gaussian plume and inverse objective functions.
- `src/optimization/` - MGA and NMGA implementations.
- `src/metrics/` - source-estimation metrics.
- `sandbox/results/` - generated Markdown and MAT reports.

## Commands
Run from this folder in MATLAB:

```matlab
main
run_unit_tests
run_article_exact_reproduction
run_nmga_reproduction
run_nmga_adaptive_audit
run_sandbox_deviation_check
```

For a longer article-sized repetition count, use:

```matlab
run_article_exact_reproduction('article_exact')
run_nmga_reproduction('full')
run_nmga_adaptive_audit('full')
```

The default command uses a smaller deterministic run so the project remains practical as a local smoke-test sandbox.
`main` runs the adaptive audit with the `unit` profile; run `run_nmga_adaptive_audit` directly for the wider default quick audit.
`run_article_exact_reproduction` defaults to the expensive public-text Table 1 protocol: `MGA 100 x 2000`, `NMGA 100 x 1000`, and `NMGA 100 x 500`. Use `run_article_exact_reproduction('unit')` only as a smoke check of reports/operators.
