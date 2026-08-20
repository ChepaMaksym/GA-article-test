# EU26-24 - Preferendus floating-wind OLD-first candidate

## Status

`PREREGISTERED_OLD_ONLY / HYBRID_BLOCKED_BY_OLD`

This is a new candidate cycle created directly from the verified PR #8 base. No
numerical result, thesis claim, data row, graph, or implementation from PR #19
is reused as evidence.

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

The published min-max endpoint is:

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
more than 15 task-specific physical/economic parameters, including vessel
capacities, day rates, availability limits, emissions, utilisation chances,
soil, chain, anchor and loading constants.

This distinction is explicit: the project does not falsely claim 51 independent
physical design variables.

## OLD objective and adaptive formula

The min-max objective is

```text
Phi(x) = max_i w_i * (100 - P_i(O_i(x)))
```

with weights `[0.30, 0.35, 0.15, 0.20]` for duration, cost, fleet utilisation
and emissions.

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
value `0.175`. OLD therefore has two named profiles:

- `source_compatible` - primary numerical reproduction of Tables 3 and 4;
- `printed_formula` - sensitivity profile, never silently substituted.

## OLD-first gate

Executable HYBRID work is forbidden until all of the following pass:

1. source, paper, license and blob identities;
2. objective, preference, decoder, constraint and mutation micro-oracles;
3. deterministic fixed-tape control transitions;
4. published Table 3/4 endpoint under the source-compatible profile;
5. independent deterministic feasibility/oracle check;
6. seed-ledger completeness and no outcome-informed amendment;
7. worker-invariant scientific rows for 1, 2 and 4 workers.

The full acceptance rule is frozen in `preregistration/PROTOCOL.md` and
`preregistration/protocol.json`.

## Planned HYBRID after OLD PASS

After OLD passes, the application, objective functions, constraints, decoder,
initial populations, seeds and logical evaluation budget remain fixed. The
search-control layer may then be replaced or augmented by the independently
verified PR #8 reset self-adjusting `(1+(lambda,lambda))` mechanism:

```text
p_g = lambda_g / n
c_g = 1 / lambda_g
```

with success-based shrink, failure-based growth and failure-at-cap reset.
Exploratory variants must use a separate training seed set. Only one frozen
variant may enter untouched confirmatory seeds.

## Claim boundary

Before the OLD and HYBRID gates pass, this branch may claim only candidate
selection, source authentication and formula-level work. It may not claim
published-result reproduction, improved quality, fewer iterations, faster wall
clock time, scientific novelty, or a completed master thesis.
