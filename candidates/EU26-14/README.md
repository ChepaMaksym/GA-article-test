# EU26-14 — MSC-CMA-ES targeted artifact replay

Paper: Nedanovski, Nenov, and Pilev,
*MSC-CMA-ES: Structure-Aware Restarts for CMA-ES via Cyclic Nearest-Better
Basin Discovery*, arXiv:2606.15830v3, DOI
[`10.48550/arXiv.2606.15830`](https://doi.org/10.48550/arXiv.2606.15830).

Status: **`TARGETED_ARTIFACT_REPLAY_ONLY`**

Paper mapping: **`PAPER_CONTEXT_ONLY`**

This candidate authenticates the complete source and CEC2020 Zenodo archives,
then replays one lexicographically selected raw endpoint without running
source-native optimization. The frozen member is:

```text
experiments/cec2020/d15/MSC-CMA/maxevals_3000000/f1.pkl
```

It records CEC2020 F1 at dimension 15, budget 3,000,000, 51 seeds (`0..50`),
and full CMA-ES under the alternating MSC restart schedule. Run 0 has error
`0.0`, 339 improvement rows, 30 cycles, pre-refinement error
`0.8729793091438722`, and `nfev_total=2893419`.

## Security and evidence boundary

Every external artifact input is traversed component by component without
following symlinks, opened once, hashed through a retained descriptor, rewound,
parsed from that same descriptor, then re-fstat'ed and re-hashed. Final path
and parent-directory identities are rechecked. Path replacement, ancestor or
leaf symlinks, in-place mutation, archive duplicates, unsafe tar names/types,
wrong offsets, and output replacement fail closed.

The result archive is hashed in full before zstd/tar decoding. The selected
pickle is never passed to a general unpickler. A local stack machine recognizes
only the exact protocol-5 primitive subset and statically validates the two
NumPy constructions used by the frozen bytes: `numpy.dtype` and
`numpy._core.numeric._frombuffer`. No payload callable is imported or run.
Exact dtype `BUILD` slots are type-checked so Python numeric equality cannot
substitute booleans or floats for frozen integers. The post-freeze clarification
and its timing are disclosed in
[`preregistration/amendment-001-safe-pickle-and-verifier-hardening.md`](preregistration/amendment-001-safe-pickle-and-verifier-hardening.md);
the original preregistration files remain byte-identical to their frozen commit.

The committed JSON and CSV fixtures bind source/result/member hashes, seed
order, run-0 endpoint literals, every run-0 cycle, alternation, sample reuse,
and evaluation/improvement arithmetic. GNU Octave checks those controls
independently. The finalizer recomputes the domain-separated Python report
digest, enforces the complete claim/gate projection with exact JSON types, and
binds the Octave fixture hashes and exact static assertion-site count. Octave
creates its report through `mkstemp` plus an atomic no-clobber hard link; an
existing output is never replaced.

## Run locally

Install the verifier dependency and run unit/protocol/adversarial tests:

```bash
python -m pip install -r candidates/EU26-14/environments/python/requirements.txt
python candidates/EU26-14/tests/run_python_tests.py
```

With the four complete inputs in an artifact directory:

```bash
EU2614_ARTIFACT_DIR=/path/to/artifacts \
  python candidates/EU26-14/tests/run_python_tests.py --require-full-artifact

python candidates/EU26-14/environments/python/run_artifact_verification.py \
  --record-json /path/to/artifacts/record.json \
  --checksum-manifest /path/to/artifacts/SHA256SUMS \
  --source-archive /path/to/artifacts/source.tar.gz \
  --result-archive /path/to/artifacts/msc_cec2020.tar.zst \
  --output /new/path/eu26-14-report.json
```

Run the independent control when Octave is installed:

```bash
octave --quiet --eval \
  "addpath('candidates/EU26-14/tests/octave'); run_octave_tests('/new/path/octave.json');"
```

Every candidate-scoped pull request automatically runs registry regression,
Python 3.13.5 unit/adversarial controls, independent Octave controls, and a
required bounded download that reauthenticates the complete 318 MB archive.
The full job rejects any test skip and binds the two language reports.

## Claim ceiling

`PASS_TARGETED_ARTIFACT_REPLAY` means only that the immutable licensed
artifact, safe parse, frozen endpoint, and controls passed. It is not
`PASS_FULL`, an exact source-native replay, a literal paper endpoint, or proof
of the historical environment.

The raw run stops 106,581 evaluations short of its nominal budget. This is
kept as a paper/raw stop-semantic conflict; literal budget exhaustion is not
claimed.
