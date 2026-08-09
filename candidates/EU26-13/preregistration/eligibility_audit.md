# EU26-13 eligibility audit

Audit date: 2026-08-09. This audit and its machine-readable contract were
committed before candidate-local verifier implementation.

## Candidate and positive gates

- Jacob de Nobel, Diederick Vermetten, Anna V. Kononova, Ofer M. Shir, and
  Thomas Bäck, *Avoiding Redundant Restarts in Multimodal Global Optimization*,
  PPSN 2024, DOI `10.1007/978-3-031-70068-2_17`.
- Qualifying European affiliation: de Nobel, Vermetten, Kononova, and Bäck are
  affiliated with LIACS, Leiden University, the Netherlands.
- Direct optimization: the experiments directly minimize continuous BBOB and
  CEC 2013 functions. This is not inversion, inverse modelling, parameter
  estimation, or surrogate-only optimization.
- Dimension: the BBOB experiment includes `D=20`. The selected raw scenario is
  exactly `D=20`, and its best point has 20 coordinates.
- Full EA: the released algorithm is a complete population-based CMA-ES with
  Gaussian mutation, selection, recombination, covariance adaptation,
  cumulative step-size adaptation, bound correction, elitism, restart
  criteria, and BIPOP restart control.
- Within-run control: covariance and step size are updated every generation.
  On restart, BIPOP changes population size and initial step size. The
  repelling extension updates a tabu archive and rejection radii and shrinks a
  radius after rejected samples.
- Legal sources: the arXiv manuscript is publicly available. Zenodo record
  `10.5281/zenodo.10997200` is CC-BY-4.0. The frozen source archive contains a
  complete MIT license and bundled Eigen source.
- Frozen evidence: Zenodo fixes the code archive and 17.6-GB result archive by
  size and MD5. A ZIP64 directory plus one nested ZIP directory and raw JSON
  member can be authenticated by bounded HTTP ranges.
- Raw endpoint and seeds: the selected `D=20` scenario contains 500 runs,
  ordered as 50 runs for each instance 1 through 10. The released driver loops
  instances then runs and applies `set_seed(42 * run)`; the selected first run
  is instance 1, run 0, seed 0.

These facts support a bounded artifact verification, but not a full paper or
source-native reproduction.

## Admission decision

Admission: **`ADMITTED_TARGETED_ARTIFACT`**

Status: **`TARGETED_ARTIFACT_REPLAY_ONLY`**

Paper mapping: **`PAPER_CONTEXT_ONLY`**

The paper cites the Zenodo repository for reproducibility and additional
figures. However, the selected exact JSON value is not printed in the paper,
and Section 5 describes default-restart results in the paper while pointing to
IPOP/BIPOP results as additional repository material. The selected BIPOP,
elitist, `c=1000` run must therefore remain artifact-only context.

## Mandatory blockers and conflicts

1. The selected objective is not a literal paper table or figure value.
2. The code archive is a frozen Zenodo source snapshot, but it differs from
   public repository history. No Git commit or tag may be attributed to it.
3. `requirements.txt` contains only `ioh>=0.3.12`, `numpy>=1.18.5`,
   `pybind11>=2.6.0`, and `scipy>=1.9.1`; `setup.py` relaxes these further to
   unversioned runtime requirements.
4. Exact Python, NumPy, SciPy, pybind11, compiler, libstdc++, CPU, and build
   versions are not frozen. The Linux build uses `-O3 -march=native`.
5. The bundled extension is named for CPython 3.11 and Linux x86-64, but that
   filename does not establish the complete historical toolchain.
6. The JSON reports IOH format version `0.3.15`, while the source requirement
   is only a lower bound. This does not freeze the IOH build that generated the
   result.
7. The seed schedule is explicit, but C++ standard-library distribution and
   Eigen/compiler numerical semantics are not fully portable from the
   available provenance.
8. The 17.6-GB archive MD5 is declared by Zenodo and is not recomputed by a
   range-only verifier.
9. The selected outer member is a stored nested ZIP. The verifier authenticates
   its central-directory identity and the exact target member, not all
   385,093,474 bytes of the nested ZIP and not all 17.6 GB of the outer file.

The source-native gate is therefore fixed to
**`BLOCKED_UNPINNED_TOOLCHAIN_DEPS`**. No candidate-local result may upgrade
it. `PASS_FULL`, literal-paper, exact-historical-environment, full-archive-MD5,
or Git-commit-equivalence claims are forbidden.

## Timing disclosure

Triage inspected the manuscript, immutable Zenodo metadata, code snapshot,
experiment driver, source formulas, outer ZIP64 directory, selected nested ZIP
directory, and first eligible `D=20` raw run before this freeze. The endpoint
was selected by a deterministic identity rule: the named BIPOP repelling
variant, BBOB F1, `D=20`, then the first archived run. No tolerance is chosen
from a replay deviation: member bytes and the objective decimal must match
exactly. No candidate-local verifier or Octave control existed at freeze time.
