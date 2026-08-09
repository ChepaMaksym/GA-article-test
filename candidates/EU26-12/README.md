# EU26-12 — range-authenticated Modular DE artifact replay

Paper: Vermetten et al., *Modular Differential Evolution*, GECCO 2023,
DOI [`10.1145/3583131.3590417`](https://doi.org/10.1145/3583131.3590417).

Status: **`TARGETED_ARTIFACT_REPLAY_ONLY`**

Paper mapping: **`PAPER_EXPERIMENT_ARTIFACT_MAPPING`**

This bounded study verifies the lexicographically first eligible `D=20`
L-SHADE run in the paper-cited Zenodo artifact: BBOB F1 Sphere, instance 0,
seed 0. The frozen JSON result reports 50,002 evaluations and best objective
`1.698652750709869e-14`, first reached at evaluation 45,886.

The 4.8-GB raw archive is never vendored or downloaded in full. Candidate code
authenticates immutable Zenodo metadata, ZIP64 tail and directory structure,
the selected local headers and deflate streams, CRC32, exact member SHA-256,
strict JSON shape, seed ordering, and the frozen numeric pointer. It also
authenticates the small static code archive and runner.

Independent Python and MATLAB/Octave controls cover the released SHADE memory
updates, parameter transforms, replacement equality rule, ties-even population
reduction, and the 50,000-to-50,002 evaluation overshoot.

## Claim boundary

Allowed evidence labels are bounded to authenticated metadata, code, range
members, artifact endpoint, controls, cross-language fixtures, and an optional
modern-environment source-native endpoint diagnostic.

`PASS_FULL`, `PASS_LITERAL_PAPER_ENDPOINT`, claims that the exact historical
dependency environment is known, and claims that the full raw-archive MD5 was
recomputed are forbidden.

See `preregistration/eligibility_audit.md` and
`preregistration/verification_contract.md` for the frozen gates. Execution
commands are added only by the post-freeze implementation commit.
