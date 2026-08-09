# EU26-09 targeted artifact contract v1

Frozen: 2026-08-09, before candidate-local implementation and before any
source-native replay.

Status: **`TARGETED_ARTIFACT_REPLAY`**

Paper mapping: **`PAPER_FIGURE_CONTEXT_ONLY`**

## Frozen source identity

- DOI: `10.1145/3564755`.
- Legal author manuscript: `https://mhevia.com/assets/pdf/journal_oplclga.pdf`,
  4,891,151 bytes, SHA-256
  `4ba0a96795ab7fe1c8d775489a41631ecca9f3b42e0ffbe5a0dc982ad1fa2221`.
- Official repository:
  `mariohevia/Parameter-Control-Mechanisms-Genetic-Algorithm` at commit
  `49949a55208359ac93b7110afb23ed276bda158d`, tree
  `a9d1a04fbbafbb114585ff7caf10bddc6381755a`.
- License: root `LICENSE`, GPL-3.0, SHA-256
  `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`.
- Raw member:
  `Raw/results_20-09-28_06:58:03_OneMax_n100_JA.OnePlusLambdaCommaLambdaSAReset_λ100.txt`,
  48,918 bytes, Git blob `5d6ab57c986d3c166cf0b731496d24d973b0b651`,
  SHA-256 `22177154c4375290632476ab8e82845465d4a7261a31c78f63701ef7e901714a`.

The Git revision is publication-era and selected by the auditor. Neither the
paper nor README identifies it as the execution revision.

## Frozen endpoint and protocol

The official README command is:

```text
python master.py -t OneMax -n 100 -l 100 -r 500 -c 1 -a JA.OnePlusLambdaCommaLambdaSAReset -G 1.5 --seed 885480221 -v
```

Frozen configuration:

- OneMax, `n=100`, 500 runs, stop on solved;
- base seed `885480221`;
- run IDs `1..500`;
- both `numpy.random` and Python `random` receive `base_seed + run_id`, hence
  seeds `885480222..885480721`;
- cap `lambda_max=100`, update factor `G=1.5`, crossover rate one;
- artifact evaluation accounting excludes the initial parent and adds
  `2*round(lambda)` per generation, including a zero-strength mutation draw;
- rows log the final generation's pre-transition rounded `lambda` and
  pre-transition `p=lambda_real/100`.

Required raw shape is exactly 48,918 UTF-8 bytes, 522 LF bytes, no CR or NUL,
no terminal LF, and 523 logical lines. Metadata, separators, all 500 contiguous
run rows, and all four footers must match the frozen grammar.

Frozen integer totals and exact means:

| Quantity | Total | Mean |
|---|---:|---:|
| generations | 98,168 | 196.336 |
| evaluations | 447,632 | 895.264 |
| final fitness | 50,000 | 100.0 |
| final logged rounded lambda | 4,946 | 9.892 |

All 500 rows must say `Solved: True`. Integer totals and decimal means are
exact; no numeric acceptance tolerance applies to the target endpoint.

## Independently implemented controls

The artifact/source profile is:

```text
p = lambda_real / n
c = min(1, 1 / lambda_real)
offspring_count = Python round(lambda_real)  # ties to even
success:       lambda_next = max(lambda_real / G, 1)
failure at cap lambda_next = 1
other failure: lambda_next = min(lambda_real * G^(1/4), lambda_max)
```

The paper-diagnostic profile substitutes `ceil(lambda_real)` for the offspring
count. It is intentionally not pooled with the artifact profile. Python and
MATLAB/Octave must independently implement ties-to-even for the source profile
and show the profiles differ at a frozen half-integer fixture (`lambda=2.5`).

## Verification gates

| Gate | Requirement |
|---|---|
| A1 source identity | Clean checkout commit/tree plus byte size, Git blob, and SHA-256 for every required member match before and after use. |
| A2 strict parser | UTF-8/line-ending shape, exact metadata, row grammar, contiguous unique run IDs, finite values, ranges, solved flags, and exact footers pass. |
| A3 endpoint | Recomputed integer totals and exact decimal means equal the frozen endpoint with no tolerance. |
| A4 controls | Independent source-profile transitions, reset, caps, probability mapping, evaluation parity, and paper/source rounding conflict fixtures pass. |
| A5 cross-language | MATLAB/Octave independently parses the authenticated raw member and agrees exactly on integer totals and decimal means; transition fixtures agree within `1e-12`. |
| A6 source-native replay | Optional authenticated disposable checkout run uses the exact command/seed schedule, records Python/NumPy/SciPy versions, and matches every run tuple and footer. |
| A7 fail closed | Mutations of commit/tree/hash/bytes, encoding, line endings, metadata, row count/order/IDs, solved flag, numeric syntax/ranges/non-finite values, footer, or claim boundary are rejected. |
| A8 boundary | Every result retains `TARGETED_ARTIFACT_REPLAY`, `PAPER_FIGURE_CONTEXT_ONLY`, all conflicts, and explicit `PASS_FULL` prohibition. |

## Outcomes

- `PASS_AUTHENTICATED_ARTIFACT`: A1 and A2 pass.
- `PASS_ARTIFACT_ENDPOINT`: A1 through A4 and A7 pass.
- `PASS_CROSS_LANGUAGE`: A5 passes without weakening any blocker.
- `PASS_SOURCE_NATIVE_RAW_REPLAY`: A6 passes exactly; this demonstrates replay
  under the recorded environment, not the authors' historical environment.
- `SOURCE_NATIVE_BLOCKED_<reason>`: A6 cannot run or differs; the full mismatch
  evidence is preserved.

`PASS_FULL`, `PASS_LITERAL_PAPER_ENDPOINT`, and
`HISTORICAL_DEPENDENCY_ENVIRONMENT_PROVEN` are forbidden under contract v1.
