# EU26-17 amendment 001 — applied dimension and lawful input

Frozen: 2026-08-09, before implementing or running the EU26-17 validators.

This amendment corrects three conservative classifications in the original
eligibility audit. It does not edit that immutable audit and does not change
the decisive gate-8 failure or overall **`HARD_FAIL`** status.

## Corrected scope interpretation

The candidate rule requires the real applied problem to expose at least 11
meaningful domain decision/model parameters separately from the GA controls;
it does not require those domain parameters to be a fixed-length chromosome.
The selected Parkinson's Telemonitoring regression problem has 18 real
biomedical input variables. They are listed individually in the frozen JSON
contract and independently obtained from the loader and authenticated CSV.
They are not OneMax/Sphere/CEC/BBOB coordinates and are not mutation,
crossover, population, or selection settings.

The optimization target is direct supervised regression/model composition:
SupRB directly selects and combines rules to minimize prediction error and
rule count. It does not infer a hidden physical source, state, or parameter
through a forward model.

Therefore this amendment supersedes the original rows as follows:

| Criterion | Original status | Amended status | Evidence |
|---|---:|---:|---|
| Direct-only | unresolved | **pass** | Direct rule-subset composition for supervised regression, not inverse reconstruction. |
| C2 at least 11 meaningful applied parameters | unresolved | **pass** | PT has 18 named biomedical input variables and 5,875 samples in paper Table I, loader, and byte-authenticated data. |
| G7 lawful reproducible inputs | unresolved | **pass** | The primary UCI record declares CC BY 4.0, and its `parkinsons_updrs.data` member is byte-identical to the experiment repository's `parkinson.csv`. |

## Primary input identity

- UCI dataset DOI: [`10.24432/C5ZS3N`](https://doi.org/10.24432/C5ZS3N).
- Primary record:
  `https://archive.ics.uci.edu/dataset/189/parkinsons+telemonitoring`.
- Primary download:
  `https://archive.ics.uci.edu/static/public/189/parkinsons+telemonitoring.zip`.
- Archive member: `parkinsons_updrs.data`.
- Member byte count: `911261`.
- Member SHA-256:
  `f2c7d5025dec4e92e7feae367a5f7ccf58789a10ac6b54bdf15976c599f9dd39`.
- Repository `problems/datasets/data/parkinson.csv` at experiment commit
  `5c7c87...`: the same byte count and SHA-256; byte comparison result `cmp=0`.
- License declared by the UCI primary record: CC BY 4.0.

Later validators may emit `PASS_APPLIED_DIMENSION` and `PASS_LAWFUL_INPUT`
when these identities and the paper/loader facts pass. Neither label is an
optimizer outcome. No result may emit `PASS_FULL`, invent a numeric endpoint,
or weaken `HARD_FAIL_ELIGIBILITY_UNCHANGED`.

## Unchanged blockers

G8 remains a decisive failure because there is no literal unambiguous numeric
SAGA1 result cell in the unchanged paper. Raw `mlruns`, an author-pinned core
revision, and historical release/run provenance also remain absent. Passing
direct-only, C2, and G7 cannot cure those failures.
