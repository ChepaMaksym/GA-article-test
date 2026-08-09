# EU26-14 source and semantic audit

Audit date: 2026-08-09. No source-native endpoint run was executed before the
contract was frozen.

## Paper and artifact mapping

The arXiv record links the official repository, and Zenodo record 21483843
identifies itself as benchmark data for MSC-CMA-ES on CEC2014, CEC2017,
CEC2020, and CEC2022 and as a supplement to arXiv:2606.15830. This establishes
paper context, not a literal mapping from the selected raw value to a printed
paper cell. The study therefore uses `PAPER_CONTEXT_ONLY`.

## Algorithm semantics

The released implementation wraps complete CMA-ES searches. Within the MSC
run, cyclic nearest-better clustering selects basins, alternate configurations
change restart behavior, the Sobol pre-sample is reused on alternate cycles,
visited basins are excluded, and new CMA-ES restarts are initialized from
accumulated observations. The candidate is therefore not merely an external
parameter sweep or a fixed optimizer selected between runs.

## Frozen source and environment boundary

The official repository commit
`a88841620b2eddd13a1fab85331fcfc8caa1e85f` is MIT. Zenodo's
`source.tar.gz` is frozen independently by MD5 and SHA-256 and has directory
root `src-a888416`. The verifier will compare the required implementation,
runner, requirements, README, and license bytes with immutable Git blobs.

Raw metadata names Python 3.13.5, NumPy 2.3.1, SciPy 1.15.3, cma 4.4.2, and
minionpy 1.5.0. That is useful provenance but not a complete historical Intel
runtime, compiler, BLAS, operating-system, or floating-point lock. A bitwise
source-native claim is therefore disallowed.

## Raw stop-semantic conflict

The selected run records a nominal budget of 3,000,000, but
`nfev_total=2,893,419`. The paper/README description that refinement spends
the remaining budget is not literally true for this raw run under the
released stop behavior. The artifact endpoint remains valid evidence of what
was recorded; the verifier must preserve the discrepancy and must not rewrite
it as budget exhaustion.
