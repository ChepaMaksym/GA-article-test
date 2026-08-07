# Source audit notes — USA26-04

Candidate source: Andrew Ni and Lee Spector, “Effective Adaptive Mutation
Rates for Program Synthesis,” GECCO 2024, DOI
[`10.1145/3638529.3654135`](https://doi.org/10.1145/3638529.3654135),
[arXiv:2406.15976v1](https://arxiv.org/abs/2406.15976v1).

Audit result: **the analytic objectives and local controller equations support
a clean-room formula/ambiguity study; the published result is not
reproducible from the available record**.

The official NSF-PAR full text, arXiv v1 PDF/source, and exact byte identities
are in `sources.csv`. The NSF PDF carries an ACM permission notice rather than
an open source-code license. The arXiv files are available under arXiv's
nonexclusive distribution terms. No paper source is copied into this
repository.

## Code search and revision facts

The article states that it uses Propeller but gives no repository URL, commit,
tag, archive checksum, or environment lock for the reported experiments. The
author-named fork `andrewni2002/propeller` was audited at commit
`19cd3291bdc85cc51ad8ae2d442726e5e141841e` (tree
`9d4a59e74f8ac1987323ef5ca87dea00ee5eff39`). It has a dual-license notice:
EPL-2.0 or GPL-2.0-or-later with the Classpath exception.

The closest upstream Propeller revision preceding the arXiv submission was
identified for comparison as commit
`847341e4d8dd632b9aef961cfdc170ebd23b8bd8` (tree
`2054bcbb16bdcac6774fcdc9b87b2f668d8c2214`). That temporal relationship is an
audit inference, not an article-pinned revision. The author fork differs from
that upstream tree by one `_shove` correction in
`src/propeller/push/instructions/polymorphic.cljc`; neither tree contains the
paper's bandit/tile controller, function-minimization driver, seed ledger, raw
runs, or Table 1 endpoint artifact. The fork therefore corroborates the G9
absence; it cannot fill it.

No upstream code was copied. All candidate kernels must be independently
written from the archived article equations.

## Source-supported numeric facts

Appendix A defines six unconstrained analytic objectives, dimension 100, and
the initialization SDs shown in the preregistration. Section 4.1 specifies a
population of `100 + 1 elite`, truncation size 10, 1000 generations (100 for
Linear), and averages over 50 runs. Table 1 reports:

| Problem | Bandit | GESMR | SAMR | LAMR-100 |
|---|---:|---:|---:|---:|
| Ackley | 10.1 | 15.8 | 14.8 | 2.0 |
| Griewank | 4.69e-3 | 4.95e-3 | 5.24e-3 | 1.02e4 |
| Rastrigin | 3686 | 4505 | 4772 | 815 |
| Rosenbrock | 105 | 102 | 102 | 98 |
| Sphere | 5.56e-8 | 6.86e-11 | 4.52e-10 | 2.74e-4 |
| Linear | -2.91e46 | -1.12e17 | -2.10e21 | -1949 |

These are rounded descriptive means without raw endpoints or numerical
confidence intervals. Only the Rastrigin/Bandit cell is primary, and no value
is an executable acceptance target.

Appendix D specifies five bandits, 20 tile codings per bandit, history length
100, `gamma ~ 10^U[-4,-3]`, momentum 0.9, epsilon annealed linearly from 1 to
0.01 over five generations, function-minimization sampling noise 7, log-sigma
range `[-100,100]`, base width 0.03, widths uniformly drawn from
`{0.18,0.21,0.24,0.27,0.30,0.33,0.36,0.39}`, and offsets uniformly drawn from
`{0,0.03,0.06,0.09,0.12,0.15}`.

## Why G5 and G9 remain blocked

The paper contains mutually incompatible reward directions and transformation
instructions, an off-by-one/divisor problem in Eq. (2), an unresolved upper
tile boundary, and no initialization/tie/RNG specification. It does not
provide the continuous-vector mutation transition or full experiment driver.
The exact omissions are frozen in
`preregistration/formula_and_ambiguity_contract.md` and machine-readable in
`config/protocol.json`.

There are no paper-specific seeds, raw runs, exact endpoint precision, numeric
bootstrap intervals, dependency lock, or executable result revision. Therefore
neither a source-native replay nor an independent full stochastic replay is
admissible. Python and MATLAB/Octave can independently validate the formulas
and exhibit the ambiguities, but their agreement cannot promote the study
beyond `conditional_noneligible`.
