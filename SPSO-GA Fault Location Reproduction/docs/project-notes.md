# Project Notes

## What Is Reproduced
- IEEE33-node radial branch structure.
- Fault-section signatures for FTU-style binary alarms.
- Objective function based on mismatch between expected and observed FTU states.
- PSO-GA baseline and SPSO-GA variant with article-reported settings.
- Tests and sandbox deviation checks.

## What Is Synthetic
The executable data are `synthetic_reproduction`:

- synthetic fault sections;
- synthetic FTU sensor layouts;
- deterministic alarm flips for noisy cases;
- deterministic missing-FTU layouts.

The reports do not claim exact reproduction of the article's private simulation records.

## Runtime Policy
The article reports 200 repeated tests. This project uses a smaller deterministic smoke-test set by default so it runs quickly, while preserving the same population and iteration settings.
