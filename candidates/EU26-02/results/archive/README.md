# EU26-02 formal archive validation — 2026-08-07

Formal Git SHA: `79eb3b6e01e581fb364c9f17b4db985544eb0130`.

The run began and ended with every hashed source tracked and byte-identical to
that HEAD. The original 64,960,102-byte archive matched SHA-256
`1b7e8cf1ef637005bd994104f6e1ee520256ed387994b126bbe875a137632e41`.

## Results

- P1 `artifact_actual_10800`: `PASS_ARCHIVE_EXACT`; all 31 published
  AHEAD+Deleter best/mean/time cells match, all seeds `0..19` are retained,
  and the canonical 31-instance digest is
  `23ad21210e61dddd10f4fbb72a50dcc882f006ebc7d5d0e7395b0d78b77d9de6`.
- Inventory: 1,143 root attempt files, 620 retained legal results, 298 files
  with 7,450 literal `restart` lines.
- P2 `paper_claimed_3600_diagnostic`: `DIAGNOSTIC_ONLY`; 617 results remain.
  Missing are `C2000.9` seeds 3 and 8 and `r1000.5` seed 5.
- Selected `r250.5`, seed 15 witness: `PASS_SELECTED_WITNESS`; the pinned
  235-vertex/13,968-edge input has a 66-color solution with zero conflicts,
  and the archived turn-30 transition removes operator 1.

The complete local archive report was 433,451 bytes with file SHA-256
`7143c378808c4923cc77a5ac6d169c742e61cece7626bf494140c06579415b9f`
and semantic report digest
`94760eff05e0d4460d086d6de1cac3cb6b19c7d5d75aef1068669b59711ebe61`.
The candidate workflow regenerates and uploads the complete per-seed JSON.

These results establish exact table-artifact provenance only. The mandatory
paper-level status remains **`BLOCKED_MULTIPLE_SOURCE_CONFLICTS`** because the
paper, code, archive and environment do not specify one common protocol.
