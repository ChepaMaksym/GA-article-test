# NMGA Strong Source Location Reproduction

MATLAB replication package for:

**Application of New Modified Genetic Algorithm in Inverse Calculation of Strong Source Location**

Source: https://www.mdpi.com/2073-4433/14/1/89  
DOI: `10.3390/atmos14010089`

This project reproduces the article's workflow structure: Gaussian plume forward model, MGA/NMGA inverse source calculation, deterministic tests, and synthetic sandbox scenarios. Raw field/simulation monitoring data from the article are not available in this workspace, so generated runs are clearly labeled `synthetic_reproduction`.

## Structure
- `main.m` - full workflow entry point.
- `run_nmga_reproduction.m` - root command for article-aligned MGA/NMGA comparison.
- `run_sandbox_deviation_check.m` - root command for stress-case sandbox.
- `run_unit_tests.m` - deterministic test command.
- `docs/` - article summary, project notes, and verification guide.
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
run_nmga_reproduction
run_sandbox_deviation_check
```

For a longer article-sized repetition count, use:

```matlab
run_nmga_reproduction('full')
```

The default command uses a smaller deterministic run so the project remains practical as a local smoke-test sandbox.
