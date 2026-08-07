# Amendment 003 — deterministic container access

Frozen: 2026-08-07, after the first accepted formal command was manually
stopped without a report or scientific result.

The pinned compressed tar stores members in an order different from the
31-row target order. Random member access through Python's gzip seek path was
too slow for the frozen CI timeout. No P1/P2 status or partial cell result had
been emitted when the command was stopped.

Every full `validate_archive()` call must continue to hash and authenticate
the original 64,960,102-byte gzip object. After that check, it may decompress
the authenticated bytes once into a temporary, uncompressed tar outside the
repository and parse members from that derivative. The derivative's SHA-256
is retained in the report and the temporary file is deleted on exit.

This amendment changes container access only. It does not change member
selection, source data, seeds, target cells, P1/P2 row rules, statistics,
rounding, tolerances, or outcome labels.
