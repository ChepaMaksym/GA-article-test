# EU26-02 hardware evidence — superseded 2026-08-07

Status: **`SUPERSEDED_TOCTOU_RERUN_REQUIRED`**.

The prior Work 4, Work 8, GitHub 4-vCPU and H5 reports were generated before
archive workers were bound to immutable authenticated member bytes. Amendment
004 supersedes every earlier H0–H5 archive/hardware claim, including the
previous `PASS_BITWISE` comparison.

Work 4 and Work 8 must be rerun from the first clean tracked remediation
revision. GitHub 4-vCPU must then run from the byte-identical PR tree, after
which the fail-closed comparator must recompute H5 from all three full result
objects and the shared payload manifest.

The paper-level status remains **`BLOCKED_MULTIPLE_SOURCE_CONFLICTS`**.
