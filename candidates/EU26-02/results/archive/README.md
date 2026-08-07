# EU26-02 archive evidence — superseded 2026-08-07

Status: **`SUPERSEDED_TOCTOU_RERUN_REQUIRED`**.

The archive replay and selected-witness evidence previously recorded from Git
SHA `cc6b4834d59c86511c363343fa68f03169c20e2b` used a hash-close-reopen access
path. An adversarial review showed that a caller-controlled archive could be
replaced after hashing and before parsing. Amendment 004 therefore supersedes
those reports as acceptance evidence.

The earlier numerical observations are retained only in Git history. They do
not establish a current provenance PASS and must not be cited as such. P1, P2
and the selected witness must be regenerated from the first clean tracked
revision containing the authenticated-snapshot remediation.

The paper-level status remains **`BLOCKED_MULTIPLE_SOURCE_CONFLICTS`** and
`PASS_FULL` remains forbidden.
