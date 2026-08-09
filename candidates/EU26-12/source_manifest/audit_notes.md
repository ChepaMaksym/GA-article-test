# EU26-12 source and provenance audit

Audit date: 2026-08-09. No source-native endpoint run was executed before the
contract was frozen.

## Paper-to-artifact mapping

The paper's reproducibility paragraph cites Zenodo DOI
`10.5281/zenodo.7624677` as the complete experiment scripts, irace logs,
verification runs in IOHanalyzer format, analysis, and visualization material.
Experiment 1 states 24 BBOB problems, 50 runs split across ten instances,
dimensions 5, 10, and 20, and a budget of 50,000 evaluations. Table 2 names
the exact L-SHADE modules used by the common runner.

This is a literal mapping to the paper experiment and artifact collection, but
the exact first-run JSON value is not printed in the paper. The study therefore
uses `PAPER_EXPERIMENT_ARTIFACT_MAPPING`, not a literal-paper endpoint claim.

## Publication source revision

The Zenodo static `ModDE.zip` was created from CRLF working-tree files. For all
14 required source, test, documentation, and license members, CRLF-to-LF
normalization produces the exact Git blob IDs at commit
`b65062c66ecf22873f2e8f0aa4b12d04161d4bd5`, tree
`b845e5b2677ed43768eb5d664c2481e8db022466`. This commit is dated
2022-12-22 and predates artifact publication. The paper and artifact do not
name the Git revision, so it remains an auditor-established mapping rather
than an author-pinned execution revision.

The artifact's `requirements.txt` contains only lower bounds. Bundled
`cpython-38.pyc` filenames and the upstream CI matrix provide evidence for
Python 3.8 compatibility, not an exact historical environment.

## Non-vendoring and range policy

No paper, upstream source, Zenodo file, central directory, or raw member is
committed in this candidate folder. The verifier fetches the 70-KB code
archive, 6-KB runner, 64-KB archive tail, 7.3-MB ZIP64 directory, and only the
compressed bytes of the selected JSON and companion DAT members. Each request
is bounded below eight MB and must return an exact HTTP `206 Content-Range`.

The Zenodo metadata declares the full raw archive's size and MD5. Because the
4.8-GB object is never downloaded in full, this study cannot claim to have
recomputed that MD5. Instead it freezes and checks the tail, ZIP64 records,
complete central directory, local headers, compressed streams, CRC32 values,
uncompressed sizes, and member SHA-256 values.

## Audited execution semantics

`Common_DE_runner.py` loops instance IDs 0 through 9 and seeds 0 through 4,
calls `np.random.seed(seed)` for every run, constructs the selected L-SHADE
modules, and requests 50,000 evaluations. The static source initializes 360
individuals directly against IOH, so those evaluations do not increment its
separate `used_budget`. Later offspring do increment `used_budget`. Termination
is tested only after a whole population has been evaluated.

The exact source schedule reaches 582 generations, offspring-used budget
49,642, and IOH evaluation 50,002. The JSON reports that exact total. It also
reports the best objective `1.698652750709869e-14`, first reached at evaluation
45,886. The companion DAT rounds it to zero at ten decimal places, so endpoint
acceptance is bound to the authenticated JSON decimal literal.

The source updates both `F` and `CR` memories using weighted arithmetic means,
samples CR from a clipped normal distribution and F from a positive-redrawn,
upper-capped Cauchy distribution, and linearly reduces the population using
NumPy rounding. Replacement chooses the offspring on equal fitness but records
only a strict decrease as an adaptation success. These released semantics are
the independent-control target even where they differ from canonical SHADE.
