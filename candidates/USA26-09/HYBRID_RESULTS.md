# USA26-09 HYBRID status

```text
HYBRID = BLOCKED_NOT_AUTHORIZED
EXECUTABLE HYBRID EVIDENCE = REMOVED
```

HYBRID cannot be evaluated because the OLD reproduction gate failed.
Historical numbers from the first PR publication and the superseded binary
bundle are not scientific evidence.

A second blocker is budget fairness: HYBRID selected
`max(4, round_half_up(lambda))` surrogate proposals for every edit of every
mutant, while OLD used a fixed six proposals. Those surrogate evaluations were
not recorded in `RunResult`, so logical Split-call counts did not measure equal
total work.

The dual-adaptation formula remains a prospective idea only. It may be tested
on a future candidate after an independently reproduced OLD and explicit exact,
surrogate, cache and wall-clock effort ledgers are frozen.
