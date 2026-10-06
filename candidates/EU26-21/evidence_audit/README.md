# Historical evidence audit (separate from the prospective bridge)

The manual `eu26-21-historical-evidence-audit.yml` workflow authenticates the
two already published historical archives by fixed repository, run ID, head
SHA, artifact ID, name, API digest and independently hashed downloaded ZIP.
It safely extracts original bytes and checks each ledger is exactly seeds
1..30. Existing strict aggregators then recompute the source-compatible and
corrected official-UCI profiles separately. No optimizer is run, no model is
trained, and no historical row is regenerated or combined with bridge seeds.

The output artifact preserves the extracted original archives' contents and
adds per-profile reports and a manifest with source/file/report SHA-256
digests. GitHub retains the new output for 90 days. This is renewable evidence
retention, not permanent archival storage. In particular, API metadata on
2026-09-08 gave 2026-09-15 as the original source-compatible final artifact's
expiry. The original artifacts and runs are never modified or deleted.

Execution and unit tests are GitHub Actions only. The registration push event
skips the audit job; explicit manual dispatch binds the checked-out code and
actual workflow revision to its expected SHA. The bootstrap and decisions
remain those of each historical protocol, not the new bridge's estimand.

## Descriptive bridge report

The separate `eu26-21-thesis-evidence-report.yml` workflow runs on scoped
reporting-file pushes or manual dispatch. It binds its actual workflow and
reporting implementation to the pushed SHA or dispatch `expected_sha`. It fetches
only the 30 fixed artifact IDs from campaign `34233477859`, authenticates
their ZIP/file hashes, and checks all paired observations against the two
preserved campaign/reaggregation reports. Synthetic table and adaptive
diagnostic tests run in CI before the immutable inputs are downloaded.

`thesis_tables.py` produces arm medians, all 30 paired CSV rows, two explicitly
descriptive plots and a provenance/output-hash manifest. It performs no new
optimization, model fitting/deserialization, bootstrap or hypothesis test.
Arm medians and means in these displays must not be substituted for the
preregistered median paired differences. Failed non-inferiority and the
blocked efficiency/subset-size claims are preserved unchanged.

The [Ukrainian thesis research report](../common_bridge/THESIS_REPORT_UK.md)
records the evidence links and distinguishes research SHA from reporting SHA.

## Adaptive response and observed non-improvement intervals

`adaptive_diagnostics.py` uses the same authenticated 30-pair campaign and
independently validates saved generation transitions. The
[descriptive analysis plan](ADAPTIVE_DIAGNOSTICS_PLAN_UK.md) fixes example
seed 41001, all-pair inclusion, counter definitions and interpretation
before these summaries are computed. It is a post-outcome analysis, not a
new preregistered confirmatory experiment.

The output separates success relative to the current parent (which controls
lambda), strict improvements of the best queried lexicographic score, and
improvements in validation WBA alone. Counters start at zero after the
shared 50 initial evaluations. Their maxima and terminal values describe
only calls 51–400; a terminal interval is cut off by the evaluation limit.
Plots, CSV files and a hash manifest are generated only in CI, without new
search, training, model deserialization or statistical decisions. None of
these descriptive measurements establishes a local optimum or a causal
benefit of adaptation.
