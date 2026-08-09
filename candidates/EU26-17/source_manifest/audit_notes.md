# EU26-17 source audit notes

## Revision relationship

Commit `cefd949488dbe23c030f17bb50b6c7c73a44ae3` adds the four SAGA
implementations on 2023-12-19. Commit
`2af04212216ffd6a01160167f50ee01e62b2b36c` is the last audited core
commit before the CEC 2024 conference dates and is used as a date-bounded
snapshot. The SAGA1 file and the two target methods have identical frozen
identities at both commits.

This relationship does not establish historical execution provenance. At
experiment commit `5c7c87df854ce397533b1d4efcdf8758b3783047`,
`requirements.txt` contains
`-e git+https://github.com/heidmic/suprb@main#egg=suprb`. It does not name a
commit or submodule. The first audited core tag containing `2af0421...`,
`v1.0.0`, was created after the conference. The validator must call the commit
an auditor freeze, never an author pin.

## Source/runtime evidence boundary

The experiment source fixes `random_state = 42`, constructs eight model seeds
with `numpy.random.SeedSequence(42).generate_state(8)`, and uses
`ShuffleSplit(n_splits=8, test_size=0.25, random_state=42)`. These are
source-level protocol facts. They do not prove that the plotted jobs ran this
exact revision or persisted those seeds.

The frozen `.gitignore` ignores `**/mlruns/**`, `mlruns/**`, and
`mlruns_pt/**`; no matching raw result members exist in the frozen Git tree.
Consequently, no figure point can be traced to a raw MLflow record by this
artifact.

## Paper object and target boundary

The institutional PDF is lawful full text, but the retrieved wrapper reports
2026 metadata around a 2024 publication. Its exact bytes are authenticated so
the Table I fact can be parsed deterministically. The later wrapper metadata
is not evidence of the camera-ready object's publication-time identity.

Table I literally reports Parkinson's Telemonitoring (`PT`) with dimension
`18` and sample count `5875`. The frozen CSV has 22 columns and 5,875 data
rows. Removing target `total_UPDRS` plus `subject#`, `test_time`, and
`motor_UPDRS`, exactly as the loader specifies, leaves the 18 feature names in
the JSON contract. The loader docstring says dimensionality 26; that stale
docstring is not used as expected evidence.

The paper's optimizer outcomes are figures rather than literal numeric cells.
Approximate observations in prose are intentionally neither transcribed nor
tested. The Table I dimension and sample count are descriptive dataset facts,
not published optimizer endpoints and not proof that the GA chromosome itself
has 18 direct decision variables.

## Validation-harness divergence

The upstream `calc_gdm` method directly divides mean fitness by maximum
fitness, and `adjust_rates` compares the result to both thresholds. There is no
explicit empty, NaN, infinity, or zero-maximum guard. The clean-room Python and
MATLAB/Octave implementations will reject those inputs to remain fail closed.
That deliberate test-harness policy is reported separately and never patched
into or attributed to upstream source.
