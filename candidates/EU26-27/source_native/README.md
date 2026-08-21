# Source-native OLD harness

This directory does not contain a second implementation of the algorithm.

The scientific OLD is fetched from `FurongYe/GSEMO` at the exact paper-era
commit pinned in `UPSTREAM_LOCK.json`. The upstream tree has no root license at
that revision, so its source is not vendored as project-owned code. CI executes
the original bytes directly after reconstructing the historical dependency
paths.

Files here are only the reproducibility harness:

- `UPSTREAM_LOCK.json` — immutable source/dependency/profile identities;
- `compare_source_native_old.py` — Zenodo raw comparator and SVG generator;
- `PROFESSOR_GATE.md` — fail-closed academic review criteria.

No file in this directory implements TwoRate GSEMO.
