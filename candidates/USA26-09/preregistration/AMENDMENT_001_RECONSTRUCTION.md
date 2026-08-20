# Amendment 001 - clean-room reconstruction and fresh confirmatory ledger

Date frozen: 2026-08-20

## Reason

The first USA26-09 publication attempt stored the executable package in a
binary ZIP whose remote bytes could not be authenticated against the declared
manifest after connector transport. The readable Markdown summary exposed the
old confirmatory ledger `2001..2030`, so those seeds are outcome-exposed and
may not be reused for the reconstructed implementation.

This amendment freezes a source-tree publication and a fresh confirmatory
ledger before any reconstructed confirmatory row is run.

## Evidence status superseded by this amendment

All previously stated USA26-09 numerical OLD/HYBRID decisions are
`SUPERSEDED_TRANSPORT_AND_RECONSTRUCTION_RERUN_REQUIRED`. They are historical
context only and cannot support the master thesis.

## Frozen pilot and confirmatory separation

- development/pilot seeds: `1001..1005`;
- pilot rows are excluded from hypothesis testing;
- fresh OLD/HYBRID confirmatory seeds: `3001..3030`;
- instance seed: `20240809`;
- nodes/customers/salesmen: `50 / 49 / 10`;
- logical objective-evaluation budget: `1500` per method and seed;
- matched first-hit target: `1.830`;
- population size: `40`;
- same initial population within each OLD/HYBRID pair;
- factor `F=1.5`;
- quality non-inferiority margin: `+0.010` objective units for
  `HYBRID - OLD`;
- coverage rule: HYBRID coverage is not below OLD and is at least `24/30`;
- efficiency rule: lower endpoint of the paired 95% percentile-bootstrap
  interval for relative capped-NFE reduction is at least `20%`.

## OLD-first gate

HYBRID confirmatory execution is prohibited until fresh OLD rows satisfy all
of the following:

1. `30/30` complete rows;
2. deterministic rerun and 1/2/4-worker equality;
3. median final objective `<=1.840`;
4. absolute difference between the fresh OLD median and the published Set-I
   `N=50,m=10` HGA anchor `1.82` is `<=0.020`.

This remains a published-cell compatibility gate, not an exact historical seed
replay because the paper's instance and search seed ledgers are unavailable.

## Frozen reconstructed mapping

Both OLD and HYBRID use the same exact dynamic Split objective, population,
success-weighted four-operator roulette, order crossover, and cheap
route-adjacency education. That education selects among legal edits without
calling the mTSP objective; it is recorded separately from logical NFE.

OLD uses a fixed six-proposal education effort for its selected local move.
HYBRID retains the same roulette but transfers the verified PR #8 control:

```text
p_g = lambda_g / n
c_g = 1 / lambda_g
offspring_g = round_half_up(lambda_g)

strict success: lambda_{g+1} = max(lambda_g/F, 1)
failure:        lambda_{g+1} = min(lambda_g*F^(1/4), n)
failure at cap: lambda_{g+1} = 1
F = 1.5
```

For every mutation edit, HYBRID selects the best route-adjacency surrogate
among `max(4, round_half_up(lambda_g))` legal proposals. This rule is frozen
now from pilot-only evidence and may not change after viewing seeds
`3001..3030`.
