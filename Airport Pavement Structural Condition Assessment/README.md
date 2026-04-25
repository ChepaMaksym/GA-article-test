# Airport Pavement Structural Condition Assessment

MATLAB project based on the article:

**Using Genetic Algorithms to Improve Airport Pavement Structural Condition Assessment: Code Development and Case Study**

## Files
- `main.m` - root entry point; adds `src` to the MATLAB path and runs the checks plus GA sandbox
- `src/data/` - article-backed constants from Tables 1-7
- `src/models/` - calibrated surrogate response model and fitness function
- `src/optimization/` - executable GA sandbox runner
- `src/replication/` - replication report generator and article consistency checks
- `src/io/` - XML/Appendix extraction utilities
- `docs/deep-research-report.md` - formal article and replication-study overview

## Scope
- This project stores the article inputs and reported outputs in MATLAB form.
- It validates Tables 4, 5, 6, and 7 against the bundled XML article.
- It runs a replication sandbox for the paper's direct validation, indirect GA check, airport case-study deflection basin, and Table 7 error recalculation.
- It runs an executable GA sandbox so `main.m` now performs an actual optimization step, not only table printing.
- It extracts the raw Appendix A section from the XML into `appendix/appendix_a_raw.xml`.
- The executable GA sandbox uses a calibrated surrogate response model; the full Appendix A GA/MLET implementation is still not reconstructed into standalone MATLAB functions.

## Main Commands
- `main` - run the project entry point.
- `run_replication_study` - regenerate `sandbox/results/replication_report.md`.
- `run_ga_surrogate_backcalculation` - regenerate `sandbox/results/ga_surrogate_report.md`.
