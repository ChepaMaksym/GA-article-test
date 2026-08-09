# EU26-14 eligibility audit

Audit date: 2026-08-09. This record was frozen before candidate-local
verifier implementation and before any source-native execution.

## Candidate and bounded eligibility

- Dimitar Nedanovski, Svetoslav Nenov, and Dimitar Pilev,
  *MSC-CMA-ES: Structure-Aware Restarts for CMA-ES via Cyclic Nearest-Better
  Basin Discovery*, arXiv:2606.15830v3, DOI
  `10.48550/arXiv.2606.15830`.
- Qualifying European affiliations: Sofia University St. Kliment Ohridski and
  the University of Chemical Technology and Metallurgy, Bulgaria.
- Direct optimization: the paper and artifact directly minimize CEC objective
  functions. The selected cell is CEC2020 F1 at dimension 15; released cells
  also include dimensions 20 and 30. This is not inversion, parameter fitting,
  or surrogate-only optimization.
- Full evolutionary strategy: every local search is a complete CMA-ES run,
  adapting covariance and step size. MSC changes restart configuration within
  a run, alternates configurations, reuses the Sobol sample, excludes visited
  basins, and initializes restarts from accumulated observations.
- Legal immutable artifacts: the paper names the public MIT repository. Zenodo
  record `21483843`, version `1.0.0`, is immutable and CC-BY-4.0. Its
  `source.tar.gz` maps to repository commit
  `a88841620b2eddd13a1fab85331fcfc8caa1e85f`; its CEC2020 archive contains
  seed-addressable raw result objects.
- Numeric evidence: the lexicographically selected eligible member contains
  51 runs with seeds 0 through 50 and literal run/cycle/improvement values.

These facts admit a bounded artifact replay. They do not establish the
historical floating-point environment or a source-native regeneration of the
51 by 3,000,000-evaluation cell.

## Admission decision

Study status: **`TARGETED_ARTIFACT_REPLAY_ONLY`**

Paper mapping: **`PAPER_CONTEXT_ONLY`**

The selected endpoint is raw paper-associated artifact evidence, not a number
printed literally in the paper. Source-native rerun is deliberately outside
this study.

## Mandatory conflicts and hard stops

1. The paper provides context for this experiment, but the selected detailed
   run endpoint is not a literal paper table cell.
2. The released metadata records Python 3.13.5, NumPy 2.3.1, SciPy 1.15.3,
   cma 4.4.2, and minionpy 1.5.0. Intel/platform details and floating-point
   execution state are not complete enough for bitwise source-native claims.
3. A full source-native cell would require 51 runs at a 3,000,000-evaluation
   budget and is outside the validation scope.
4. The paper/README says that local refinement spends the remaining budget,
   while the selected raw run records `nfev_total=2893419`, below 3,000,000.
   This is a documented paper/raw stop-semantic conflict. No report may claim
   literal budget exhaustion.
5. Python pickle is executable. The verifier may not call `pickle.load`,
   `pickle.loads`, NumPy's pickle loader, or any equivalent general unpickler.
   It must parse the frozen protocol without executing constructors, allow
   only the frozen NumPy symbolic references, and reject every other global,
   extension, persistent reference, reducer, object-construction path, or
   unexpected opcode.
6. The 317,976,046-byte result archive must pass its complete SHA-256 before
   endpoint acceptance. A partial or range-only result cannot pass.
7. The selected member must be located by streaming zstd and tar parsing at
   the frozen uncompressed offset, never by extracting archive paths into the
   repository or trusting a filename alone.

No candidate-local check may clear these limits. `PASS_FULL`, an exact
source-native claim, historical-environment equivalence, a literal paper-cell
claim, and literal budget-exhaustion are forbidden.

## Timing disclosure

Before this freeze, candidate triage inspected the paper metadata, repository
identity/license, Zenodo metadata, author-supplied checksums, archive member
inventory, and the selected raw object's values. The endpoint was selected by
the fixed lexicographic rule `cec2020`, `d15`, `MSC-CMA`, budget 3,000,000,
`f1.pkl`, then run 0. No candidate-local parser, verifier, fixture, tolerance,
or test existed at selection time.
