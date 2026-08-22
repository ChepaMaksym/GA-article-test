# Магістерська робота — робочий академічний рукопис

## Робоча назва

**Самоадаптивне керування параметрами багатоцільових еволюційних алгоритмів: відтворення GSEMO та контрольована гібридизація механізмів адаптації**

> Статус документа: робочий рукопис. Числові твердження для HYBRID v3 мають бути перенесені до фінальної редакції лише після завершення незалежного holdout. Негативні результати v1/v2 є остаточними для відповідних зафіксованих протоколів і не можуть бути переписані наступними ітераціями.

---

## Анотація

У роботі досліджується відтворюваність і контрольована модифікація самоадаптивних механізмів у багатоцільових еволюційних алгоритмах на прикладі Global Simple Evolutionary Multi-objective Optimizer (GSEMO). Вихідною точкою є дослідження Furong Ye та співавторів, у якому аналізуються адаптивні схеми мутації для GSEMO на класичних псевдобулевих задачах та використовуються показники якості множини Парето, зокрема hypervolume, для керування адаптацією.

Першим внеском цієї роботи є побудова fail-closed процедури відтворення вихідного алгоритму. Для конфігурації OneMinMax з розмірністю `n=100`, TwoRate, `lambda=10` та початковою ймовірністю мутації `1/n` було відтворено не лише агреговане середнє, а повну матрицю перших досягнень 101 точки фронту Парето у 100 авторських запусках. Відтворений результат має середнє 61 623.78 function evaluations (FE), медіану 57 717.5 FE та нуль розбіжностей із автентифікованим еталонним артефактом на рівні матриці і вектора кінцевих FE.

Другим внеском є експериментальна перевірка гібридних схем, у яких оригінальна TwoRate-адаптація mutation-rate не переписується, а доповнюється окремим контролером кількості offspring `lambda`. Перша схема використовувала one-fifth-inspired multiplicative control із reset; вона не підтвердила покращення: paired median relative FE reduction становила -20.237%, 95% bootstrap interval [-32.412%, +4.935%]. Друга схема застосовувала baseline-preserving rollback control; її primary effect становив +1.575%, але 95% interval [-14.391%, +19.146%] перетнув нуль, тому гіпотеза також була відхилена. Ці негативні результати збережено як самостійні наукові результати, а не використано для post-hoc зміни критеріїв успіху.

Третій внесок — методологія розділення development і confirmatory evaluation для наступного етапу. Відомий незалежний ledger v2 використовується лише як development set для детермінованого вибору верхньої межі `lambda` з наперед зафіксованої множини, після чого остаточна оцінка виконується на новому незалежному holdout. Такий дизайн зменшує ризик outcome-informed tuning та дозволяє відокремити інженерний пошук конфігурації від статистичного підтвердження.

Ключовий методологічний висновок роботи полягає в тому, що успішна реплікація baseline і коректна реалізація адаптивного механізму не гарантують статистично підтвердженого покращення. Для самоадаптивних MOEA необхідні точне збереження provenance, paired experimental design, незалежні seed ledgers, явні ablations і попередньо визначені критерії прийняття гіпотез.

**Ключові слова:** genetic algorithm, multi-objective optimization, GSEMO, parameter control, self-adaptation, mutation rate, population size, one-fifth rule, rollback, reproducibility, hypervolume, bootstrap.

---

# Вступ

## Актуальність

Еволюційні алгоритми широко застосовуються до задач, у яких простір пошуку є великим, дискретним або нелінійним, а похідні цільової функції недоступні. У багатоцільовій оптимізації складність зростає через необхідність одночасно наближати множину компромісних рішень. Параметри еволюційного алгоритму — імовірність мутації, розмір offspring population, selection pressure та інші — істотно впливають на швидкість збіжності та різноманітність популяції.

Статичні параметри є простими для відтворення, але часто не відповідають різним фазам пошуку. Тому важливим напрямом є parameter control: параметр змінюється під час виконання відповідно до стану пошуку або результативності останніх кроків. У багатоцільовому випадку ця задача складніша, оскільки поняття «успіху» має враховувати множину недомінованих рішень, а не одну скалярну fitness value.

Окремою проблемою є відтворюваність. Невелика розбіжність у random number generation, порядку оновлень, force-flip semantics, stopping condition або interpretation of function evaluations може змінити stochastic runtime distribution. Якщо новий контролер порівнюється з неточно відтвореним baseline, спостережуваний ефект може бути наслідком implementation drift, а не алгоритмічної модифікації.

Ця робота поєднує дві задачі: спочатку відтворити baseline на рівні raw stochastic evidence, а потім виконати контрольовану гібридизацію без зміни вихідного mutation controller.

## Мета роботи

Метою є **дослідити, чи може додаткове самоадаптивне керування offspring population size покращити evaluation efficiency відтвореного TwoRate GSEMO без зміни його вихідної mutation-rate adaptation, та сформувати відтворювану методологію перевірки таких модифікацій**.

## Завдання

1. Автентифікувати вихідний код, dependency revision та результатний артефакт базового дослідження.
2. Відтворити paper-compatible OLD configuration для OneMinMax `n=100`.
3. Перевірити baseline не лише за mean/median, а за повною first-hit matrix фронту Парето.
4. Визначити інваріантну частину алгоритму, яка не змінюється під час гібридизації.
5. Реалізувати адаптивні `lambda` controllers як additive extensions до TwoRate GSEMO.
6. Для кожної confirmatory iteration наперед зафіксувати seed ledger, metric, statistical test та acceptance criterion.
7. Зберігати negative results і ablations без post-hoc relabeling.
8. Розділити development і independent confirmation для параметризованої v3 family.
9. Оцінити загрози валідності та межі узагальнення результатів.
10. Сформувати reproducibility package, придатний для повторної перевірки числових висновків.

## Об'єкт і предмет дослідження

**Об'єкт дослідження:** багатоцільові еволюційні алгоритми для дискретних псевдобулевих задач.

**Предмет дослідження:** самоадаптивне керування mutation rate і offspring population size у GSEMO та його вплив на кількість function evaluations до повного знаходження фронту Парето.

## Методи

Використано аналіз наукових публікацій, source-level reproducibility audit, deterministic provenance checks, stochastic paired experiments, exact raw-output comparison, bootstrap confidence intervals, ablation studies, regression testing та CI-based fail-closed execution.

## Наукова новизна — коректне вузьке формулювання

У роботі **не** заявляється перший adaptive-`lambda` MOEA: one-fifth-inspired dynamic `lambda` для `(1+(lambda,lambda))` Global SEMO вже досліджувався Doerr, El Hadri та Pinard.

Новизна цієї роботи полягає у:

1. експериментальному поєднанні **точно відтвореної TwoRate mutation adaptation GSEMO** з окремим success-based controller для offspring population size;
2. збереженні mutation-control law як експериментального інваріанта, що дозволяє локалізувати зміну на рівні `lambda`;
3. використанні exact raw first-hit reproduction baseline як обов'язкового regression gate перед кожною hybrid evaluation;
4. побудові послідовності preregistered negative/positive tests із незалежними seed ledgers;
5. розділенні development-selection і independent confirmatory holdout для controller family.

## Практичне значення

Результатом є reusable pipeline для перевірки адаптивних MOEA, у якому нова модифікація не може перейти до статистичного evaluation, доки базова реалізація не пройде exact source-native regression. Підхід може бути використаний у подальших роботах, де необхідно відрізнити algorithmic effect від implementation drift.

---

# 1. Аналіз предметної області

## 1.1. Багатоцільова оптимізація та фронт Парето

Нехай задано вектор цільових функцій

`F(x) = (f1(x), ..., fk(x))`.

У загальному випадку не існує одного рішення, яке одночасно оптимізує всі компоненти. Рішення `x` домінує `y`, якщо воно не гірше за всіма цілями і строго краще хоча б за однією. Множина недомінованих objective vectors утворює Pareto front.

Для OneMinMax бітовий рядок довжини `n` оцінюється двома конфліктними цілями — кількістю одиниць і кількістю нулів. Для `n=100` повний фронт містить 101 objective point. Це робить задачу зручною для runtime experiments: завершення можна визначити точно як перший момент, коли знайдено всі 101 точки.

## 1.2. GSEMO

Global Simple Evolutionary Multi-objective Optimizer підтримує archive недомінованих рішень. На кожній ітерації батьківське рішення вибирається з поточного archive, генерується мутований кандидат, після чого archive оновлюється відповідно до dominance relation.

Простота GSEMO робить його корисним для теоретичного й емпіричного аналізу parameter control. Водночас навіть для цього алгоритму stochastic trajectory суттєво залежить від mutation distribution, archive size, selection process та порядку random draws.

## 1.3. Самоадаптація mutation rate

Робота Ye et al. досліджує кілька self-adaptive mutation schemes для GSEMO та використовує multi-objective performance metrics, серед яких hypervolume та inverted generational distance. Для TwoRate offspring поділяються між двома mutation regimes, а state parameter `r` змінюється залежно від якості кандидатів.

Для нашого експерименту важливо, що TwoRate law не переписується. Hybrid controller викликається поверх нього і змінює іншу величину — кількість offspring у наступному поколінні.

## 1.4. One-fifth rule і dynamic population size

У single-objective evolutionary computation multiplicative success-based updates використовуються для adaptation of population size. Узагальнено, після success параметр зменшується, а після failure збільшується з таким співвідношенням множників, щоб підтримувати певну цільову success frequency.

Doerr, El Hadri та Pinard перенесли ключовий механізм `(1+(lambda,lambda))` GA до multi-objective Global SEMO та запропонували one-fifth-inspired dynamic parameter setting. Для OneMinMax вони отримали теоретичну асимптотичну перевагу над classic GSEMO. Це є важливим prior art і визначає межу claim novelty цієї роботи.

## 1.5. Rollback modification

Bassin і Buzdalov показали, що one-fifth population-size control може бути шкідливим на задачах, де assumptions of the adaptation mechanism виконуються погано: `lambda` може зростати занадто агресивно і витрачати evaluations. Запропонований ними rollback mechanism призначений для зменшення негативного ефекту таких невдалих growth episodes.

Ця ідея мотивувала HYBRID v2, але сама наявність теоретично або емпірично обґрунтованого controller не означає, що він покращить конкретну TwoRate GSEMO configuration. Саме тому v2 був перевірений незалежним paired holdout.

---

# 2. Методологія відтворення baseline

## 2.1. Принцип artifact-first

До реалізації HYBRID було встановлено exact revision source code і dependency. Використання рухомої `main` branch або сучасної dependency version не допускалося, оскільки це створює неконтрольований semantic drift.

Зафіксовано:

- GSEMO revision: `fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380`;
- IOHexperimenter revision: `f223c682dff0749067d00b870f83ad754f7d96f5`;
- audited blob `src/gsemo.hpp`: `2693144bcfccff902343a02c6c8e48d7dd263257`;
- audited blob `src/main.cpp`: `22025e4680da85c98e3bb5ea30db8334ca25dff3`.

## 2.2. Canonical OLD configuration

Для primary baseline використано:

- problem: OneMinMax;
- dimension: `100`;
- adaptation: `TwoRate`;
- offspring population size: `10`;
- starting mutation parameter: `1/n`;
- adaptation metric: hypervolume;
- runs: 100 для canonical replay;
- stopping: до повного front completion із non-binding safety cap.

Safety cap не трактується як paper parameter; він лише запобігає нескінченному виконанню і суттєво перевищує максимальний авторський endpoint.

## 2.3. Exact first-hit verification

Агрегованого збігу mean недостатньо: дві різні stochastic distributions можуть випадково мати однакові середні. Тому для кожного з 100 runs та кожної з 101 Pareto points визначено first-hit FE.

Отримана `101 x 100` matrix порівнювалася cell-by-cell з еталонним Zenodo artifact.

Результат canonical OLD:

```text
complete source runs: 100/100
paper/Zenodo mean FE: 61623.78
source mean FE: 61623.78
reference median FE: 57717.5
source median FE: 57717.5
matrix mismatches: 0
endpoint mismatches: 0
```

Таким чином, hybrid experiments стартують не з приблизного clean-room baseline, а з source-native implementation, яка відтворює raw reference exactly.

---

# 3. Проєктування гібридного алгоритму

## 3.1. Експериментальний інваріант

У всіх HYBRID variants зберігаються:

- problem representation;
- objective functions;
- archive/dominance semantics;
- parent selection;
- mutation mechanism;
- TwoRate update of `r`;
- random-number implementation;
- metric used by TwoRate;
- full Pareto completion endpoint.

Змінюється тільки `lambda`, тобто кількість offspring у generation.

## 3.2. HYBRID v1 — one-fifth/reset

V1 використав multiplicative controller:

```text
L0 = 10
F = 1.5
Lmin = 1
Lmax = 100

success: L <- max(L/F, Lmin)
failure: L <- min(L*F^(1/4), Lmax)
at cap + failure in reset version: L <- Lmin
```

Success визначався як strict hypervolume improvement хоча б одним offspring.

Confirmatory seeds `27001..27030` були зафіксовані до outcomes.

## 3.3. HYBRID v2 — baseline-preserving rollback

Після негативного v1 була створена **нова** iteration, а не змінено acceptance threshold v1. V2 підняв lower bound до canonical OLD `lambda=10` та додав rollback state.

Primary variant:

```text
F = 1.5
U = 5
lambda_floor = 10
lambda_max = 100
Delta0 = 10
```

Secondary ablation `HYBRID_FLOOR` прибрала rollback і залишила лише baseline floor.

Confirmatory seeds `28001..28030` не перетиналися з v1.

## 3.4. HYBRID v3 — development-selected capped controller

Результат v2 показав, що `lambda` часто досягає 100. Це означає потенційно високу evaluation cost у failure streaks. Однак cap не можна вибирати на майбутньому test set.

Тому v3 застосовує двоступеневий design.

**Development family:**

```text
lambda_floor = 10
F = 1.5
lambda_cap in {15, 20, 30, 40, 60, 100}
```

Retired v2 seeds використовуються лише як development set. Для кожного cap обчислюється paired median relative FE reduction проти OLD. Вибирається найбільший score; при точній рівності — менший cap.

Після запису `selected_cap.json` запускається independent holdout `29001..29030`. Ці seeds не беруть участі у виборі cap.

---

# 4. Статистичний протокол

## 4.1. Чому paired design

Stochastic runtime має значну міжзапускову варіативність. Порівняння лише marginal medians може створювати хибне враження переваги. Тому для однакового seed OLD та HYBRID утворюють пару.

Для кожної пари:

`r_i = (FE_OLD_i - FE_HYBRID_i) / FE_OLD_i`.

Позитивне `r_i` означає меншу кількість FE у HYBRID.

Primary statistic — median of paired `r_i`.

## 4.2. Bootstrap interval

Для primary effect використовується paired bootstrap: resampling виконується над paired relative reductions, а не незалежно над двома marginal samples.

Для confirmatory experiments використовується 50 000 deterministic resamples з наперед зафіксованим bootstrap seed.

Гіпотеза про покращення вважається підтвердженою лише якщо lower endpoint 95% interval строго більший за zero та всі required runs завершили повний Pareto front.

## 4.3. Negative-result policy

Green CI означає лише те, що експеримент виконаний відповідно до protocol. Статус наукової гіпотези визначається окремим statistical gate.

Після FAIL:

- результат не перейменовується на PASS;
- acceptance threshold не змінюється;
- seed ledger не використовується повторно як «новий» confirmatory set;
- наступна модифікація є новою iteration з новим holdout.

---

# 5. Результати

## 5.1. Canonical OLD

Canonical replay повністю пройшов source-native gate. Exact matrix equality усуває одну з найважливіших confounders майбутнього hybrid comparison — невідомий baseline implementation error.

## 5.2. HYBRID v1

```text
OLD median FE:             55,425.0
HYBRID_RESET median FE:    62,489.0
HYBRID_NO_RESET median FE: 57,912.5

H1 paired median relative reduction: -20.237076%
95% CI: [-32.412176%, +4.934754%]
H1: FAIL

reset-specific median effect: -2.388751%
95% CI: [-15.523548%, +10.684546%]
H2: NO_CLEAR_EFFECT
```

V1 не лише не підтвердив improvement: point estimate primary comparison був негативним. Отже механічне перенесення success rule в новий algorithmic context не є достатнім.

## 5.3. HYBRID v2

```text
OLD median FE:             63,782.0
HYBRID_ROLLBACK median FE: 64,136.0
HYBRID_FLOOR median FE:    56,181.5

H1 paired median relative reduction OLD -> ROLLBACK: +1.575182%
95% CI: [-14.390699%, +19.145964%]
H1: FAIL

H2 rollback-specific paired median: -11.055069%
95% CI: [-21.663500%, +9.532151%]
H2: NO_CLEAR_EFFECT
```

Rollback був реально активним: median 55 rollback events/run, а median maximum observed lambda дорівнювала 100. Проте сам факт activation не створив statistically clear benefit.

Marginal median `HYBRID_FLOOR` був нижчим за OLD, але paired analysis на retired development data дав значно менший ефект, тому ця цифра не використовується як confirmatory claim. Вона лише мотивує вивчення evaluation-cost-aware cap.

## 5.4. HYBRID v3

**Статус у цьому revision:** confirmatory outcome ще не вставляється до рукопису до завершення незалежного workflow.

Після завершення PR #26 цей підрозділ має бути автоматично оновлений із:

- selected cap;
- development paired scores для всіх caps;
- OLD/V3 holdout median FE;
- paired H1 estimate;
- 95% bootstrap interval;
- PASS/FAIL;
- artifact SHA-256;
- raw evidence reference.

Незалежно від знаку результату, v3 не змінює вже зафіксовані висновки v1/v2.

---

# 6. Обговорення

## 6.1. Чому adaptation може не давати покращення

Більший `lambda` збільшує ймовірність отримати сильного кандидата в generation, але прямо збільшує кількість function evaluations. Якщо success signal не компенсує цю ціну достатньо часто, generation-level progress може виглядати кращим, а FE-to-completion — гіршим.

Друга проблема — interaction of controllers. TwoRate уже адаптує mutation regime. Додатковий lambda controller реагує на performance signal, який залежить від mutation adaptation. Тому два feedback loops можуть створювати надлишкову реакцію на одну й ту саму stochastic fluctuation.

Третя проблема — state dependence archive. Hypervolume improvement стає складнішим у різних фазах пошуку; однакова multiplicative rule може бути доречною на початку і надто дорогою наприкінці.

## 6.2. Значення негативних результатів

V1 і v2 показують, що науково відомий parameter-control mechanism не можна вважати transferable лише через його успіх в іншому алгоритмі. Негативний результат тут зменшує простір необґрунтованих claims і дає конкретну інформацію для design наступної family.

## 6.3. Reproducibility як частина algorithm design

Exact OLD regression перед кожним hybrid run перетворює reproducibility з одноразової підготовчої дії на постійний invariant experiment pipeline. Якщо additive patch випадково змінить OLD random stream або semantics, confirmatory evaluation не запускається.

---

# 7. Загрози валідності

## 7.1. Internal validity

Основний ризик — implementation drift. Він зменшується exact upstream hashes, blob checks, exact OLD regression і additive patching.

Інший ризик — outcome-informed tuning. V1/v2 seed ledgers retired після використання; у v3 v2 ledger явно позначений development-only, а confirmatory holdout створений окремо.

## 7.2. Construct validity

Primary efficiency metric — function evaluations до повного Pareto front. Це відповідає runtime objective для даного benchmark, але не тотожне wall-clock speed. Зміна `lambda` може впливати на можливість parallel execution, тому wall-clock results потребують окремого protocol.

## 7.3. External validity

Поточний primary benchmark — OneMinMax `n=100`. Навіть позитивний v3 не буде доказом universal superiority на LOTZ, COCZ або прикладних задачах. Після confirmatory success потрібні окремі generalization experiments.

## 7.4. Statistical conclusion validity

30 paired runs дають обмежену precision для heterogeneous effects. Тому висновок ґрунтується на interval, а не лише point estimate. Interval, що перетинає zero, трактується як відсутність confirmatory evidence, а не як доказ exact equality.

---

# 8. Reproducibility package

Для кожної iteration зберігаються:

- source/dependency revisions;
- source blob hashes;
- preregistration protocol;
- seed ledger;
- source patch;
- raw `.dat` outputs;
- stdout/controller traces;
- paired endpoint table;
- JSON statistical report;
- human-readable summary;
- CI workflow/run identity;
- artifact SHA-256.

Такий пакет дозволяє розрізнити три рівні evidence:

1. **source authenticity** — чи запускається саме зафіксований implementation;
2. **execution integrity** — чи відповідає run frozen protocol;
3. **statistical claim** — чи підтримують outcomes конкретну hypothesis.

---

# Висновки — робоча редакція

1. Вихідний TwoRate GSEMO для OneMinMax `n=100` відтворено exact на рівні повної first-hit matrix, а не лише агрегованого показника.
2. One-fifth/reset lambda control у v1 не підтвердив evaluation-efficiency improvement і мав негативний primary point estimate.
3. Baseline-preserving rollback у v2 також не підтвердив improvement; його interval був широким і перетинав zero.
4. Negative results збережено як immutable scientific outcomes відповідних frozen protocols.
5. Спостереження v2 мотивувало не post-hoc claim, а новий development/confirmation design v3.
6. Методологія показує необхідність exact baseline regression, paired stochastic comparison і незалежних seed ledgers при дослідженні parameter control.
7. Остаточний висновок щодо capped v3 буде сформульовано лише після незалежного `29001..29030` holdout.

---

# Положення, які можуть виноситися на захист

1. Fail-closed source-native regression до raw first-hit matrix є ефективним способом відокремити algorithmic modification від baseline implementation drift.
2. Перенесення success-based population-size adaptation до вже адаптивного MOEA не гарантує зменшення evaluation runtime, навіть якщо controller коректно реалізований та активується у всіх runs.
3. Development-selected parameter control має оцінюватися на незалежному holdout; використання того самого stochastic ledger і для selection, і для confirmation завищує доказову силу результату.
4. Негативні preregistered iterations є частиною наукового результату і повинні зберігатися разом із raw evidence та acceptance criteria.

---

# TODO до фінальної редакції

- [ ] імпортувати остаточний HYBRID v3 result із PR #26;
- [ ] якщо v3 H1 PASS — виконати multi-OS / worker / load verification і generalization experiments;
- [ ] якщо v3 H1 FAIL — зафіксувати negative result без зміни H1 та визначити, чи потрібна наступна development family;
- [ ] додати final figures з raw artifacts;
- [ ] додати таблицю всіх seed ledgers і artifact hashes;
- [ ] оформити бібліографію за вимогами університету;
- [ ] додати перелік скорочень;
- [ ] додати formal algorithm pseudocode;
- [ ] додати додаток із CI/provenance schema;
- [ ] узгодити назву, титульну сторінку та обсяг із формальними вимогами кафедри.
