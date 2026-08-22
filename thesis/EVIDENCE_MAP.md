# Evidence map for the master's thesis

Цей документ відокремлює твердження рукопису від джерел evidence. Жодне claim не повинно переходити до фінального тексту без вказаного рівня доказу.

## Claim classes

- `SOURCE_FACT` — твердження безпосередньо про paper/source/artifact.
- `REPRODUCED` — наш числовий результат, відтворений у frozen pipeline.
- `CONFIRMATORY_FAIL` — preregistered hypothesis не пройшла acceptance gate.
- `DEVELOPMENT_ONLY` — outcome дозволено використовувати для design, але не як незалежне підтвердження.
- `PENDING_CONFIRMATION` — protocol frozen, outcome ще не повинен цитуватися.

## Core evidence ledger

| Claim | Class | Evidence |
|---|---|---|
| Source-native TwoRate OLD відтворюється exact | `REPRODUCED` | PR #23; exact `101 x 100` first-hit matrix; 0 matrix mismatches; 0 endpoint mismatches |
| OLD mean FE = 61,623.78 | `REPRODUCED` | PR #23 canonical replay / authenticated Zenodo comparison |
| OLD median FE = 57,717.5 | `REPRODUCED` | PR #23 canonical replay |
| v1 reset improves OLD | `CONFIRMATORY_FAIL` | PR #24: paired median `-20.237076%`, CI `[-32.412176%, +4.934754%]` |
| v1 reset-specific effect | `CONFIRMATORY_FAIL` | PR #24: `-2.388751%`, CI `[-15.523548%, +10.684546%]`, `NO_CLEAR_EFFECT` |
| v2 rollback improves OLD | `CONFIRMATORY_FAIL` | PR #25: `+1.575182%`, CI `[-14.390699%, +19.145964%]` |
| v2 rollback adds clear benefit over floor ablation | `CONFIRMATORY_FAIL` | PR #25: `-11.055069%`, CI `[-21.663500%, +9.532151%]`, `NO_CLEAR_EFFECT` |
| v2 floor's lower marginal median proves improvement | **NOT ALLOWED** | marginal median is not the preregistered paired primary statistic; retired data only |
| v3 selected capped controller improves OLD | `PENDING_CONFIRMATION` | PR #26; only independent `29001..29030` holdout may resolve this claim |

## Immutable identities

### OLD

```text
GSEMO revision:
fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380

IOHexperimenter revision:
f223c682dff0749067d00b870f83ad754f7d96f5

gsemo.hpp blob:
2693144bcfccff902343a02c6c8e48d7dd263257

main.cpp blob:
22025e4680da85c98e3bb5ea30db8334ca25dff3
```

### HYBRID v1

```text
PR: #24
confirmatory seeds: 27001..27030
status: H1 FAIL
```

### HYBRID v2

```text
PR: #25
confirmatory seeds: 28001..28030
status: H1 FAIL
workflow run: 32572161500
artifact: 9475683444
artifact SHA-256:
085a477d5594e4fedb465c5817ebf3e4c3183165456f5ea7a3205388481a2ef3
```

### HYBRID v3

```text
PR: #26
development seeds: 28001..28030 (retired v2; development-only)
cap grid: {15,20,30,40,60,100}
selection: maximum paired-median relative FE reduction; tie -> smaller cap
independent holdout: 29001..29030
bootstrap resamples: 50,000
bootstrap seed: 29029
status: pending until workflow completes
```

## Seed non-reuse policy

| Ledger | Role now | May be called independent confirmation again? |
|---|---|---|
| 27001..27030 | historical v1 confirmatory | No |
| 28001..28030 | historical v2 confirmatory; v3 development | No |
| 29001..29030 | v3 independent holdout | Yes, only for the frozen v3 hypothesis; retired immediately after inspection |

## Thesis figure provenance

Figures must be generated from retained CSV/JSON/raw outputs, not manually redrawn values.

Planned figures:

1. exact OLD endpoint/reference identity;
2. v1 paired FE plot;
3. v2 paired FE plot;
4. v3 development score by cap;
5. v3 independent paired FE plot;
6. comparison of primary paired effects and 95% intervals across v1/v2/v3;
7. controller-state trajectory examples, clearly marked diagnostic rather than primary evidence.

## Claim wording rules

Allowed after a FAIL:

- “не отримано статистично підтвердженого покращення”;
- “95% bootstrap interval перетинає нуль”;
- “point estimate становить ...”;
- “дані не підтримують preregistered improvement claim”.

Not allowed after a FAIL:

- “алгоритми однакові”;
- “доведено відсутність ефекту”;
- “гібрид кращий” лише через нижчу marginal median;
- зміна margin/metric/seed subset після перегляду outcome з метою отримати PASS.

## Final evidence gate for thesis completion

Перед фінальним export рукопису необхідно:

1. перевірити статус PR #26;
2. записати v3 artifact identity;
3. синхронізувати `MASTER_THESIS_DRAFT.md` із final v3 report;
4. якщо є нові robustness/generalization experiments — додати їх як окремі hypotheses, а не змішувати з H1;
5. перевірити всі таблиці проти machine-readable reports;
6. переконатися, що claims prior art не перевищують формулювання джерел.
