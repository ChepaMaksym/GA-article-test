# EU26-24 - Preferendus floating-wind OLD-first candidate

## Final status

`REJECTED_OLD_REPRODUCTION / HYBRID_BLOCKED_NOT_CREATED`

This was a new candidate cycle created directly from the verified PR #8 base.
No numerical result, thesis claim, data row, graph, or implementation from PR
#19 was reused as evidence.

The 30-seed source-compatible OLD campaign completed successfully at the
runtime/protocol layer, but only 10/30 runs entered the preregistered published
anchor basin; the required coverage was 24/30. The acceptance rule was not
weakened after observing the pilot or confirmatory rows. See `OLD_STATUS.md`.

## Reference study and source

- H. J. van Heukelum, R. Binnekamp, A. R. M. Wolfert,
  *Socio-technical systems integration and design: a multi-objective
  optimisation method based on integrative preference maximisation*.
- Publication year: 2023; version of record published 16 January 2024.
- DOI: `10.1080/15732479.2023.2297891`.
- Applied case: floating-wind-turbine anchor installation planning.
- Author-linked source: `TUDelft-Odesys/Preferendus`.
- Frozen source commit: `5b2e5c337b0b06cd4cf1c208de4c0679d64a2fe4`.
- Source license: Apache-2.0.

Published min-max endpoint:

```text
x = [1 small OCV, 0 large OCV, 2 barges, 2.2 m diameter, 8.0 m length]
project duration = 91 days
installation cost = 10.45E6 EUR
fleet-utilisation objective = 0.04
CO2 emissions = 7135 t
preference scores = [43, 38, 97, 15]
```

## Dimension requirement

The applied model has five decoded design variables, but the published source
profile encodes the two real variables with 24 bits each and retains three
integer loci. The mutable chromosome therefore has `3 + 24 + 24 = 51` loci,
which exceeds the project threshold of 15. The engineering model also contains
more than 15 task-specific physical/economic parameters.

This distinction remains explicit: the project does not falsely claim 51
independent physical design variables.

## OLD objective and adaptive formula

The min-max objective is

```text
Phi(x) = max_i w_i * (100 - P_i(O_i(x)))
```

with weights `[0.30, 0.35, 0.15, 0.20]`.

The source mutation controller uses a log-normal random walk. For chromosome
locus count `R`, mutation-order parameter `q=4`, and `Z_g ~ N(0,1)`:

```text
tau = R^(-1/q)
r_mut(0) = tau
r_mut(g+1) = r_mut(g) * exp(tau * Z_g)
```

Crossover is fixed at `r_cross=0.8`. The source profile uses population 1500,
maximum 400 generations, maximum stall 20, 10% elitism and 24 bits per real
variable.

## Paper/source divergence retained

The printed fleet formula is `prod_i p_i^x_i`, while the released code computes
`prod_i p_i^(x_i^2)`. The published Table 3 value `0.04` for `[1,0,2]` agrees
with the released-code value `0.7 * 0.5^4 = 0.04375`, not the literal printed
value `0.175`.

OLD therefore used two named profiles:

- `source_compatible` - primary numerical reproduction of Tables 3 and 4;
- `printed_formula` - sensitivity profile, never silently substituted.

## Confirmatory result

```text
complete and feasible: 30/30
vessel configuration [1,0,2]: 30/30
published anchor basin: 10/30, required 24/30
median duration: 91.0 days
median cost: 10,460,923.52 EUR
median fleet objective: 0.04375
median emissions: 7135 t
median logical NFE: 57,000
campaign digest:
9e745f23e12f71f80f96938f0ebd8d2ae91dd48e7ba26dbdc3655b01b0209ebc
```

Decision:

```text
OLD = REJECTED_OLD_REPRODUCTION
HYBRID = BLOCKED_NOT_CREATED
MASTER THESIS = BLOCKED
```

No executable EU26-24 implementation is retained in this repository. The next
candidate must start from the PR #8 base rather than from this rejected branch.
