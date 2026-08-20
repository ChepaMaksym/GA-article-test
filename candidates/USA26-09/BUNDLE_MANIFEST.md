# USA26-09 reproducibility bundle

The complete clean-room source, tests, preregistration, compact per-seed data,
load/reset/worker reports, CSV table, and SVG figures are stored in:

`usa26-09-reproducibility-bundle.zip`

```text
SHA-256: 9da9cb8896965434a7da112c6a1a7dc4ea4249d79497f1f0f69e4ed35c2ca984
size: 83188 bytes
files: 37
```

The GitHub Actions workflow verifies the SHA-256 before extraction. The archive
uses sorted paths and a fixed ZIP timestamp, so its bytes are reproducible from
the retained candidate directory.

Large raw/debug rows and PNG renderings are intentionally excluded from the Git
snapshot; the compact 30-seed rows, machine-readable decisions, CSV table and
vector figures required to recompute the claims are retained. The archive
contains no upstream Julia source or upstream dataset bytes.
