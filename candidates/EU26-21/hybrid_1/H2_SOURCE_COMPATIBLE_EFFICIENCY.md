# H2 - пошукова ефективність Hybrid 1 у source-compatible профілі

## Академічне формулювання

> **H2. За незмінного source-compatible протоколу Hybrid 1 має вищу
> пошукову ефективність, ніж OLD CHC-QX, якщо він одночасно зберігає
> прогнозну якість у межах наперед установленої межі не-гіршості,
> не збільшує типову кількість вибраних ознак і досягає узгодженого
> рівня validation accuracy з меншою кількістю logical fitness
> evaluations.**

Термін **«вища пошукова ефективність»** у цій гіпотезі не означає вищу
точність. Він означає підтверджений багатокритеріальний компроміс:

```text
збереження якості
AND компактність підмножини ознак
AND економія logical NFE
```

Формально:

```text
H2 = H2a AND H2b AND H2c
```

## H2a - збереження прогнозної якості

Критерій:

```text
lower endpoint of paired 95% BCa
(Hybrid test accuracy - OLD test accuracy) >= -0.10 percentage point
```

Додатково не менше 24 із 30 Hybrid-запусків мають перевищувати
all-feature baseline щонайменше на 1.50 процентного пункту.

Фактичні дані:

| Показник | OLD CHC-QX | Hybrid 1 / парний ефект |
|---|---:|---:|
| Медіана test accuracy | 94.9367% | 94.9016% |
| Парна медіана Hybrid - OLD | - | -0.0263125 pp |
| 95% BCa | - | [-0.0676607; -0.0012530] pp |
| Межа не-гіршості | - | -0.10 pp |
| Запуски з приростом над all-feature baseline >=1.50 pp | - | 30/30 |

Рішення:

```text
H2a = PASS_CONFIDENCE_BOUND
```

Інтервал розташований нижче нуля, тому Hybrid 1 не доведено точнішим за
OLD. Підтримано тільки збереження якості в межах заздалегідь визначеної
межі.

## H2b - компактність підмножини ознак

Критерій:

```text
median(Hybrid selected features - OLD selected features) <= 0
```

Фактичні дані:

| Показник | Значення |
|---|---:|
| OLD median selected features | 5.5 |
| Hybrid median selected features | 5.0 |
| Парна медіана Hybrid - OLD | -1 feature |
| Hybrid вибрав менше ознак | 16/30 pairs |
| Однакова кількість | 7/30 pairs |
| Hybrid вибрав більше ознак | 7/30 pairs |

Рішення:

```text
H2b = PASS
```

Це описовий paired результат. Для sparsity не було зафіксовано окремого
confidence-bound критерію.

## H2c - економія logical NFE

Основний matched validation target:

```text
0.946
```

Критерії:

1. OLD і Hybrid досягають target щонайменше у 24 із 30 запусків;
2. coverage Hybrid не нижча за coverage OLD;
3. нижня межа paired 95% BCa для відносного скорочення NFE не менша
   за 20%.

Фактичні дані:

| Показник | OLD CHC-QX | Hybrid 1 |
|---|---:|---:|
| Target reached | 29/30 | 30/30 |
| Median capped logical NFE | 319.0 | 141.5 |
| Mean capped logical NFE | 391.97 | 228.00 |
| Hybrid faster | - | 26/30 pairs |

Парний ефект:

```text
median relative NFE reduction: 55.4990%
95% BCa: [34.9110%; 64.9701%]
restricted-mean reduction with censoring: 41.8318%
```

Рішення:

```text
H2c = PASS_CONFIDENCE_BOUND
```

Нижня межа 34.91% перевищує наперед установлений критерій 20%.

## Підсумкове рішення H2

Усі три складові пройдено:

```text
H2a quality preservation = PASS_CONFIDENCE_BOUND
H2b subset compactness   = PASS
H2c logical NFE economy  = PASS_CONFIDENCE_BOUND
```

Отже:

```text
H2 = SUPPORTED_SOURCE_COMPATIBLE_ONLY
```

Коректне формулювання висновку:

> **У source-compatible профілі Hybrid 1 продемонстрував вищу пошукову
> ефективність за OLD CHC-QX: за підтвердженої не-гіршості test accuracy
> в межі 0.10 процентного пункту він вибирав на одну ознаку менше за
> парною медіаною та досягав validation target 0.946 з медіанним
> скороченням logical NFE на 55.5%; нижня межа 95% BCa для скорочення
> становила 34.9%.**

## Межі твердження

H2 підтримано **лише для source-compatible профілю**. Воно не означає,
що:

- Hybrid 1 має вищу test accuracy;
- позитивний висновок переноситься до corrected official-UCI профілю;
- весь виграш NFE спричинений тільки reset-переходом;
- logical NFE дорівнює пропорційному wall-clock прискоренню;
- результат узагальнюється на інші datasets або classifiers.

У corrected official-UCI профілі C-H1 має статус
`FAIL_NONINFERIORITY`, тому H2 не можна використовувати як загальний
прикладний висновок поза source-compatible умовами.

## Походження даних

```text
immutable paired seed run: 31934321927
corrected aggregation run: 31934816828
final artifact id: 9260332711
artifact SHA-256:
8efc217b690f1c3e6698cb9aa0f55207d93f10e6390087c6e9f425d935bea21a
seed ledger: 1..30
```
