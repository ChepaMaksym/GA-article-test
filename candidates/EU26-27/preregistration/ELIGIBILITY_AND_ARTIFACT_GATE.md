# Eligibility and artifact gate - EU26-27

Date frozen: 2026-08-20

## Source identity

- publication DOI: `10.1145/3638529.3654073`;
- open preprint: `arXiv:2303.04611`;
- dataset DOI: `10.5281/zenodo.7880836`;
- target artifact record ID: `7880836`;
- base branch: `research/EU26-07-reset-jump-verification`;
- base commit: `e981c13bc4763b26f2e00da9c30047fc38eb9a29`.

No source or result byte from PR #19 is admissible evidence.

## Hard eligibility facts already established

- qualifying EU affiliation: Leiden University, Netherlands;
- publication year: 2024 version of record;
- binary decision dimension: `n=100`;
- synthetic, deterministic benchmark definitions: OneMinMax, LOTZ and COCZ;
- in-run adaptive mutation formulas and pseudocode are printed;
- reported experiment count: 100 independent runs;
- paper declares a Zenodo data record.

## Artifact-first stopping rule

The audit workflow downloads record metadata and all open files, verifies
record checksums, rejects unsafe archives, and inventories source/result
members. The decision is fail-closed.

`PASS_ARTIFACT_GATE` requires:

```text
record id == 7880836
DOI matches the frozen DOI
at least one downloaded file
every declared MD5 checksum matches
no unsafe archive member
raw-result candidate members exist
source-code candidate members exist OR an exact author source revision is found
```

Passing this gate is not OLD reproduction. It only authorizes source and
result-schema analysis.

## Outcome-blind OLD-profile selection

The final profile is selected before reading its numerical values. The
selection order is:

1. an exact author-labeled `n=100`, `lambda=10`, 100-run AGSEMO cell on
   OneMinMax, if source and raw rows are complete;
2. otherwise the first complete self-adaptive GSEMO cell in this fixed order:
   two-rate, log-normal, variance-controlled; problem order OneMinMax, LOTZ,
   COCZ; offspring size `lambda=10`;
3. if neither condition is met, reject EU26-27.

The selected cell must expose a recomputable endpoint such as median or mean
function evaluations to complete the full Pareto front. Its literal row count,
aggregation, tolerance and independent seed ledger are frozen in a second
preregistration commit before any OLD implementation campaign.

## OLD gates

After the second freeze:

- source transition and fixed-random-tape tests;
- benchmark objective micro-oracles;
- exact population dominance/update semantics;
- result-schema replay against the retained raw rows;
- independent clean-room OLD campaign;
- deterministic same-seed replay;
- 1/2/4 worker equality;
- Linux/macOS/Windows portability;
- preregistered numerical endpoint acceptance.

HYBRID is prohibited until all OLD gates pass.

## Professor-review requirements

Before a positive claim, an independent audit must challenge:

- experimental-unit equivalence;
- hidden or unequal computational work;
- post-hoc endpoint/tolerance selection;
- seed and RNG provenance;
- cache and evaluation accounting;
- multiple-comparison inflation;
- negative and mutation controls;
- CI artifact binding;
- claim language and generalization limits.
