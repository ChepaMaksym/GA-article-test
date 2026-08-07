# Candidate selection log

EU26-07 was selected after hard-stop screening against the current adaptive-GA
definition and the provenance failures recorded for earlier candidates.

The strongest runner-up was Nguyen et al. (FOGA 2025), *Multi-parameter
Control for the (1+(lambda,lambda))-GA on OneMax via Deep Reinforcement
Learning*. It genuinely controls `lambda_m`, `lambda_c` and `alpha` and has
open code, but the paper omits integer rounding, its Algorithm 1 specifies
uniform ties while source takes the first strict best, and the paper starts
uniformly while the evaluation instance fixes exactly half the bits. EU26-07
was preferred because it exposes the complete raw ledger and exact seed map.

The GECCO 2021 one-shot dynamic crossover candidate was not selected because
its exact fitness-band schedule is shown graphically rather than tabulated in
the paper. Mutation-only alternatives were rejected for missing numeric
targets/provenance or for source code that did not actually apply the claimed
adaptive mutation parameter.
