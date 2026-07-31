# Реєстр кандидатів adaptive GA

Ця папка містить об'єднаний реєстр 15 досліджень, сформований без послаблення жорстких критеріїв пошуку.

## Файли

- [`candidates.json`](./candidates.json) — плоский масив із 15 записів. Перші 7 записів точно походять із `candidates_eu.json`, наступні 8 — із масиву `candidates` у `candidates_us.json`. Після поглибленого аудиту синхронно оновлено EU-001, EU-002, EU-003, USA-001, USA-002, USA-003, USA-004 та умовний статус EU-006; усі інші записи збережено.
- [`candidates_eu.json`](./candidates_eu.json) — 7 кандидатів із принаймні однією кваліфікованою установою автора з ЄС.
- [`candidates_us.json`](./candidates_us.json) — 8 кандидатів із принаймні однією установою автора зі США.
- [`ranking.csv`](./ranking.csv) — рейтинговий список лише для допустимих `hard_pass`; недопустимі та умовні записи наведені окремим блоком `noneligible`.
- [`attempt_outcomes.md`](./attempt_outcomes.md) — результати послідовних спроб для обох ranked `hard_pass`, посилання на failure evidence та зафіксоване вичерпання реєстру без success-only workbook.
- [`re_audits/USA-002_no_go.md`](./re_audits/USA-002_no_go.md) — повторний аудит USA-002 з фіксованим commit/blob provenance, підрахунком рядків архіву та обґрунтуванням `hard_fail`.
- [`re_audits/EU-002_no_go.md`](./re_audits/EU-002_no_go.md) — повторний аудит EU-002 з хешами PDF, перевіркою формул/операторів/wing inputs, аналізом 5% цілі та обґрунтуванням `hard_fail`.
- [`re_audits/EU-003_no_go.md`](./re_audits/EU-003_no_go.md) — повторний аудит EU-003 з provenance законного full text, хешем audited corrected proof, перевіркою недоступних borehole inputs, суперечностей adaptive state machine та непридатності CI/SD/5% цілі.
- [`re_audits/USA-003_no_go.md`](./re_audits/USA-003_no_go.md) — повторний аудит USA-003 з хешем institutionally hosted PDF, license boundary, перевіркою request-only analytic inputs, operator/state ambiguities та непридатності reported CI/5% як equivalence gate.
- [`re_audits/USA-004_no_go.md`](./re_audits/USA-004_no_go.md) — повторний аудит USA-004 з хешем UCF-hosted PDF, ACM license boundary, split arithmetic, перевіркою відсутніх processed inputs/masks/seeds/operator semantics і непридатності figure-only CI/5% як equivalence gate.

## Фактичні кількості

| Регіон | Усі записи | Hard pass зі score | Conditional noneligible | Hard fail |
|---|---:|---:|---:|---:|
| USA | 8 | 1 | 2 | 5 |
| EU | 7 | 1 | 1 | 5 |
| Разом | 15 | 2 | 3 | 10 |

Початкова ціль 12–20 кандидатів та щонайменше по 5 первинних записів із USA і EU виконана. Однак повністю допустимих досліджень менше п'яти в кожному регіоні: 1 у USA і 1 у EU. Дефіцит становить чотири hard-pass для USA і чотири для EU.

Критерії не послаблювалися. Найчастіші причини недопуску:

- немає однозначно законного повного тексту саме потрібної публікації;
- фактичний оптимізований вектор має менше 11 decision variables;
- описана адаптація змінює surrogate/fitness model, а не GA hyperparameter або GA operator;
- критична формула, межі чи порядок адаптації відсутні або доступні лише через інше дослідження;
- немає достатніх даних, коду або параметрів для точного clean-room відтворення.

## Рейтинг допустимих кандидатів

| Rank | ID | Region | Score | Дослідження |
|---:|---|---|---:|---|
| 1 | EU-001 | EU | 79 | Adaptive Gene Level Mutation |
| 2 | USA-001 | USA | 77 | Calibration of an Adaptive Genetic Algorithm for Modeling Opinion Diffusion |

Оцінки **79** для EU-001 та **77** для USA-001 замінюють попередні скринінгові оцінки 92 і 81. Поглиблений аудит перевірив точні revision-и репозитаріїв, виконуваність driver-ів, ліцензійні межі, наявність raw outputs, paper/code розбіжності, baseline та ablation; тому саме ці нижчі значення є канонічними. Арифметика:

- EU-001: \(12+8+10+5+5+10+7+8+4+5+5=79\);
- USA-001: \(14+10+8+5+7+6+10+10+5+0+2=77\).

Повторний аудит USA-002 відкликав попередній score 77: оприлюднені CSV є неповними результатами, а не вхідними даними для повторного запуску; генератор, driver, seeds, матриці та analysis script відсутні. Повторний аудит EU-002 також відкликав score 67: Equation (10) не задає працездатної variance, параметр β суперечить сам собі, базові GA operators і wing inputs неповні, а жодна опублікована числова ціль не придатна для точного порогу ≤5%. Повторний аудит EU-003 відкликав score 56: стаття прямо забороняє публічний доступ до 70 borehole inputs, adaptive fractions/probabilities і stall triggers суперечать одне одному, custom operators відсутні, а seeds, raw runs, SD і CI не опубліковано. Повторний аудит USA-003 відкликав score 54: exact 40662-row table і splits доступні лише на запит, десять operator-argument mappings та boundary/self-mutation/multi-parent semantics відсутні, а code, seeds і raw 50-run values не оприлюднено. Повторний аудит USA-004 відкликав score 45: exact processed 40662×25 table відсутня, reported splits залишають 299 unexplained rows, 900 masks/seeds та executable SAGA semantics не опубліковані, а figure-only confidence bands не задають перевірюваної числової цілі. **EU-001 є єдиним кандидатом із найвищим score 79**, USA-001 посідає друге місце зі score 77.

На момент freeze рейтингу автоматично було обрано **EU-001, Adaptive Gene
Level Mutation**, score 79. Цей історичний вибір уже виконано; після його
невдачі також виконано fallback USA-001. Поточного кандидата для наступного
етапу в цьому cohort немає.

## Результат послідовного виконання

Обидва допустимі кандидати були виконані в рейтинговому порядку. EU-001
не пройшов кількісну перевірку published Table 1 після трьох
source-grounded diagnostics; USA-001 не пройшов published P2/P4 після
paper-faithful primary та трьох source-grounded diagnostics. Обидві
failed-candidate folders видалено лише після запису evidence. Інших
неперевірених `hard_pass` у реєстрі немає. Канонічний журнал результатів:
[`attempt_outcomes.md`](./attempt_outcomes.md).

Success-only fixed-GA comparison, ablations, 18-sheet Excel workbook та
повний reproducibility package не створювалися, оскільки жоден кандидат
не пройшов published-result gate.

## Недопустимі й умовні записи

| ID | Region | Status | Критична причина |
|---|---|---|---|
| USA-002 | USA | hard_fail | Архів містить неповні output CSV, але не rerunnable inputs; генератор, driver, seeds, матриці та analysis code відсутні, закон генерації ваг недовизначено, а paper/code semantics суперечать одна одній. |
| EU-002 | EU | hard_fail | Equation (10) непридатна без винайдення виправлення; entropy/normalizers і базові GA operators недовизначені, β=0.7 у тексті суперечить β=0.3 у Table 6, а wing vector/CFD inputs та надійна ≤5% ціль відсутні. |
| EU-003 | EU | hard_fail | Автори прямо вказують, що 70-borehole dataset не може бути публічним; 80/15/5 суперечить 85/10/5, every-five stalls суперечить stall=10, custom operators і stochastic provenance відсутні, тому CI/SD або ≤5% target неможливий без fabrication. |
| USA-003 | USA | hard_fail | Exact analytic table/splits є request-only; ten operator mappings, boundary/self-mutation/no-crossover/multi-parent semantics і source відсутні; reported CI не прив'язаний до reproducible pipeline, а ±5% band допускає nonadaptive baselines. |
| USA-004 | USA | hard_fail | Exact processed table відсутня; 20331+10016+10016=40363, що на 299 менше stated total; masks/seeds/operator state machine і raw outputs відсутні, а graphical CI та forced ±5% band не відрізняють faithful SAGA від baseline. |
| USA-005 | USA | conditional_noneligible | Адаптивний механізм не є самодостатньо описаним у цій статті й імпортується з попередньої роботи. |
| USA-006 | USA | conditional_noneligible | Не доведено щонайменше 11 активних route genes; формулу та межі dynamic-rate function пропущено. |
| EU-004 | EU | hard_fail | Немає однозначного законного повного тексту точної журнальної статті. |
| EU-005 | EU | hard_fail | Не підтверджено одночасно законний повний текст і точну розмірність `>=11`. |
| EU-006 | EU | conditional_noneligible | Не встановлено upstream license/provenance для кожного біомедичного датасету. Поглиблена оцінка 73/100 є лише provisional, `final_score=null`, кандидат не ранжується. |
| EU-007 | EU | hard_fail | Оптимізуються лише дві decision variables. |
| USA-007 | USA | hard_fail | Адаптується surrogate potential, а не параметр чи оператор GA; критичні artifacts відсутні. |
| USA-008 | USA | hard_fail | Адаптується surrogate potential, а не параметр чи оператор GA; критичні artifacts відсутні. |

## Формула score

Score обчислюється лише для `hard_pass` як сума 11 компонентів:

| Компонент | Максимум |
|---|---:|
| Повнота математичного опису | 15 |
| Повнота параметрів експерименту | 10 |
| Законна доступність даних | 10 |
| Random seeds і кількість запусків | 10 |
| Відкритий код | 10 |
| Якість ліцензії коду | 10 |
| Перевірюваність проміжних результатів | 10 |
| Повнота адаптивних параметрів | 10 |
| Зрозумілість порядку оновлення | 5 |
| Baseline GA | 5 |
| Ablation study | 5 |
| **Разом** | **100** |

Для `hard_fail` і `conditional_noneligible` поле `final_score` дорівнює `null`; такі записи не ранжуються. Зокрема, provisional 73/100 для EU-006 збережено лише як аудиторську довідку в [`top_candidate_audit.md`](./top_candidate_audit.md), а не як фінальний score.

## Схема та provenance

EU-записи мають 58 реєстрових полів плюс `score_breakdown`; USA-записи
мають 59 реєстрових полів плюс `score_breakdown`, оскільки додатково
містять `evidence_sources`. Щоб зберегти джерельні записи без перезапису,
регіональні назви деяких еквівалентних полів залишені як є:

- EU: `region_category`, `adaptation_timing`, `formula_pages_and_numbers`, `optimization_problem_type`, `eligibility_status`;
- USA: `geography_category`, `simultaneous_or_sequential`, `page_and_formula_number`, `optimization_task_type`, `compliance_status`.

Для побудови рейтингу статус нормалізується за кінцевим маркером `hard_pass`, `conditional_noneligible` або `hard_fail`; вміст реєстрового запису не змінюється.

## Перевірки

Після механічного злиття слід перевіряти:

1. `candidates.json` коректно парситься як JSON.
2. У масиві рівно 15 унікальних `candidate_id`.
3. Перші 7 об'єктів глибоко тотожні `candidates_eu.json`, а останні 8 — об'єктам `candidates_us.json`.
4. Кожен EU-запис має 58 реєстрових полів, кожен USA-запис — 59, і всі
   мають 11 score dimensions у `score_breakdown`.
5. Для кожного scored `hard_pass` сума score dimensions дорівнює `final_score`.
6. Для всіх інших записів `final_score` є `null`.
