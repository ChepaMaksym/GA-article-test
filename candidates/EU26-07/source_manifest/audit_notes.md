# Source audit notes

The final paper explicitly links the author repository as the location of the
complete implementation and results. Repository README lines 1-2 identify the
paper; lines 17-19 identify `Results.ods`, `Raw/` and `processed-results/` as
the result artifacts.

The repository HEAD is a 2021-01-05 commit, roughly 23 months before the
journal issue date. It has no release or tag. The commit, tree and file hashes
are therefore all frozen independently. This is an authenticated author-linked
artifact, but not an archival or post-publication release.

The artifact is GPL-3.0. No GPL source or raw dataset is vendored here. The
candidate contains an independent compatibility implementation and discloses
the source-specific behavioral observations it mirrors. This is a scientific
provenance boundary, not a legal originality conclusion. The source adapter
loads an external checkout only after verifying its hashes.

## Paper/source differences retained as evidence

1. Printed Algorithm 3 mutates `x` before comparing strict success. The source
   and explanatory text require comparison with the old parent.
2. Paper half-up rounding differs from Python ties-to-even at exact `.5`.
3. Paper final selection has one best mutant; source retains all mutants.
4. Source skips all offspring work when the shared mutation strength is zero.
5. The published Jump class applies additional distribution-preserving local-
   optimum shortcuts that alter RNG consumption and exact seeded trajectories.
6. Logical evaluation counts always add the complete `2*m` batch, including
   skipped work; the initial parent is omitted.
7. CLI metadata calls 20 the initial offspring population, but constructor code
   forces `lambda_0=1` and interprets 20 as `lambda_max`.
8. The generic source accepts crossover coefficients other than one; the paper
   fixture is restricted to coefficient one and `c=1/lambda`.
9. The driver tries to write into a missing `Python-code/results/` directory.
   The adapter invokes the algorithm class directly and does not call this
   incidental broken output path.

These differences are not normalized away. Each is either an adversarial test
or an explicit claim blocker. They permanently forbid a `PASS_FULL` claim;
the strongest allowed outcomes are profile-specific formula and artifact
replay statuses.
