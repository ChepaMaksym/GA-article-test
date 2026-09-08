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
