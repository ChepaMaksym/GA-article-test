# USA26-09 - adaptive HGA for min-max mTSP, reconstructed OLD first

## Current status

```text
first binary-bundle publication: SUPERSEDED_TRANSPORT_RERUN_REQUIRED
reconstructed source tree: FROZEN_BEFORE_CONFIRMATORY_V2
fresh OLD seeds 3001..3030: NOT_RUN
fresh HYBRID seeds 3001..3030: BLOCKED_BY_OLD
cross-machine current-head CI: PENDING
master thesis: BLOCKED_BY_FRESH_RESULTS_AND_CI
PR #19 numerical evidence used: false
```

The candidate is Mahmoudinazlou and Kwon, *A hybrid genetic algorithm for the
min-max Multiple Traveling Salesman Problem*, Computers & Operations Research
162 (2024) 106455, DOI `10.1016/j.cor.2023.106455`.

The author-linked Julia repository is pinned at
`Sasanm88/m-TSP@7d9fa1f63dfae44506f33a43aaa812793bebc065`. Because it has no
project-wide license file, this candidate contains an independent clean-room
Python implementation and no copied upstream code or data bytes.

## Objective

For `m` depot-returning tours, minimize the longest tour:

```text
minimize max_r C(T_r)
```

A permutation chromosome is evaluated by an exact dynamic contiguous Split.

## OLD adaptive formula

```text
w_i(0)=100
p_i(g)=w_i(g)/sum_j w_j(g)
w_i(g+1)=w_i(g)+1 after a strict improvement by operator i
```

The four moves are Reinsert, Exchange, Or-opt2 and Or-opt3. OLD uses fixed
education effort.

## HYBRID formula

Only after the fresh OLD gate passes, HYBRID may use:

```text
p_g=lambda_g/n
c_g=1/lambda_g
offspring_g=round_half_up(lambda_g)

success:        lambda_{g+1}=max(lambda_g/F,1)
failure:        lambda_{g+1}=min(lambda_g*F^(1/4),n)
failure at cap: lambda_{g+1}=1
F=1.5
```

See `preregistration/AMENDMENT_001_RECONSTRUCTION.md` and
`preregistration/protocol_v2.json`. The fresh confirmatory ledger is
`3001..3030`; earlier `2001..2030` results are outcome-exposed and superseded.
