# EU26-17 — SupRB SAGA1 source-transition validation

Paper: Michael Heider, Maximilian Krischan, Roman Sraj, and Jörg
Hähner, *Exploring Self-Adaptive Genetic Algorithms to Combine Compact Sets
of Rules*, IEEE CEC 2024, DOI
[`10.1109/CEC60901.2024.10612101`](https://doi.org/10.1109/CEC60901.2024.10612101).
All authors list the Organic Computing Group, University of Augsburg,
Augsburg, Germany.

Artifact scope: **`FORMULA_AND_SOURCE_TRANSITION_VALIDATION_ONLY`**

Eligibility status: **`HARD_FAIL`**

SAGA1 changes its mutation and crossover rates once per solution-composition
generation, before selection, crossover, mutation, replacement, and the next
population fit. The source transition is sufficiently explicit to test in
Python and MATLAB/Octave. This directory therefore authenticates and exercises
that narrow transition only.

It is not a published-result reproduction. The unchanged paper has no literal,
unambiguous numeric SAGA1 result cell: its empirical results are figures, and
the few approximate statements in prose are neither protocol-complete nor
permitted targets. This is a decisive gate-8 failure. No score, tolerance, or
numeric endpoint is frozen here.

Other blockers independently prevent a full claim:

- the Parkinson's Telemonitoring row establishes 18 input features and 5,875
  samples, but input dimensionality is not automatically the number of direct
  chromosome decisions; the benchmark-only applied-status interpretation is
  unresolved;
- the experiment revision installs `heidmic/suprb@main`, not an immutable
  SupRB commit. Core commit `2af0421...` is an auditor-selected,
  publication-era snapshot, not an author-pinned experiment dependency;
- the repositories ignore and omit the `mlruns` result store, so the plotted
  runs cannot be mapped to raw run records;
- the first core tag containing the selected snapshot postdates the
  conference, and the retrieved institutional PDF wrapper has later metadata,
  leaving release/publication provenance unresolved.

The preregistered claim boundary and exact source identities are frozen under
`preregistration/` and `source_manifest/`. Passing the eventual validators may
establish only source identity, source-method transitions, cross-language
agreement, and the Parkinson input-dimension fact. `PASS_FULL`, empirical CEC
replay, a literal-paper-endpoint pass, and an author-pinned-core claim are
forbidden.
