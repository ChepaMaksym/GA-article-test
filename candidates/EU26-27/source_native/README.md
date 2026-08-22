# Source-native OLD harness

This directory does not contain a second implementation of TwoRate GSEMO.

The canonical scientific OLD is fetched from `FurongYe/GSEMO` at the exact
paper-era commit pinned in `UPSTREAM_LOCK.json`. CI executes the original author
bytes after reconstructing the frozen paper-era IOHexperimenter dependency paths.

Files here are the reproducibility harness:

- `UPSTREAM_LOCK.json` — immutable source/dependency identities;
- `compare_source_native_old.py` — shared Zenodo download/parser/plot helpers;
- `compare_source_native_old_fail_closed.py` — canonical paper-faithful exact replay gate;
- `test_compare_source_native_old.py` — unit and negative controls for the canonical gate;
- `PROFESSOR_GATE.md` — academic claim and verification boundary;
- `diagnose_historical_environment.py` — legacy 100k forensic recovery diagnostics only.

## Canonical semantics

The original paper measures function evaluations until the entire Pareto front is
obtained. The canonical replay therefore uses a large non-binding executable safety
ceiling rather than the earlier artificial 100000-FE cap.

Verified canonical result:

```text
PASS_SOURCE_NATIVE_OLD
100/100 complete runs
exact 101x100 first-hit matrix
0 matrix mismatches
exact 100-run endpoint vector
0 endpoint mismatches
source mean = Zenodo mean = 61623.78 FE
```

GitHub Actions evidence: run `32565217851`.

The former 100000-FE experiments remain historical diagnostics explaining how a
binding cap changed the author's single global RNG stream. They are not alternative
OLD implementations and cannot override the canonical gate.
