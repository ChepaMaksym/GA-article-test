# Source audit notes — USA26-01

Candidate source: Akarsh Kumar, Bo Liu, Risto Miikkulainen, and Peter
Stone, “Effective Mutation Rate Adaptation through Group Elite
Selection,” GECCO 2022, DOI
[`10.1145/3512290.3528706`](https://doi.org/10.1145/3512290.3528706),
[arXiv:2204.04817](https://arxiv.org/abs/2204.04817).

Audit status: **formula source is sufficient for a clean-room kernel;
published-result reproduction is blocked/inconclusive**.

## Direct-optimization eligibility

The paper minimizes explicit analytic functions over
\(x\in\mathbb{R}^d\). The clean-room scope contains only Sphere, Ackley,
Griewank, Rastrigin, and Rosenbrock. It contains no forward model,
observed-data fitting, hidden-state reconstruction, parameter inversion,
or system identification.

## Formula interpretation

- Eq. (2): \(x'=x+\sigma\epsilon\),
  \(\epsilon\sim\mathcal N(0,I)\).
- Eq. (3): one unchanged solution elite; the remaining \(N\) parents are
  sampled with replacement from the best \(m=\eta_xN\) solutions.
- Eqs. (4)–(5): the \(N\) children are partitioned into contiguous groups
  \((k-1)N/K+1,\ldots,kN/K\); MR worth is that group’s minimum child-minus-
  parent objective change.
- Eq. (6): one unchanged MR elite; the remaining \(K-1\) MR parents are
  sampled with replacement from the best \(l=\eta_\sigma K\) MRs.
- Eq. (7) and the preceding definition:
  \(\sigma'=\sigma\tau^u\), \(u\sim\mathcal U(-1,1)\), with the elite MR
  unchanged.

The floor expression printed in Eq. (4) yields group index 0 for early
one-based children and index \(K\) at \(i=N\), while the paper defines MRs
as \(1,\ldots,K\). The explicit group intervals in the prose and Eq. (5)
are unambiguous and agree with the author implementation’s zero-based
integer grouping. Both clean-room environments therefore use those
intervals and fail if \(K\) does not divide \(N\).

The numerical defaults \(K=10\), \(\eta_x=0.5\), and
\(\eta_\sigma=0.5\) are supported by the audited author artifact:
`paper_meta.py` configures `n_mutpop=10`, and
`optim.run_evolution_ours` defaults both truncation fractions to `0.5`.
They are therefore artifact-backed defaults, not silently attributed to
otherwise ambiguous camera-ready prose.

## Source conflicts that block a published-result gate

| Topic | Camera-ready/arXiv source | Audited author artifact | Frozen scaffold decision |
|---|---|---|---|
| Dimensions | §4.2 says \(\{2,10,100,1000\}\); Appendix A/Table 1 use \(\{2,30,100,1000\}\) | `results_main.py` uses `[1000,100,30,2]` | Prospective matrix uses 30 and records the conflict |
| Seeds | §4.2 says five seeds | Table 1 caption and `results_main.py` use 40 (`0..39`) | Freeze seed IDs `0..39` for every configuration |
| Generation budgets | Appendix A maps dimensions to \(\{100,300,1000,2500\}\) | audited `results_main.py` hard-codes 1000 for every dimension | Prospective matrix keeps Appendix A budgets; no published claim |
| Table 1, GESMR, \(d=100\), std=10 | Camera-ready Ackley/Griewank/Rastrigin/Rosenbrock/Sphere: `3.6 / 0.0 / 1149.7 / 943.1 / 0.0` | tracked preliminary `results/table_mean.tex`: `5.0 / 0.4 / 1345.5 / 1.2e4 / 18.7` | Exact camera-ready result artifact/revision is missing; gate is `BLOCKED_INCONCLUSIVE` |

The notebook's `get_latex_data_str(..., stat='mean')` selects generation
500 for non-Linear functions. Consequently, the tracked
`results/table_mean.tex` values are preliminary 500-generation values,
not a like-for-like failed 1000-generation rerun. Their difference from
the camera-ready table is evidence that audited commit `2bcb6e1` does not
contain the exact camera-ready result artifact/revision; it is **not** a
numerical reproduction failure.

The author artifact also uses PyTorch float32, Torch Gaussian/uniform RNG,
and legacy NumPy parent sampling. The clean-room Python reference uses
float64/PCG64/stable sorting; MATLAB/Octave uses double/twister/stable
original-index tie breaks. Therefore native stochastic trajectories are
not expected to be bit-identical. The shared fixed-random-tape microtest
checks formula and update-order equivalence without claiming RNG-stream
equivalence.

No `LICENSE`, `COPYING`, or `NOTICE` file was found at the audited author
commit. No upstream source was copied into this candidate; the kernels
were written from the equations and pseudocode. The upstream artifact is
used only as audit evidence.
