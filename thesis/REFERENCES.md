# Core references — verified working bibliography

Це робочий бібліографічний список. Перед фінальним оформленням стиль має бути приведений до вимог університету, але назви, автори та DOI/identifiers нижче повинні зберігатися без вигадування metadata.

1. **Ye, F.; Neumann, F.; de Nobel, J.; Neumann, A.; Bäck, T.** *Towards Self-adaptive Mutation in Evolutionary Multi-Objective Algorithms.* arXiv:2303.04611, 2023. Source paper for the exact-reproduced GSEMO/TwoRate experimental line.

2. **Doerr, B.; El Hadri, O.; Pinard, A.** *The (1+(lambda,lambda)) Global SEMO Algorithm.* Proceedings of the Genetic and Evolutionary Computation Conference (GECCO 2022), 2022. DOI: **10.1145/3512290.3528868**. arXiv:2210.03618. Key prior art for one-fifth-inspired dynamic parameter control in discrete multi-objective optimization.

3. **Bassin, A. O.; Buzdalov, M.** *The 1/5-th Rule with Rollbacks: On Self-Adjustment of the Population Size in the (1+(lambda,lambda)) GA.* GECCO '19 Companion, Association for Computing Machinery, 2019, pp. 277–278. DOI: **10.1145/3319619.3322067**.

4. **Bassin, A. O.; Buzdalov, M. V.; Shalyto, A. A.** *The “One-Fifth Rule” with Rollbacks for Self-Adjustment of the Population Size in the (1+(lambda,lambda)) Genetic Algorithm.* Automatic Control and Computer Sciences, 55(7), 2021, pp. 885–902. DOI: **10.3103/S0146411621070208**. A related open journal version appeared in Modeling and Analysis of Information Systems 27(4), pp. 488–508, DOI **10.18255/1818-1015-2020-4-488-508**.

5. **Eiben, A. E.; Hinterding, R.; Michalewicz, Z.** *Parameter Control in Evolutionary Algorithms.* IEEE Transactions on Evolutionary Computation, 3(2), 1999, pp. 124–141. DOI: **10.1109/4235.771166**. Canonical terminology/taxonomy reference separating parameter tuning from parameter control and distinguishing deterministic, adaptive and self-adaptive mechanisms.

6. **Eiben, A. E.; Michalewicz, Z.; Schoenauer, M.; Smith, J. E.** *Parameter Control in Evolutionary Algorithms.* In: Lobo, F. G.; Lima, C. F.; Michalewicz, Z. (eds.), *Parameter Setting in Evolutionary Algorithms*, Studies in Computational Intelligence 54, Springer, 2007, pp. 19–46. DOI: **10.1007/978-3-540-69432-8_2**.

7. **López-Ibáñez, M.; Branke, J.; Paquete, L.** *Reproducibility in Evolutionary Computation.* ACM Transactions on Evolutionary Learning and Optimization, 2021. DOI: **10.1145/3466624**. Core methodology reference for versioned artifacts, precise seeds, raw measurements, executable analysis/presentation code, and reproducible parameter-setting procedures.

8. **de Nobel, J.; Ye, F.; Vermetten, D.; Wang, H.; Doerr, C.; Bäck, T.** *IOHexperimenter: Benchmarking Platform for Iterative Optimization Heuristics.* arXiv:2111.04077, 2021. Describes the experimentation/logging platform used by the source implementation and granular optimization-process logging.

9. **Doerr, C.; Wang, H.; Ye, F.; van Rijn, S.; Bäck, T.** *IOHprofiler: A Benchmarking and Profiling Tool for Iterative Optimization Heuristics.* arXiv:1810.05281, 2018. Describes fixed-target/fixed-budget performance analysis and parameter tracking for iterative optimization heuristics.

10. **García, S.; Molina, D.; Lozano, M.; Herrera, F.** *A General Framework for Statistical Performance Comparison of Evolutionary Computation Algorithms.* Information Sciences, 178(14), 2008, pp. 2870–2879. DOI: **10.1016/j.ins.2008.03.007**. Relevant background for distribution-free comparison of stochastic evolutionary algorithms.

11. **Hevia Fajardo, M. A.; Sudholt, D.** *Theoretical and Empirical Analysis of Parameter Control Mechanisms in the (1+(lambda,lambda)) Genetic Algorithm.* ACM Transactions on Evolutionary Learning and Optimization, 2(4), Article 13, 2023 (issue date December 2022), 39 pages. DOI: **10.1145/3564755**. Direct source for the reset/capping motivation used in PR #24 and PR #26.

12. **Altarabichi, M. G.; Nowaczyk, S.; Pashami, S.; Sheikholharam Mashhadi, P.** *Fast Genetic Algorithm for feature selection — A qualitative approximation approach.* Expert Systems with Applications, 211, Article 118528, 2023. DOI: **10.1016/j.eswa.2022.118528**. Direct CHC-QX research source for the companion applied PR #19.

## Terminology policy for the thesis

The Ye et al. source paper uses the phrase “self-adaptive mutation”. Preserve that wording when describing the source paper. For the thesis' own added `lambda` mechanisms, use the stricter Eiben terminology: because `lambda` is updated from an explicit observed success signal rather than encoded and inherited as part of the evolving representation, describe it primarily as **adaptive feedback-based parameter control** or **self-adjusting offspring-count control**, not silently as classical self-adaptation.

## Reference-to-claim boundary

### Ye et al.
May support:

- the study of self-adaptive mutation in GSEMO;
- OneMinMax, LOTZ and COCZ as source test problems;
- multi-objective indicators such as hypervolume/IGD as adaptation signals;
- empirical speedups of the authors' adaptive mutation variants in their tested settings.

Does **not** by itself support:

- our exact reproduction claim, which requires PR #23 raw evidence;
- superiority of any added `lambda` controller;
- universal superiority on arbitrary multi-objective problems.

### Doerr, El Hadri, Pinard
May support:

- prior existence of `(1+(lambda,lambda))` Global SEMO;
- one-fifth-inspired dynamic parameter setting in discrete multi-objective optimization;
- their theoretical `O(n^2)` OneMinMax result for the studied dynamic variant.

Consequence:

- do not claim the first adaptive-`lambda` MOEA;
- their performance result is about their algorithm and cannot be copied as a prediction of our TwoRate transfer without a new experiment.

### Hevia Fajardo & Sudholt
May support:

- the source observation that self-adjusting `lambda` can grow uncontrollably on `Jump_k`;
- the source result that smaller caps can be beneficial in that setting;
- reset-to-1 as a source mechanism for cycling through the parameter space.

May **not** support:

- a claim that reset or cap 20 must improve TwoRate GSEMO;
- calling PR #24 or #26 a numerical reproduction of their paper;
- transferring a `Jump_k` performance guarantee to OneMinMax GSEMO without independent evidence.

Correct use in the thesis: the paper provides the **source-grounded transfer prediction**, while PR #24/#26 determine whether that prediction survives the new setting.

### Bassin / Buzdalov
May support:

- one-fifth population-size adaptation can degrade performance when its assumptions are poor;
- overly rapid `lambda` growth can be harmful;
- rollback was proposed to reduce that negative impact in the source setting.

Does **not** imply:

- rollback must help TwoRate GSEMO;
- PR #25 is a reproduction of the rollback paper;
- a structurally faithful rollback transfer guarantees a favorable effect.

### Altarabichi et al.
May support:

- the CHC-QX qualitative-approximation research line;
- the paper's reported faster convergence relative to CHC;
- the reported higher-accuracy feature subsets, particularly on large datasets.

Does **not** by itself support:

- literal equivalence between the printed paper and the public implementation used in PR #19;
- our source-compatible 55.499% logical-NFE result;
- our corrected official-UCI weighted-balanced-accuracy result.

Correct use: compare **direction and scope** of our source-compatible result with the paper, while preserving `PAPER_SOURCE_DIVERGENCES.md` and reporting the corrected external-validity failure separately.

### Eiben et al.
May support:

- the distinction between parameter tuning and online parameter control;
- deterministic/adaptive/self-adaptive taxonomy;
- treating mutation rate and population size as meaningful EA strategy parameters.

Does **not** imply that a taxonomy label makes an algorithm empirically better or that our feedback law is optimal.

### EC reproducibility literature
May support the design choice to retain:

- exact source/version identities;
- random seed ledgers;
- raw measurements rather than summaries only;
- preprocessing/algorithm/analysis/presentation code;
- reproducible parameter-development procedures.

It does **not** establish correctness of our numerical results by itself; those require repository evidence and frozen gates.

### IOHprofiler / IOHexperimenter
May support:

- granular logging of iterative optimization;
- fixed-target/fixed-budget analysis and adaptive-parameter tracking;
- provenance of experimentation infrastructure used by the source implementation.

## Repository/source references used as experimental objects

- FurongYe/GSEMO exact revision: `fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380`.
- IOHprofiler/IOHexperimenter exact revision: `f223c682dff0749067d00b870f83ad754f7d96f5`.
- The authenticated raw result member and exact identity are recorded in PR #23 evidence.

## Additional literature still to add before final thesis

- canonical source for the classic GSEMO definition/runtime baseline;
- primary hypervolume-indicator reference;
- optional recent review of statistical tests in evolutionary/swarm computation.

These entries must be verified before citation. Placeholder metadata must not be invented.
