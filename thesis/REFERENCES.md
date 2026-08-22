# Core references — verified working bibliography

Це робочий бібліографічний список. Перед фінальним оформленням стиль має бути приведений до вимог університету, але назви, автори та DOI/identifiers нижче повинні зберігатися без вигадування metadata.

1. **Ye, F.; Neumann, F.; de Nobel, J.; Neumann, A.; Bäck, T.** *Towards Self-adaptive Mutation in Evolutionary Multi-Objective Algorithms.* arXiv:2303.04611, 2023. Source paper for the exact-reproduced GSEMO/TwoRate experimental line.

2. **Doerr, B.; El Hadri, O.; Pinard, A.** *The (1+(lambda,lambda)) Global SEMO Algorithm.* Proceedings of the Genetic and Evolutionary Computation Conference (GECCO 2022), 2022. DOI: **10.1145/3512290.3528868**. arXiv:2210.03618. This is key prior art for one-fifth-inspired dynamic parameter control in discrete multi-objective optimization.

3. **Bassin, A. O.; Buzdalov, M.** *The 1/5-th Rule with Rollbacks: On Self-Adjustment of the Population Size in the (1+(lambda,lambda)) GA.* GECCO '19 Companion, Association for Computing Machinery, 2019, pp. 277–278. DOI: **10.1145/3319619.3322067**.

4. **Bassin, A. O.; Buzdalov, M. V.; Shalyto, A. A.** *The “One-Fifth Rule” with Rollbacks for Self-Adjustment of the Population Size in the (1+(lambda,lambda)) Genetic Algorithm.* Automatic Control and Computer Sciences, 55(7), 2021, pp. 885–902. DOI: **10.3103/S0146411621070208**. A related open journal version appeared in Modeling and Analysis of Information Systems 27(4), pp. 488–508, DOI **10.18255/1818-1015-2020-4-488-508**.

5. **Eiben, A. E.; Hinterding, R.; Michalewicz, Z.** *Parameter Control in Evolutionary Algorithms.* IEEE Transactions on Evolutionary Computation, 3(2), 1999, pp. 124–141. DOI: **10.1109/4235.771166**. Canonical terminology/taxonomy reference separating parameter tuning from parameter control and distinguishing deterministic, adaptive and self-adaptive mechanisms.

6. **Eiben, A. E.; Michalewicz, Z.; Schoenauer, M.; Smith, J. E.** *Parameter Control in Evolutionary Algorithms.* In: Lobo, F. G.; Lima, C. F.; Michalewicz, Z. (eds.), *Parameter Setting in Evolutionary Algorithms*, Studies in Computational Intelligence 54, Springer, 2007, pp. 19–46. DOI: **10.1007/978-3-540-69432-8_2**.

7. **López-Ibáñez, M.; Branke, J.; Paquete, L.** *Reproducibility in Evolutionary Computation.* ACM Transactions on Evolutionary Learning and Optimization, 2021. DOI: **10.1145/3466624**. Core methodology reference for versioned artifacts, precise seeds, raw measurements, executable analysis and presentation code, and reproducible parameter-setting procedures.

8. **de Nobel, J.; Ye, F.; Vermetten, D.; Wang, H.; Doerr, C.; Bäck, T.** *IOHexperimenter: Benchmarking Platform for Iterative Optimization Heuristics.* arXiv:2111.04077, 2021. Describes the experimentation/logging platform used by the source implementation and its role in granular optimization-process logging.

9. **Doerr, C.; Wang, H.; Ye, F.; van Rijn, S.; Bäck, T.** *IOHprofiler: A Benchmarking and Profiling Tool for Iterative Optimization Heuristics.* arXiv:1810.05281, 2018. Describes fixed-target/fixed-budget performance analysis and parameter tracking for iterative optimization heuristics.

10. **García, S.; Molina, D.; Lozano, M.; Herrera, F.** *A General Framework for Statistical Performance Comparison of Evolutionary Computation Algorithms.* Information Sciences, 178(14), 2008, pp. 2870–2879. DOI: **10.1016/j.ins.2008.03.007**. Relevant background for bootstrap-based distribution-free comparison of stochastic evolutionary algorithms.

## Terminology policy for the thesis

The source paper uses the phrase “self-adaptive mutation”. The thesis preserves that wording when describing the source paper. For the thesis' own added `lambda` mechanisms, the stricter Eiben taxonomy is used: because `lambda` is updated from an explicit observed success signal rather than encoded and inherited as part of the evolving representation, the new mechanism is described primarily as **adaptive / feedback-based parameter control** or **self-adjusting population-size control**, not silently relabeled as classical self-adaptation.

## Reference-to-claim boundary

### Ye et al.
May support:
- study of self-adaptive mutation in GSEMO;
- classic test problems including OneMinMax, LOTZ and COCZ;
- use of multi-objective metrics such as hypervolume/IGD to guide adaptation;
- reported empirical speedups of adaptive mutation variants in the authors' tested settings.

Does **not** by itself support:
- our exact reproduction claim (that comes from our PR #23 evidence);
- superiority of our lambda hybrid;
- universal superiority on arbitrary multi-objective problems.

### Doerr, El Hadri, Pinard
May support:
- prior existence of `(1+(lambda,lambda))` Global SEMO;
- one-fifth-inspired dynamic parameter setting in discrete multi-objective optimization;
- their theoretical `O(n^2)` result for OneMinMax under the studied dynamic variant, versus the cited classic Global SEMO guarantee.

Consequence for thesis novelty:
- **do not claim first adaptive-lambda MOEA**;
- novelty must be restricted to the experimental combination with exact-reproduced TwoRate GSEMO and the reproducibility/validation protocol.

### Bassin / Buzdalov
May support:
- one-fifth population-size adaptation can degrade performance when its assumptions are poor;
- overly rapid lambda growth can be harmful;
- rollback was proposed to reduce negative impact in such scenarios.

Does **not** imply:
- rollback must help TwoRate GSEMO;
- our v2 should pass. In fact our preregistered v2 H1 failed.

### Eiben et al.
May support:
- the distinction between parameter tuning and on-line parameter control;
- the traditional deterministic/adaptive/self-adaptive taxonomy;
- the claim that strategy parameters such as mutation rate and population size are part of an executable EA specification and materially influence behavior.

Does **not** imply:
- one taxonomy label makes an algorithm empirically better;
- our specific feedback signal or multiplicative law is optimal.

### EC reproducibility literature
May support the thesis design choice to retain:
- exact source/version identities;
- random seed ledgers;
- raw measurements rather than summaries only;
- preprocessing/algorithm/analysis/presentation code;
- reproducible parameter-development procedure.

It does **not** establish correctness of our numerical results by itself; those are established by the repository evidence and independent gates.

### IOHprofiler / IOHexperimenter
May support:
- why granular logging of iterative optimization is useful;
- the role of fixed-target/fixed-budget measurements and tracking adaptive parameters;
- provenance of the experimentation infrastructure used by the source implementation.

## Repository/source references used as experimental objects

- FurongYe/GSEMO exact revision: `fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380`.
- IOHprofiler/IOHexperimenter exact revision: `f223c682dff0749067d00b870f83ad754f7d96f5`.
- Authenticated raw result artifact and exact reference-member identity are recorded in the EU26-27 source-native reproduction evidence and PR #23.

## Additional literature still to add before final thesis

- canonical source for the classic GSEMO definition/runtime baseline;
- primary hypervolume-indicator reference;
- optional recent review of statistical tests in evolutionary/swarm computation.

These entries must be searched and verified before being cited in the final manuscript; placeholder bibliographic metadata must not be invented.
