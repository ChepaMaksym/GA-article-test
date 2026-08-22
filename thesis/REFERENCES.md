# Core references — verified working bibliography

Це робочий бібліографічний список. Перед фінальним оформленням стиль має бути приведений до вимог університету, але назви, автори та DOI/identifiers нижче повинні зберігатися без вигадування metadata.

1. **Ye, F.; Neumann, F.; de Nobel, J.; Neumann, A.; Bäck, T.** *Towards Self-adaptive Mutation in Evolutionary Multi-Objective Algorithms.* arXiv:2303.04611, 2023. Source paper for the exact-reproduced GSEMO/TwoRate experimental line.

2. **Doerr, B.; El Hadri, O.; Pinard, A.** *The (1+(lambda,lambda)) Global SEMO Algorithm.* Proceedings of the Genetic and Evolutionary Computation Conference (GECCO 2022), 2022. DOI: **10.1145/3512290.3528868**. arXiv:2210.03618. This is key prior art for one-fifth-inspired dynamic parameter control in discrete multi-objective optimization.

3. **Bassin, A. O.; Buzdalov, M.** *The 1/5-th Rule with Rollbacks: On Self-Adjustment of the Population Size in the (1+(lambda,lambda)) GA.* GECCO '19 Companion, Association for Computing Machinery, 2019, pp. 277–278. DOI: **10.1145/3319619.3322067**.

4. **Bassin, A. O.; Buzdalov, M. V.; Shalyto, A. A.** *The “One-Fifth Rule” with Rollbacks for Self-Adjustment of the Population Size in the (1+(lambda,lambda)) Genetic Algorithm.* Automatic Control and Computer Sciences, 55(7), 2021, pp. 885–902. DOI: **10.3103/S0146411621070208**. A related open journal version appeared in Modeling and Analysis of Information Systems 27(4), pp. 488–508, DOI **10.18255/1818-1015-2020-4-488-508**.

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

## Repository/source references used as experimental objects

- FurongYe/GSEMO exact revision: `fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380`.
- IOHprofiler/IOHexperimenter exact revision: `f223c682dff0749067d00b870f83ad754f7d96f5`.
- Authenticated raw result artifact and exact reference-member identity are recorded in the EU26-27 source-native reproduction evidence and PR #23.

## Additional literature still to add before final thesis

- canonical source for GSEMO / Global SEMO definition;
- survey/taxonomy of parameter control in evolutionary algorithms;
- bootstrap/statistical comparison reference appropriate for stochastic optimization experiments;
- reproducibility recommendations for evolutionary computation;
- hypervolume indicator reference;
- IOHprofiler / IOHexperimenter methodology reference.

These entries must be searched and verified before being cited in the final manuscript; placeholder bibliographic metadata must not be invented.
