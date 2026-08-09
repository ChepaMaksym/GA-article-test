# EU26-13 source and provenance audit

Audit date: 2026-08-09. Candidate-local implementation and source-native
execution had not begun when this record was frozen.

## Paper-to-artifact boundary

The manuscript cites Zenodo DOI `10.5281/zenodo.10997200` as reproducibility
files and additional figures. It specifies BBOB dimensions including 20 and 50
independent runs on ten instances. Section 5 describes default-restart results
in the paper and explicitly points to IPOP/BIPOP results in the repository.
The selected BIPOP, elitist, `c=1000` raw run is therefore useful paper context
but not a literal or primary paper numeric endpoint.

## Source identity and conflict

The complete 24-MB Zenodo code snapshot contains Modular CMA-ES source, the
repelling and BIPOP implementation, experiment scripts, Eigen 3.4.0, a compiled
CPython 3.11 Linux extension, and an MIT license. The code snapshot differs
from public Git history; its identity is only its immutable Zenodo bytes and
member hashes. No Git commit, tag, or tree is asserted.

The driver uses ten instances, 50 runs per instance, and
`set_seed(42 * run)`. The C++ helper seeds `std::mt19937` and `srand`. It does
not freeze all standard-library distribution or compiler semantics.

The dependency file gives lower bounds only, and `setup.py` installs
unversioned runtime dependencies. Linux compilation uses `-O3`,
`-fno-math-errno`, and `-march=native`. The raw JSON identifies IOH 0.3.15,
but no complete historical environment lock exists. For that reason,
source-native replay is blocked rather than attempted under contract v1.

## Range-only evidence

The verifier is permitted to fetch Zenodo JSON, the 24-MB code archive, the
last 65,536 bytes and 6,866-byte central directory of the outer ZIP64 file,
the last 65,536 bytes and 51,011-byte central directory of the stored nested
ZIP, small local headers, and the 422,209-byte compressed target member. It may
not download either the 17.6-GB outer archive or the complete 385-MB nested
ZIP.

The outer archive's MD5 and the stored nested member's CRC32 are metadata-only
under this range policy. The target member's compressed and raw SHA-256, raw
size, and CRC32 are recomputed.

## Audited semantics

The selected configuration is full CMA-ES with covariance adaptation, CSA,
stable fitness sorting, elitism, saturating bound correction, BIPOP restarts,
and repelling tabu regions. BIPOP assigns budgets to large and small regimes,
doubles the large population after a large run, samples an even small
population, and samples a smaller initial sigma in the small regime.

On restart, the implementation finalizes the current center, tests it against
the tabu archive with ten Hill-Valley evaluations per comparison, increments
the visit count or inserts a point, then recomputes rejection radii. Candidate
samples are rejected using a covariance-scaled Mahalanobis distance. The
effective rejection radius shrinks by `0.99^(attempts/D)` after repeated
rejections. These formulas are controlled independently, but the complete
stochastic trajectory is not replayed.
