# NMGA Strong Source Location

MATLAB-проєкт для відтворення публічно описаного протоколу зі статті
**Application of New Modified Genetic Algorithm in Inverse Calculation of
Strong Source Location**.

- Стаття: https://www.mdpi.com/2073-4433/14/1/89
- DOI: https://doi.org/10.3390/atmos14010089
- Короткий огляд: [`docs/article-summary.md`](docs/article-summary.md)

## Призначення

Проєкт оцінює координати, інтенсивність і ефективну висоту сильного джерела за
концентраціями на датчиках. Пряма модель використовує Gaussian plume, а
обернена задача розв'язується MGA та NMGA з описаними у статті параметрами й
операторами.

Оригінальні концентрації та точні координати датчиків зі статті недоступні.
Тому локальні запуски використовують `synthetic_reproduction` і не заявляються
як точне відтворення авторської Table 1. Оригінального PDF статті в репозиторії
та його Git-історії немає; джерелом є офіційна сторінка MDPI.

## Структура

- `main.m` - швидкий article-aligned запуск із профілем `unit`.
- `run_article_exact_reproduction.m` - єдиний публічний runner.
- `src/data` - параметри статті та синтетичні спостереження.
- `src/models` - Gaussian plume model і objective.
- `src/optimization` - MGA/NMGA та article-aligned operators.
- `src/metrics` - похибки оцінювання джерела.
- `old` - непідтримувані бічні дослідження й попередні плани.

## Запуск

Швидка перевірка повного workflow:

```matlab
main
```

Публічно описаний протокол Table 1 з повною кількістю повторів:

```matlab
run_article_exact_reproduction('article_exact')
```

Повний профіль виконує `MGA 100 x 2000`, `NMGA 100 x 1000` і
`NMGA 100 x 500`, тому потребує значно більше часу. Результати створюються в
`sandbox/results` і не відстежуються Git.
