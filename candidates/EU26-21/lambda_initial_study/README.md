# Initial-lambda sensitivity series

Registered prospective follow-up: `EU26-21-LAMBDA-INITIAL-WBA-400-V1`.

- Registration commit: `fdf093fd4b53ecf48a148d86b28c8ecee007e7aa`.
- Protocol SHA-256: `8f96fbf91ae5e92b90409c3ba0492da2d13551bca0d49e273d299dd4ac1453b4`.
- [Admission](ADMISSION_UK.md), [scientific protocol](PROTOCOL_UK.md),
  [machine-readable specification](protocol.json).
- Reused search kernels are byte-pinned to
  `c5c9f1e870f4e80014d9f8d90bd76eb5a9d025a0`; no historical source or outcome
  is rewritten.

Six methods share each split and 50 ordered initial masks: harmonized CHC
and adaptive `(1+(λ,λ))` starting at λ = 1, 5, 10, 20, 40. Only the initial
50 physical evaluations are shared; their scores are replayed positionally
to each independent 400-call ledger. All subsequent queries, including
duplicates, are physically evaluated. Saved fits do not enlarge any search.

The primary outcome is mean paired post-initialization BSF-AUC, with four
registered Bonferroni-adjusted BCa contrasts against initial λ = 1. The ten
secondary contrasts against CHC gate any joint quality-preserving search
advantage. Every method remains in the report, including negative outcomes.
An initialization study is not a new local-optimum escape experiment.

## Execution and retained evidence

Local scientific execution is not authorized. The workflow
[eu26-21-lambda-initial-study.yml](../../../.github/workflows/eu26-21-lambda-initial-study.yml)
runs synthetic contracts and authenticated transport on a normal push;
science requires an SHA-bound `workflow_dispatch`. The distinct launch
marker `[launch-lambda-initial]` requests that dispatch only after preflight.
One seed job evaluates all six methods; all 30 must finish before the report.

`select_artifacts.py` fixes IDs by uploaded attempt without reading outcomes.
The transport helper authenticates metadata, ZIP size and digest before
extraction. `aggregate.py` checks complete manifests, traces, mask freezes,
duplicate/call accounting, class metrics and source SHA before statistics.
Downloaded joblib models are hashed, never deserialized in aggregation.

Implementation and authenticated transport verified on
`2892737a00607e03c62528deeeec4bcd5659c4e0`: all 345 synthetic tests passed.
The [new preflight](https://github.com/ChepaMaksym/GA-article-test/actions/runs/37217954946),
[older full-test preflight](https://github.com/ChepaMaksym/GA-article-test/actions/runs/37217955009),
[code-quality audit](https://github.com/ChepaMaksym/GA-article-test/actions/runs/37217955006)
and [independent audit](https://github.com/ChepaMaksym/GA-article-test/actions/runs/37217954958)
are green. The frozen campaign completed successfully on 4 October 2026
at `ce7b9a24782ae3f97b0b3cb954eb7d8b989bfe32`: all 30 six-arm jobs and
the complete-only aggregation passed, with no scientific-run retries.
[Retained results and qualified conclusions](evidence/2026-10-04/README_UK.md)
include both figures, all contrasts and exact source IDs/digests.

No initial λ = 5, 10 or 20 significantly improved post-initialization AUC
against initial λ = 1; initial λ = 40 had lower AUC. The separate secondary
quality-preserving search criterion against CHC passed for initial λ = 5
and 20 only. No test-accuracy superiority or universally optimal initial
parameter is established. Historical negative conclusions remain unchanged.
PR19 remains draft; merge is not authorized. Word and local progress files
are kept outside this repository.
