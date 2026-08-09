# EU26-13 — authenticated repelling-restart artifact replay

Paper: de Nobel et al., *Avoiding Redundant Restarts in Multimodal Global
Optimization*, PPSN 2024, DOI
[`10.1007/978-3-031-70068-2_17`](https://doi.org/10.1007/978-3-031-70068-2_17).

Status: **`TARGETED_ARTIFACT_REPLAY_ONLY`**

Paper mapping: **`PAPER_CONTEXT_ONLY`**

This bounded study authenticates one raw result from the paper-cited Zenodo
artifact without downloading the 17.6-GB outer archive. The frozen target is
the first run of the `D=20` BBOB Sphere scenario in the nested
`CMA-ES-BIPOP-repelling-c1000.0-elitist.zip` archive. The raw JSON reports
2,173 evaluations and best objective `7.379046076174201e-09`, first reached at
evaluation 2,173, with a 20-coordinate best point.

The selected BIPOP/elitist artifact is additional repository evidence, not a
literal numeric value or the main default-restart result printed in the paper.
The candidate can therefore verify only the immutable artifact endpoint and
source-grounded controls. It cannot establish `PASS_FULL` or an exact
source-native reproduction.

The static code archive is complete enough to audit the C++ CMA-ES, Eigen,
repelling, restart, seed, and experiment-driver semantics. It is frozen by its
Zenodo bytes and member hashes, not by a public Git commit. Its dependency
specification contains lower bounds only and compilation uses `-march=native`.
Consequently source-native execution is preregistered as
`BLOCKED_UNPINNED_TOOLCHAIN_DEPS`.

See `preregistration/eligibility_audit.md` and
`preregistration/verification_contract.md`. Execution commands are added only
by a later implementation commit.
