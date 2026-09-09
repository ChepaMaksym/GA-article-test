# EU26-21: CHC-QX, дані Census-Income та Hybrid 1

## Поточний стан

Нижче наведено незмінені машинні статуси перевірок. Їхню інтерпретацію
подано після блоку.

```text
OLD public-source reproduction: PASS_SOURCE_NUMERIC_ALIGNMENT
Hybrid 1 core and mechanism verification: PASS
Source-compatible paired Census H1-H2-H3: PASS_EXTENDED_30_SEED_H1_H2_H3
Corrected official-UCI protocol: PASS_PROTOCOL_RESULTS_AVAILABLE
Corrected C-H1: FAIL_NONINFERIORITY
Corrected C-H2: BLOCKED_BY_H1
Corrected C-H8 reset ablation: NO_CLEAR_EFFECT
Common-objective bridge: PASS_STRICT_EVIDENCE_VALIDATION_30_PAIRS
Bridge quality: FAIL_NONINFERIORITY
Bridge efficiency and sparsity claims: BLOCKED_BY_QUALITY_NONINFERIORITY
PR state: open draft, not merged
```

У дослідженні EU26-21 завершено три експерименти за різними протоколами.
Вони відповідають на різні наукові питання, тому їхні результати
розглядають окремо.

Третій, гармонізований протокол
[`common_bridge/PROTOCOL.md`](common_bridge/PROTOCOL.md) зафіксовано до
отримання результатів для початкових значень генератора `41001..41030`.
У 30 парах порівняно CHC на основі зафіксованого авторського коду та
`(1+(lambda,lambda))` без скидання параметра. Обидва методи використовують
спільну процедуру оцінювання й рівно 400 викликів цільової функції на групу.
Це порівняння пошукових компонентів, а не повної процедури CHC-QX.

Збереження якості в межах допустимого погіршення (non-inferiority, NI)
не підтверджено. Медіана парної різниці зваженої збалансованої точності
(WBA) на тестовій вибірці становить -0.0001373392; довірчий 95% BCa-інтервал —
[-0.0020872605, 0.0015180741] за допустимої межі -0.001. Значення наведено
на шкалі 0–1. Додатна різниця валідаційної AUC є описовим результатом,
оскільки критерій якості не виконано. Непідтвердження гіпотези є
науковим результатом, а не збоєм CI.

Основні матеріали:
[український науковий звіт](common_bridge/THESIS_REPORT_UK.md),
[перевірений машинозчитуваний звіт](common_bridge/evidence/reaggregated-report.json),
[серія з 30 пар](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34233477859)
і [повторна агрегація незмінених даних](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34234286460).
Обидва історичні архіви перевірено й переагреговано окремо в
[запуску 34233480959](https://github.com/ChepaMaksym/GA-article-test/actions/runs/34233480959).

## Першоджерела

Прикладна основа базового методу OLD:

Mohammed Ghaith Altarabichi, Sławomir Nowaczyk, Sepideh Pashami, and Peyman
Sheikholharam Mashhadi, **Fast Genetic Algorithm for feature selection - A
qualitative approximation approach**, Expert Systems with Applications 211
(2023) 118528, DOI `10.1016/j.eswa.2022.118528`.

Теоретична основа керування параметрами Hybrid 1:

Mario Alejandro Hevia Fajardo and Dirk Sudholt, **Theoretical and Empirical
Analysis of Parameter Control Mechanisms in the `(1+(lambda,lambda))` Genetic
Algorithm**, ACM Transactions on Evolutionary Learning and Optimization 2(4),
DOI `10.1145/3564755`.

Відповідність між друкованим описом і відкритим кодом установлено
не повністю. Історичний базовий метод OLD визначено перевіреною,
зафіксованою версією відкритої реалізації CHC-QX.

## Протокол A: відтворення й порівняння за умов вихідної реалізації

Протокол зберігає закодовані дані Census з авторської реалізації,
історичне 41-бітне подання, поділ 60/20/20, звичайну точність
класифікації як цільову функцію та поведінку відкритого коду CHC.
Надалі цей протокол позначено як source-compatible.

Зафіксований репозиторій і коміт:

```text
Ghaith81/Fast-Genetic-Algorithm-For-Feature-Selection
commit 6ac5a7ec77f8a7c096ab4d019254fcc897988fd6
```

Hybrid 1 замінює лише оптимізатор бінарної маски ознак на
самоналаштовуваний пошук `(1+(lambda,lambda))` зі скиданням параметра:

```text
m = round_half_up(lambda)
p = lambda/41
c = 1/lambda
strict success -> shrink
failure -> grow by F^(1/4)
failure at lambda=41 -> reset to 1
```

Цільову функцію порівнюють лексикографічно:

```text
(validation accuracy, -selected_feature_fraction)
```

Якість має пріоритет; кількість ознак враховують лише за однакової якості.

### Перевірки механізмів

Результати перевірки на Jump:

```text
reset successes: 27/50
no-reset successes: 8/50
difference: +38 percentage points
success ratio: 3.375x
solved-run median NFE with reset: 32.1% lower
```

Перевірки на OneMax також пройдено. За 1, 2 та 4 паралельних виконавців
підтверджено точний збіг сигнатур наукових результатів.

### Перевірка H1–H3 за 30 парних початкових значень генератора

Наперед зафіксований парний протокол:

- початкові значення генератора `1..30`;
- активна вибірка з 14 964 спостережень;
- 50 однакових початкових масок у кожній парі OLD/Hybrid;
- бюджет H1 — 400;
- бюджет і межа цензурування H3 — 2 500;
- цільові значення валідаційної якості — 0.945, 0.946 та 0.947;
- основне цільове значення — 0.946;
- облік логічних викликів цільової функції (NFE);
- 50 000 відтворюваних бутстреп-реплік BCa для медіани парних різниць.

H1:

```text
OLD median test accuracy: 94.9367%
Hybrid median test accuracy: 94.9016%
paired median Hybrid - OLD: -0.0263 percentage point
95% BCa: [-0.0677, -0.0013] percentage point
margin: -0.10 percentage point
result: PASS_CONFIDENCE_BOUND
```

Результат підтверджує NI в межах історичного протоколу, але не вищу точність.

H2:

```text
OLD median features: 5.5
Hybrid median features: 5.0
paired median difference: -1 feature
result: PASS
```

H3 за цільової валідаційної якості 0.946:

```text
OLD reached: 29/30
Hybrid reached: 30/30
OLD median capped NFE: 319.0
Hybrid median capped NFE: 141.5
paired median relative reduction: 55.50%
95% BCa: [34.91%, 64.97%]
result: PASS_CONFIDENCE_BOUND
```

Логічні NFE — це виклики обгорткової цільової функції, а не час виконання.
Порівнюються пошукові компоненти в цілому. Скидання параметра не
визначено як єдину причину відмінності.

Зафіксовані матеріали протоколу, сумісного з вихідною реалізацією:

```text
30-seed run: 31934321927
corrected aggregation run: 31934816828
final artifact: 9260332711
artifact SHA-256: 8efc217b690f1c3e6698cb9aa0f55207d93f10e6390087c6e9f425d935bea21a
```

Під час виправлення агрегації жодного запису окремого запуску не
створювали повторно.

## Протокол B: виправлена прикладна перевірка на офіційних даних UCI

Цей протокол усуває частину обмежень прикладної обґрунтованості
історичного експерименту:

- офіційний вихідний файл `census-income.data` використовують для
  розроблення моделей;
- офіційний файл `census-income.test` є відкладеною фінальною тестовою вибіркою;
- стовпець ваг спостережень з індексом 24 виключено з маски предикторів;
- простір пошуку містить 40 предикторних бітів замість 41 входу;
- ваги спостережень застосовують під час навчання й обчислення зважених показників;
- основною цільовою функцією стала WBA замість звичайної точності;
- використано 30 стратифікованих поділів на навчальну й валідаційну частини,
  різних між парами;
- варіанти зі скиданням і без скидання параметра порівнюють на Census
  послідовно, за однакового бюджету.

Основні параметри протоколу:

```text
training rows: 199,523
held-out test rows: 99,762
predictive dimension: 40
primary metric: weighted balanced accuracy
C-H1 non-inferiority margin: -0.10 percentage point
bootstrap: paired median BCa, 50,000 resamples
```

Хеші файлів даних:

```text
train: 3676a81db7d3528f3f8b9f3c699d0f0aa28db45e6e994fa0b8ed38327539ee86
test: 98402b1ab879573d0a7f38a699a40258080e25e33d3401e7bf9c96d3fa0fab8c
```

Зафіксовані матеріали перевірки:

```text
secure matrix run: 32049437836
source artifact: 9297184026
artifact SHA-256: 13d2f691eefb46067d3cdffbad4c22c032c429ce91600a33addbd3f5887bbdeb
seed rows: 30/30
```

### C-H1 за виправленим протоколом

```text
Hybrid H1 - corrected OLD paired median: -0.3580 percentage point
95% BCa: [-0.6932, -0.2159] percentage point
preregistered margin: -0.10 percentage point
result: FAIL_NONINFERIORITY
```

Увесь інтервал розташований нижче допустимої межі. Отже, виправлений
протокол не підтверджує NI для зваженої збалансованої точності.

### C-H2 за виправленим протоколом

```text
paired median Hybrid H1 - corrected OLD feature count: -1 feature
result: BLOCKED_BY_H1
```

Меншу кількість ознак наведено описово. Наперед визначений спільний
висновок про перевагу не допускається, оскільки критерій C-H1 не виконано.

### C-H8: перевірка внеску скидання параметра

```text
reset - no-reset paired median: 0.0000 percentage point
95% BCa: [0.0000, 0.0096] percentage point
runs with reset events: 30/30
total reset events: 49
result: NO_CLEAR_EFFECT
```

Скидання відбувалося в кожному запуску. Однак інтервал містить нуль,
тому чіткого додатного або від'ємного ефекту на офіційній тестовій
вибірці не встановлено.

## Узагальнена інтерпретація історичних протоколів A та B

Реалізація є відтворюваною й виконує критерії H1–H3 за історичним
протоколом, сумісним із вихідним кодом. За виправленим протоколом на
офіційних даних UCI з урахуванням ваг і 30 поділів вибірки Hybrid H1
не виконує наперед визначеного критерію NI для WBA. Медіана парної
різниці кількості ознак від'ємна, проте висновок про перевагу за цим
показником не допускається через невиконання C-H1. Скидання параметра
відбувалося, але його чіткого парного ефекту на офіційній тестовій
вибірці Census не встановлено.

Наявні результати не підтверджують вищої якості або NI за виправленим
протоколом, окремої переваги скидання на Census чи тотожності друкованого
Algorithm 1 і відкритого коду. Вони також не обґрунтовують універсальної
застосовності або скорочення часу виконання лише на підставі логічних NFE.

Новий гармонізований протокол розглянуто окремо на початку документа
та в [науковому звіті](common_bridge/THESIS_REPORT_UK.md). Наведені
історичні висновки не замінюють його результатів.

## Матеріали перевірки та навігація

Протокол, сумісний із вихідною реалізацією:

- `old/SOURCE_STATUS.md`;
- `old/PAPER_SOURCE_DIVERGENCES.md`;
- `hybrid_1/RESULTS.md`;
- `hybrid_1/EXTENDED_30_SEED_RESULTS.md`;
- `hybrid_1/TEST_AND_CI_AUDIT.md`.

Виправлений прикладний протокол:

- `corrected_applied/README.md`;
- `corrected_applied/METHODOLOGY_AMENDMENT.md`;
- `corrected_applied/RESULTS.md`;
- `corrected_applied/secure_cli.py`;
- `corrected_applied/secure_aggregate.py`;
- `corrected_applied/secure_plots.py`.

Основні процеси перевірки GitHub Actions:

- `.github/workflows/eu26-21-corrected-secure-reaggregate.yml`;
- `.github/workflows/eu26-21-code-quality.yml`.
