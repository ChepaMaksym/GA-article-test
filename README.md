# GA Article Test

## Поточний adaptive-GA аудит

Аудит 15 post-2020 кандидатів і послідовне виконання двох допустимих
`hard_pass` завершено 30 липня 2026 року. Обидві числові реплікації
не пройшли preregistered published-result gate після трьох
source-grounded diagnostics кожна. Тому success-only fixed-GA
comparison, ablations, 18-sheet workbook і повний reproducibility
package не створювалися.

- Канонічний реєстр: [`registry/README.md`](registry/README.md)
- Рейтинг і execution outcomes:
  [`registry/attempt_outcomes.md`](registry/attempt_outcomes.md)
- Загальний failure log:
  [`failure_logs/Failure_Log.csv`](failure_logs/Failure_Log.csv)
- Детальний USA-001 audit:
  [`failure_logs/USA-001_primary_failure.md`](failure_logs/USA-001_primary_failure.md)
- Поточний етап і відкриті питання:
  [`RESEARCH_STATUS.md`](RESEARCH_STATUS.md)

Failed-candidate directories видалено лише після зовнішнього логування.
У корені репозиторію немає активної candidate implementation.

## Швидка prospective-перевірка

Новий machine-aware staged harness для майбутньої допущеної реплікації описано в
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
