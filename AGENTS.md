# Repository instructions for agents

## Start here

Read these files before changing scientific claims or execution state:

1. `RESEARCH_STATUS.md`
2. `registry/README.md`
3. `registry/attempt_outcomes.md`
4. `failure_logs/README.md`
5. `verification/README.md`

The active default branch is `main`. There is no separate `master` branch.

## Scientific-integrity rules

- Do not call any candidate successfully reproduced unless every required
  gate reaches `PASS_FULL`.
- Preserve failed runs, negative outcomes and distinctions between source
  facts, assumptions, diagnostics and prospective infrastructure.
- Do not invent missing formulas, seeds, inputs, licenses or published
  values.
- A new candidate must be admitted by a documented eligibility audit
  before implementation.
- Freeze source revisions, data hashes, seeds, numerical endpoints,
  adapter sources and adapter configuration before inspecting outcomes.

## Protected evidence and generated files

- Treat `failure_logs/USA-001_evidence/` as immutable retained evidence.
  Its 25 manifest-listed files must keep their exact bytes and SHA-256
  values. The root `.gitattributes` rule intentionally disables text
  normalization for its CSV files.
- Do not edit or delete `old/`; it is a historical archive.
- Do not stage or delete `sandbox/results/`; it contains ignored generated
  artifacts that may belong to prior work.
- Do not recreate deleted candidate folders unless a documented restore is
  explicitly requested. A restore must not rewrite the recorded outcome.

## Verification

Run from the repository root:

```matlab
addpath('verification')
results = runtests('verification/tests');
assertSuccess(results)
verify_retained_evidence
analyze_historical_runtime
```

Before integrating a real adapter, bind it with
`fastverify.bind_adapter`. Adapter source files and immutable
configuration are part of the contract and cache identity. Do not bypass
checkpoint, provenance, seed-ledger or gate-schema validation.

## Commit scope

Keep scientific source/evidence changes separate from ignored caches and
generated outputs. Review `git status`, `git diff --check` and the staged
diff before committing. Intentional two-space CommonMark hard breaks in
historical Markdown files are not whitespace defects.
