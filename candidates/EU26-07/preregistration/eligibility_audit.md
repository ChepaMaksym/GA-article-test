# EU26-07 eligibility audit

Freeze date: 2026-08-07 (Europe/Kyiv)

Candidate: Mario Alejandro Hevia Fajardo and Dirk Sudholt,
*Theoretical and Empirical Analysis of Parameter Control Mechanisms in the
(1 + (lambda, lambda)) Genetic Algorithm*, ACM Transactions on Evolutionary
Learning and Optimization 2(4), Article 13, issue date December 2022,
DOI `10.1145/3564755`.

Decision: **ELIGIBLE FOR A TARGETED REPRODUCTION**.

## Hard-gate audit

| Gate | Evidence | Decision |
|---|---|---|
| Publication date | Final journal article, December 2022 | PASS |
| US/EU provenance | University of Sheffield (UK) and University of Passau (Germany) affiliations | PASS |
| Direct optimization | Maximizes the pseudo-Boolean `Jump_k` function directly | PASS |
| More than 10 decision variables | Primary fixture is a 20-bit string | PASS |
| Genuine within-run control | Real-valued `lambda` changes after every generation; `p=lambda/n` and `c=1/lambda` therefore change with it | PASS |
| Complete core pipeline | Initialization, shared binomial mutation strength, mutation offspring, crossover offspring, selection, update, reset and stopping rule are available | PASS, with profiles below |
| Literal numerical target | Author-processed and raw 500-run results give mean `108964.48`, median `84730`, Q1 `32787`, Q3 `150829` | PASS |
| Stochastic provenance | Base seed `816114841`; run `r` seeds both NumPy and Python RNGs with `base_seed+r`, for `r=1..500` | PASS |
| Author implementation/data | Final paper links the author repository containing GPL-3.0 code, raw results and processed results | PASS |

The selected problem is `Jump_4` with `n=20`. Its optimum is the all-one
string with `f*=24`; its local-optimum plateau has 16 one-bits and fitness 20.
This fixture exercises the reset mechanism instead of merely carrying it as
dead code.

## Mandatory profile split

The paper and the author artifact are not one executable specification. The
verification therefore freezes three non-interchangeable profiles:

1. `paper_algorithm3`: Algorithm 3 with half-up nearest-integer rounding,
   the selected best mutant plus crossover children in the final pool, and
   strict success computed against the pre-update parent.
2. `artifact_generic`: the generic author class, Python ties-to-even rounding,
   all mutation offspring retained in the final pool, and the source's
   zero-mutation shortcut.
3. `artifact_jump_optimized`: the problem-specific class that generated the
   published raw fixture. It additionally skips provably futile work at the
   Jump local optimum while charging the full logical `2*round(lambda)`
   evaluations.

Only profile 3 may be compared row-for-row with the published raw file.
Profile 1 is the independent scientific implementation. Profile 2 is a
diagnostic bridge. Passing one profile never authorizes a claim about another.

## Known blockers to `PASS_FULL`

- Algorithm 3 updates `x` before testing strict success in the printed order;
  the surrounding text and source require comparison to the old parent.
- The paper's final pool contains one selected mutant; source retains every
  mutant, changing tie multiplicities and sometimes the selected trajectory.
- Paper rounding sends `.5` upward; Python `round` uses ties-to-even.
- Raw metadata labels CLI `-l 20` as an initial population size, while source
  forcibly initializes `lambda=1` and uses 20 only as the cap.
- The raw fixture uses a Jump-specific shortcut implementation, not the
  generic Algorithm 3 class.
- Evaluation counts are logical: skipped objective calls are still charged,
  and the initial-parent call is not charged.
- The source release has no tag, archival DOI or dependency lock and predates
  the final paper by about 23 months.

Consequently this candidate may earn
`PASS_TARGET_ARTIFACT_REPLAY` and `PASS_PAPER_FORMULA_PROFILE`, but not an
unqualified `PASS_FULL` for the whole paper.

## Outcome-exposure disclosure

Before this freeze, two author-code diagnostic runs were inspected and matched
the first two raw rows (`84504` and `121590` evaluations). They were not used
to choose formulas, tolerances or profiles. The full 500-row replay and the
clean-room comparison had not been run at freeze time.
