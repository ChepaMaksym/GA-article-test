# Pre-outcome amendment for the 30-seed H1/H3 campaign

Status: `FROZEN_BEFORE_RESULT_INSPECTION`.

This amendment supersedes only the first-hit and confidence-bound details of
the initial 30-seed draft. It does not change the algorithms, seeds, data,
initial masks, budgets, targets, non-inferiority margin, or required effect
sizes.

## Why correction was required

The first draft represented target attainment asymmetrically:

- OLD recorded the first evaluated mask that reached the target;
- Hybrid 1 reconstructed attainment from the accepted-parent trajectory.

That would favor OLD and would not be a like-for-like NFE comparison. The
production campaign had started but no outcome rows or aggregate statistics had
been inspected. Version 2 was therefore frozen immediately and uses the same
rule for both algorithms:

> first logical objective evaluation whose observed validation accuracy reaches
> the target.

Hybrid H3 runs with one evaluation worker so call order is exact. Existing
1/2/4-worker tests remain evidence that final Hybrid outputs are worker
invariant. OLD target NFE includes any outer full-validation reevaluations that
occurred before the successful active-sample evaluation.

## Stronger H1 confidence rule

The initial draft proposed a one-sided 95% BCa lower bound. Version 2 uses the
lower endpoint of the **two-sided 95% BCa interval** for the paired median
Hybrid-minus-OLD test-accuracy difference. This is the more conservative rule.

The margin remains:

```text
-0.001 probability = -0.10 percentage point
```

H1 confidence-bound non-inferiority passes only if:

```text
BCa 95% two-sided lower endpoint >= -0.001
```

and at least 24/30 Hybrid runs improve the all-feature baseline by at least 1.50
percentage points.

## Frozen H3 rule

Targets remain `0.945`, `0.946`, and `0.947`, with `0.946` primary. Censoring
remains at 2,500 logical evaluations. H3 requires:

- common target attainment in at least 24/30 pairs;
- Hybrid target coverage at least as high as OLD coverage;
- paired median relative NFE reduction at least 20%;
- for a confidence-bound pass, the lower endpoint of the two-sided 95% BCa
  interval must also be at least 20%.

Hypothesis failure is a valid scientific result. CI fails only for broken
provenance, data pairing, logical-NFE accounting, or result structure.
