# EU26-02 authenticated archive validation — 2026-08-07

Formal local source commit: `4a37d5fb829540a63694fd641600de7d30c5173f`.
Remote source commit: `71c84c657f98466d3446855dd65491fef32a910a`.
Both have the byte-identical source tree
`932d16a490a502daa62ed4af54714b33e0d27ab6`.

The run began and ended with every H0 source tracked, clean and unchanged. The
64,960,102-byte archive matched SHA-256
`1b7e8cf1ef637005bd994104f6e1ee520256ed387994b126bbe875a137632e41`.
Parsing used the private authenticated 276,705,280-byte tar snapshot with
SHA-256 `a3c5893a1a7de480a05b26cbef24a2e07d161f8ed5923354444d6ea2d2fb5cf8`.

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

The full archive report is 433,553 bytes with file SHA-256
`137e9a89763565ae98aaf90ec9796381d9b066e82c26e899429f90713096ec47`
and semantic report digest
`ebe802cf61a2580d23d7e6331a846e57ca11831e04b2d8a0dbc3c0f0701e2160`.
The candidate workflow regenerates and uploads the complete per-seed JSON.

These results establish exact table-artifact provenance only. The mandatory
paper-level status remains **`BLOCKED_MULTIPLE_SOURCE_CONFLICTS`** and
`PASS_FULL` remains forbidden.
