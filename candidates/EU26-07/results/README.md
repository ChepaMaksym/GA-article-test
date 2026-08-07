# Formal replay result

Status: **`PASS_TARGET_ARTIFACT_REPLAY`**

The preregistered verifier at clean commit
`282b9dcc01b189c8344f8d12cef82f640a09b8ee` examined all 500 ordered runs.
For every run, both the pinned author class and the independent compatibility
implementation matched the authenticated author raw row exactly for run seed,
generations, logical evaluations, final rounded lambda, last mutation
probability and solved flag.

| Check | Result |
|---|---:|
| Source-native rows matched | 500 / 500 |
| Compatibility rows matched | 500 / 500 |
| First failure | none |
| Raw/source/compatibility canonical digest | `6e5b6b6da38d0c2d846b3379150532667447a0ff38fb64aae3148149db41d176` |
| Raw artifact SHA-256 | `b2ac8c81efaf786823d49dcef26eeb20f0257ca7fe9e1e2394d02ca5e26dd9a6` |
| Formal report SHA-256 | `93e49149f97e9c96c6b38d43395ed0933737f1f9549c7c176eb28aafe9c7e945` |

The raw ledger recomputed the declared 500-run mean `108964.48`, median
`84730`, Q1 `32787`, and Q3 `150829` exactly. Population SD
`99730.17415323008` and sample SD `99830.05417240708` are derived diagnostics,
not author-published values.

H0–H6 passed. H7 is deliberately outside the Python replay report and is run
as a separate GNU Octave workflow job. The paper-level status remains
**`BLOCKED_PAPER_SOURCE_DIVERGENCES`**; this result is not `PASS_FULL`.
