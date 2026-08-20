# Candidate-search loop before EU26-24

This ledger records candidates rejected before implementation or before HYBRID.
It prevents unsuitable studies from being silently forgotten and prevents files
from a failed candidate from becoming evidence for a later one.

## EU26-22 - MOEA-ISa

Result: `REJECTED_OLD_NUMERIC_ENDPOINT_UNAVAILABLE`.

The source and adaptive crossover formulas were verifiable, but the released
runner contained a dataset-loop defect, the historical seed ledger and exact
runtime were absent, and no unambiguous retained 30-run numeric endpoint could
be bound before experimentation. The candidate was closed as PR #20 and is not
reused here.

## FSTSP self-adaptive GA screening

Result: `REJECTED_BEFORE_IMPLEMENTATION`.

The discovered repository did not establish an authenticated mapping to the
study implementation and did not expose a complete reproducible result package.
Candidate files were removed from its temporary branch.

## Hybrid min-max multiple-TSP screening

Result: `REJECTED_BEFORE_IMPLEMENTATION`.

The routing study had an applied high-dimensional problem and public Julia
source, but the inspected snapshot lacked an explicit repository license and a
historical seed ledger, required an unavailable Julia environment, and exposed
source-level uncertainties that prevented a clean OLD-first claim. No code from
that candidate is carried into EU26-24.

## Why EU26-24 proceeds

Preferendus provides all of the following before implementation:

- recent EU publication;
- real industrial infrastructure case;
- author-linked public repository;
- Apache-2.0 license;
- immutable commit and file blobs;
- explicit objective, constraint and search code;
- 51 mutable chromosome loci;
- an adaptive log-normal mutation controller in the released GA;
- literal numeric Table 3 and Table 4 endpoints;
- a computationally manageable clean-room Python path.

Proceeding means only that EU26-24 passed the screening gate. It does not imply
that OLD reproduction or HYBRID improvement has passed.
