# GA Article Test

## Активний кандидат EU26-21

У гілці `research/EU26-21-chcqx-census-old-first` та draft PR #19 активне
дослідження EU26-21 для CHC-QX, Census-Income і Hybrid 1. Воно має два окремі
валідаційні профілі, які не можна змішувати.

```text
Source-compatible OLD reproduction: PASS_SOURCE_NUMERIC_ALIGNMENT
Source-compatible Hybrid H1-H3: PASS_EXTENDED_30_SEED_H1_H2_H3
Corrected official-UCI protocol: PASS_PROTOCOL_RESULTS_AVAILABLE
Corrected C-H1: FAIL_NONINFERIORITY
Corrected C-H2: BLOCKED_BY_H1
Corrected C-H8 reset ablation: NO_CLEAR_EFFECT
PR: draft, open, not merged
```

Source-compatible профіль зберігає історичне encoded представлення, 41-бітну
маску, accuracy objective і source-oriented split. За цим профілем Hybrid 1
проходить H1-H3: не гірша test accuracy в межах 0.10 процентного пункту, на одну
ознаку менше за paired median і 55.5% менше logical NFE до primary validation
target.

Corrected applied профіль використовує офіційні raw UCI train/test, вилучає
instance-weight raw index 24 із predictors, має 40-бітну маску, передає ваги до
навчання та метрик, оптимізує weighted balanced accuracy і змінює
train/validation split у 30 paired seeds. У цьому профілі Hybrid H1 не проходить
preregistered non-inferiority margin:

```text
Hybrid H1 - corrected OLD paired median: -0.3580 percentage point
95% BCa: [-0.6932, -0.2159] percentage point
margin: -0.10 percentage point
```

Reset/no-reset Census ablation виконав reset у 30/30 runs, але дав
`NO_CLEAR_EFFECT` на офіційному test-файлі.

Основні матеріали:

- [`candidates/EU26-21/README.md`](candidates/EU26-21/README.md)
- [`candidates/EU26-21/hybrid_1/RESULTS.md`](candidates/EU26-21/hybrid_1/RESULTS.md)
- [`candidates/EU26-21/corrected_applied/RESULTS.md`](candidates/EU26-21/corrected_applied/RESULTS.md)
- [`candidates/EU26-21/SCIENTIFIC_NOVELTY_AND_CLAIMS.md`](candidates/EU26-21/SCIENTIFIC_NOVELTY_AND_CLAIMS.md)

Канонічні контрольні workflow:

- `.github/workflows/eu26-21-corrected-secure-reaggregate.yml`
- `.github/workflows/eu26-21-code-quality.yml`

Жоден негативний або нульовий науковий результат не перейменовується на PASS.
Merge у цьому етапі не виконується.

## Попередній adaptive-GA аудит

Аудит 15 post-2020 кандидатів і послідовне виконання двох допустимих
`hard_pass` завершено 30 липня 2026 року. Обидві числові реплікації того етапу
не пройшли preregistered published-result gate після трьох source-grounded
diagnostics кожна. Тому success-only fixed-GA comparison, ablations, 18-sheet
workbook і повний reproducibility package для тих кандидатів не створювалися.

- Канонічний реєстр: [`registry/README.md`](registry/README.md)
- Рейтинг і execution outcomes:
  [`registry/attempt_outcomes.md`](registry/attempt_outcomes.md)
- Загальний failure log:
  [`failure_logs/Failure_Log.csv`](failure_logs/Failure_Log.csv)
- Детальний USA-001 audit:
  [`failure_logs/USA-001_primary_failure.md`](failure_logs/USA-001_primary_failure.md)
- Загальний етап і відкриті питання:
  [`RESEARCH_STATUS.md`](RESEARCH_STATUS.md)

Failed-candidate directories попереднього етапу видалено лише після зовнішнього
логування. EU26-21 є окремим наступним активним дослідженням і не змінює
зафіксовані outcomes попереднього аудиту.

## Швидка prospective-перевірка

Machine-aware staged harness для майбутніх допущених реплікацій описано в
[`verification/README.md`](verification/README.md). Він використовує до чотирьох
process-workers, зберігає SHA-256-verified checkpoints у `tempdir` і припиняє
обчислення після definitive failure на незворотному published milestone, не
змінюючи run IDs, три algorithmic RNG streams, tolerances або повний budget
на шляху, який пройшов qualification. Окремий `analysisSeed` лишається
non-algorithmic metadata з retained ledger.

Основні команди MATLAB:

```matlab
cd verification
run_fast_verification_tests
verify_retained_evidence
analyze_historical_runtime
run_fast_verification_demo(true)
```

Попередній MATLAB-проєкт **NMGA Strong Source Location** перенесено без змін до
[`old/research/nmga-strong-source/`](old/research/nmga-strong-source/), оскільки
він є архівним дослідженням і не повинен змішуватися з наступною активною
реплікацією.

## Архівний NMGA-проєкт

Опис джерела та обмежень відтворення розміщено в
[`old/research/nmga-strong-source/docs/article-summary.md`](old/research/nmga-strong-source/docs/article-summary.md).
Архівні точки запуску:

- `old/research/nmga-strong-source/main.m`;
- `old/research/nmga-strong-source/run_article_exact_reproduction.m`.

Для запуску архівної реалізації перейдіть у її каталог у MATLAB, щоб відносні
шляхи до `src` обчислювалися від кореня цього проєкту:

```matlab
cd old/research/nmga-strong-source
main
```

Згенеровані результати в каталогах `sandbox/results/` не відстежуються Git.
