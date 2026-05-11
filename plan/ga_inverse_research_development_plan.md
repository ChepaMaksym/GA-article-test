# Загальний шаблон дослідження: SAGA + GA

## 1. Призначення документа

Цей документ є загальним шаблоном для дослідження та реалізації **Self-Adaptive Genetic Algorithm (SAGA)**.

У межах цього шаблону дозволені тільки:

- класичний Genetic Algorithm (GA) як baseline;
- формальний Self-Adaptive Genetic Algorithm (SAGA).

Будь-які інші алгоритми, модифікації, гібриди або попередні контексти не входять до цього шаблону.

## 2. Формальне визначення

**Self-Adaptive Genetic Algorithm (SAGA)** — це підклас алгоритмів з області Evolutionary Computation, у якому керуючі параметри алгоритму включені до генотипу індивіда та еволюціонують разом із рішенням під дією стандартних операторів варіації.

## 3. Модель

Нехай індивід:

```text
I = (x, θ)
```

де:

- `x` — рішення;
- `θ` — вектор параметрів алгоритму.

Для SAGA `θ` не є глобальним налаштуванням запуску. `θ` є частиною індивіда, змінюється через оператори варіації та проходить selection разом із `x`.

## 4. Необхідні умови SAGA

### 4.1. Вбудованість

```text
θ ⊆ genotype
```

### 4.2. Спільна варіація

```text
(x, θ) --variation--> (x', θ')
```

### 4.3. Селекція

```text
selection(x, θ)
```

### 4.4. Відсутність зовнішнього оновлення параметрів

```text
θ не оновлюється зовнішніми правилами
```

## 5. Обмеження на параметри

Self-adaptation стосується лише базових параметрів алгоритму:

```text
θ ⊆ θ_base
```

де `θ_base` включає:

- ймовірність мутації;
- ймовірність кросоверу;
- параметри селекції;
- параметри операторів варіації.

Допоміжні або штучно введені параметри не враховуються:

```text
θ_aux ∉ criterion
```

До `θ_aux` належать:

- службові лічильники;
- logging flags;
- кількість сценаріїв;
- кількість seeds;
- runtime limits;
- назви режимів;
- пороги для звітності;
- будь-які параметри, які не є базовими параметрами GA.

## 6. Критерій SAGA

Алгоритм є SAGA тоді і тільки тоді, коли:

- `θ ∈ genotype`;
- `θ` змінюється через `variation`;
- `selection` діє на `(x, θ)`;
- `θ ⊆ θ_base`.

Якщо хоча б одна умова не виконується, алгоритм не є SAGA.

## 7. Негативні умови

Алгоритм не є SAGA, якщо:

- параметри не входять у генотип;
- параметри є глобальними;
- параметри змінюються зовнішніми правилами;
- змінюються лише допоміжні параметри;
- базові параметри залишаються сталими;
- `selection` відбирає тільки `x`, а не повний індивід `(x, θ)`;
- `θ` перепризначається після selection окремим правилом;
- `θ` використовується тільки для логування, але не бере участі у variation.

Заборонені як SAGA-механізм правила виду:

```text
Pm = f(generation)
Pm = f(stagnation)
Pc = f(diversity)
σ = f(progress)
```

Такі правила є не-SAGA логікою, якщо `θ` не входить у генотип і не змінюється через variation.

## 8. Дозволені режими

У цьому шаблоні є тільки два режими.

### 8.1. Класичний GA

Класичний GA використовується як baseline:

```text
I = x
Pm = constant
Pc = constant
selection_parameters = constant
variation_parameters = constant
```

Параметри GA задаються перед запуском і не входять у генотип.

### 8.2. SAGA

SAGA використовує індивіда:

```text
I = (x, θ_base)
```

Мінімальний приклад:

```text
I = (x, Pm, Pc, σ)
```

де:

- `Pm` — ймовірність мутації;
- `Pc` — ймовірність кросоверу;
- `σ` — сила або масштаб мутації.

## 9. Мета дослідження

Мета — реалізувати та перевірити SAGA у порівнянні з класичним GA за однакових умов.

Порівняння:

```text
classical GA vs SAGA
```

Основне питання:

```text
чи еволюція θ_base всередині генотипу покращує або стабілізує пошук без зовнішнього оновлення параметрів
```

## 10. Ресурси

### 10.1. Мінімальна структура

Шаблон реалізації має містити:

| Ресурс | Роль |
|---|---|
| `README.md` | короткий опис задачі, запуску та обмежень |
| `main.m` | основний запуск |
| `run_unit_tests.m` | запуск тестів |
| `run_reproduction.m` | запуск відтворення GA vs SAGA |
| `run_sandbox.m` | запуск sandbox-сценаріїв |
| `src/data/` | вхідні або синтетичні дані |
| `src/models/` | forward model та fitness |
| `src/optimization/` | GA та SAGA |
| `src/metrics/` | метрики |
| `tests/` | unit tests |
| `sandbox/results/` | звіти та `.mat` результати |

### 10.2. Зовнішні ресурси

Використовувати тільки легальні та відкрито доступні джерела:

- сторінка статті або технічного опису;
- DOI landing page, якщо є;
- офіційний PDF або HTML full text, якщо доступний;
- supplementary materials, якщо доступні;
- author-provided repository, якщо доступний;
- MATLAB documentation;
- офіційна документація MathWorks.

Не використовувати:

- paywall обходи;
- неофіційні копії;
- неперевірені дані;
- джерела без зрозумілого походження.

## 11. Пошук, free-view і download

Під час пошуку джерел застосовувати критерій:

```text
source can be freely viewed
AND source or metadata can be downloaded legally
AND enough algorithm details are available for SAGA/GA reproduction
```

Порядок пошуку:

1. Шукати джерело за точною назвою, DOI або ключовими словами.
2. Перевіряти офіційну сторінку видавця або автора.
3. Шукати PDF або HTML full text тільки з легальних джерел.
4. Перевіряти supplementary materials.
5. Шукати відкритий код або дані авторів.
6. Якщо raw data недоступні, позначати локальні сценарії як `synthetic_reproduction`.
7. Якщо доступний тільки abstract, не використовувати джерело як основну базу для відтворення.

Пошукові запити:

```text
"self-adaptive genetic algorithm" "genotype" "mutation probability"
"self-adaptive genetic algorithm" "crossover probability"
"genetic algorithm" "strategy parameters" "genotype"
"self adaptation" "genetic algorithm" "operator parameters"
"SAGA" "evolutionary computation" "parameter encoded"
```

Критерій включення джерела:

- є повний текст або достатньо деталей алгоритму;
- можна безкоштовно переглянути;
- можна легально завантажити PDF, HTML або metadata;
- описано GA або SAGA operators;
- є fitness або задача, яку можна відтворити.

Критерій виключення:

- джерело закрите paywall і немає легального full text;
- немає опису variation або selection;
- немає fitness або forward model;
- алгоритм не є GA або SAGA;
- алгоритм названий self-adaptive, але `θ` не входить у генотип.

## 12. MATLAB-частина

### 12.1. Робоче середовище

Шаблон орієнтований на MATLAB-запуск через:

```matlab
main
run_unit_tests
run_reproduction
run_sandbox
```

Batch-запуск:

```powershell
matlab -batch "main"
matlab -batch "run_unit_tests"
matlab -batch "run_reproduction"
matlab -batch "run_sandbox"
```

### 12.2. MATLAB-залежності

Бажаний формат — self-contained MATLAB-код без обов'язкових toolbox-залежностей.

Базово потрібні:

- MATLAB;
- стандартні MATLAB-функції для масивів і структур;
- `rng` для відтворюваності;
- `save` / `load` для `.mat` результатів;
- `fprintf` для Markdown-звітів;
- `mkdir` для створення `sandbox/results`;
- доступ на запис у теку результатів.

Не робити обов'язковими без окремої причини:

- Global Optimization Toolbox;
- Parallel Computing Toolbox;
- Statistics and Machine Learning Toolbox;
- Optimization Toolbox.

Якщо будь-яка toolbox-залежність все ж потрібна, її треба явно записати в:

- `README.md`;
- секцію dependencies;
- verification guide;
- повідомлення чат-бота перед запуском.

## 13. Відтворення

### 13.1. Дані

Дані мають бути чітко позначені:

```text
reported_data             -> значення, прямо взяті з відкритого джерела
synthetic_reproduction    -> локальні синтетичні сценарії
```

Не можна видавати synthetic sandbox за оригінальні авторські дані.

### 13.2. Порівняння

Порівнювати тільки:

```text
classical GA
SAGA
```

Умови мають бути однаковими:

- data;
- bounds;
- fitness;
- population size;
- max generations;
- number of seeds;
- number of scenarios;
- random seed policy.

## 14. Реалізаційний план

### Крок 1. Реалізувати класичний GA

Baseline:

```text
I = x
Pm = constant
Pc = constant
σ = constant
```

### Крок 2. Реалізувати SAGA-індивіда

Структура:

```text
individual.x
individual.theta.Pm
individual.theta.Pc
individual.theta.sigma
individual.fitness
```

### Крок 3. Ініціалізувати `θ`

```text
Pm ∈ [Pm_min, Pm_max]
Pc ∈ [Pc_min, Pc_max]
σ ∈ [σ_min, σ_max]
```

Межі задаються для експерименту, але самі значення `Pm`, `Pc`, `σ` живуть у генотипі.

### Крок 4. Оновити variation

Variation має діяти на весь індивід:

```text
variation(individual) -> child_individual
```

Очікувана дія:

```text
x -> x'
θ -> θ'
```

Після variation:

```text
x' clipped to problem bounds
θ' clipped to θ bounds
```

### Крок 5. Оновити selection

Selection має повертати повні індивіди:

```text
selected_individual = selection(population)
```

Заборонено:

```text
selected_x = selection(x_only)
θ = global_rule(...)
```

### Крок 6. Додати логування

Логувати:

```text
Pm_history
Pc_history
sigma_history
theta_population_history
theta_best_individual_history
best_fitness_history
generation_to_best
function_evaluations
```

## 15. SAGA Unit Tests

Тести мають перевіряти не лише результат, а й формальний статус алгоритму як SAGA.

Обов'язкові unit tests:

1. `individual contains x and theta`.
2. `theta contains only base GA parameters`.
3. `theta is not global`.
4. `variation receives complete individual`.
5. `variation changes x and may change theta`.
6. `theta mutation changes at least one theta value under controlled seed`.
7. `theta crossover can inherit theta from parents`.
8. `theta stays within configured bounds`.
9. `selection returns complete individuals`.
10. `selection does not recreate theta externally`.
11. `no generation-based theta update exists`.
12. `no stagnation-based theta update exists`.
13. `no diversity-based theta update exists`.
14. `same seed gives reproducible SAGA result`.
15. `SAGA output respects problem bounds`.
16. `SAGA logs theta history`.
17. `theta history length equals generation count`.
18. `best individual includes best x and best theta`.

Тести класичного GA:

1. `GA uses x-only genotype`.
2. `GA uses fixed mutation probability`.
3. `GA uses fixed crossover probability`.
4. `GA output respects problem bounds`.
5. `same seed gives reproducible GA result`.

Класифікаційний тест:

```text
if not satisfies_saga_criterion(algorithm):
    stop execution
    report: "Algorithm is not SAGA: θ is not encoded in genotype or is externally updated."
```

## 16. SAGA Sandbox

Sandbox має перевіряти SAGA у контрольованих сценаріях, а не доводити перевагу в кожному запуску.

### 16.1. Базові сценарії

```text
baseline_clean
baseline_low_noise
baseline_high_noise
small_population
large_population
short_run
long_run
tight_bounds
wide_bounds
```

### 16.2. Сценарії для `θ`

```text
narrow_theta_bounds
wide_theta_bounds
low_initial_mutation_probability
high_initial_mutation_probability
low_initial_crossover_probability
high_initial_crossover_probability
low_initial_mutation_strength
high_initial_mutation_strength
```

### 16.3. Сценарії стійкості

```text
flat_fitness_region
noisy_fitness
multimodal_fitness
shifted_optimum
boundary_optimum
ill_scaled_variables
```

### 16.4. Обов'язкові sandbox checks

Кожен sandbox-запуск має перевіряти:

- SAGA не порушує bounds для `x`;
- SAGA не порушує bounds для `θ`;
- `θ` змінюється через variation;
- `θ` не оновлюється зовнішнім правилом;
- `selection` переносить `(x, θ)` разом;
- `Pm_history`, `Pc_history`, `sigma_history` записані;
- `theta_best_individual_history` записаний;
- final fitness є скінченним;
- repeated seeds мають відтворювану поведінку;
- GA і SAGA використовують однакові data, bounds і budget.

### 16.5. Sandbox failure policy

Sandbox вважається failed, якщо:

- `θ` не входить у генотип;
- `θ` глобальний;
- `θ` змінюється через generation/stagnation/diversity rule;
- `θ` не змінюється через variation;
- selection працює тільки з `x`;
- logs не дозволяють перевірити журнал змін `θ`;
- SAGA використовує інший fitness або інший budget, ніж GA.

У разі failure чат-бот має зупинити роботу й написати повідомлення:

```text
Роботу зупинено: алгоритм не проходить критерій SAGA. Причина: <конкретна причина>.
```

## 17. Метрики

### 17.1. Метрики точності

```text
final_fitness
best_fitness
error_to_known_solution
RMSE
MAE
success_rate
```

### 17.2. Метрики швидкості

```text
runtime_seconds
generation_to_best
generation_to_threshold
function_evaluations
```

### 17.3. Метрики self-adaptation

```text
Pm_history
Pc_history
sigma_history
theta_variance_history
theta_best_individual_history
theta_population_history
```

Головна метрика SAGA — не просто кращий fitness, а доказ, що `θ_base` був у генотипі, змінювався через variation і проходив selection разом із `x`.

## 18. Таблиці звіту

### 18.1. Таблиця точності

| Method | Mean error | Std error | Best | Worst | Success rate |
|---|---:|---:|---:|---:|---:|
| Classical GA | ... | ... | ... | ... | ... |
| SAGA | ... | ... | ... | ... | ... |

### 18.2. Таблиця швидкості

| Method | Mean runtime | Mean generations | Function evaluations | Generation to threshold |
|---|---:|---:|---:|---:|
| Classical GA | ... | ... | ... | ... |
| SAGA | ... | ... | ... | ... |

### 18.3. Таблиця `θ`

| Generation | Best Pm | Best Pc | Best sigma | Mean Pm | Mean Pc | Mean sigma | Best fitness |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | ... | ... | ... | ... | ... | ... | ... |
| 10 | ... | ... | ... | ... | ... | ... | ... |
| 50 | ... | ... | ... | ... | ... | ... | ... |
| 100 | ... | ... | ... | ... | ... | ... | ... |

## 19. Обчислювальні ресурси

Основна оцінка:

```text
complexity ~= population_size * max_generations * fitness_model_cost
```

Для repeated experiments:

```text
total_complexity ~= population_size * max_generations * fitness_model_cost * number_of_scenarios * number_of_seeds
```

Фіксованими для чесного порівняння залишаються:

- `population_size`;
- `max_generations`;
- кількість scenarios;
- кількість repeated seeds;
- bounds задачі;
- fitness function;
- forward model.

Ці параметри не входять до `θ_base` на першому етапі, бо вони напряму змінюють runtime.

## 20. Очікуваний результат

SAGA-реалізація вважається коректною, якщо:

- кожен індивід містить `(x, θ_base)`;
- `θ_base ∈ genotype`;
- `θ_base` змінюється через variation;
- selection переносить увесь індивід `(x, θ_base)`;
- немає зовнішнього оновлення `θ`;
- GA і SAGA мають однакові data, bounds, seeds, population size і max generations;
- logs показують зміну `θ`;
- tests проходять;
- sandbox reports створюються.

Не потрібно доводити, що SAGA кращий у кожному single case. Потрібно чесно показати:

```text
mean result over repeated seeds and stress scenarios
```

## 21. Правила для чат-бота

Чат-бот має перед будь-якою реалізацією або аналізом перевірити:

```text
is_classical_GA_or_SAGA(request)
```

Якщо запит стосується класичного GA, можна працювати тільки в межах baseline GA.

Якщо запит стосується SAGA, потрібно перевірити:

```text
θ ∈ genotype
θ changes through variation
selection acts on (x, θ)
θ ⊆ θ_base
no external θ update
```

Якщо алгоритм не проходить критерій SAGA, чат-бот має:

1. Зупинити реалізацію.
2. Не додавати код, який маскує не-SAGA логіку під SAGA.
3. Написати в чат коротке повідомлення з причиною.

Шаблон повідомлення:

```text
Роботу зупинено: це не SAGA за формальним критерієм. Причина: <причина>. Можу продовжити тільки як класичний GA або змінити алгоритм так, щоб θ було частиною генотипу.
```

## 22. Що не робимо на цьому етапі

На цьому етапі не робимо нічого, що виходить за межі класичного GA або формального SAGA.

Заборонено додавати:

- будь-яку схему, де параметри змінюються зовнішніми правилами;
- generation-based parameter schedules;
- stagnation-based parameter updates;
- diversity-based parameter updates;
- success-rate-based external parameter updates;
- будь-які алгоритми поза межами класичного GA або формального SAGA;
- будь-які зовнішні механізми оптимізації як заміну GA або SAGA;
- будь-які гібридні схеми;
- будь-які додаткові optimization layers;
- будь-які багатокритеріальні розширення;
- будь-яке розпаралелювання як обов'язкову частину;
- claims про універсальний метод;
- нові фізичні моделі без потреби;
- paywalled або неперевірені джерела;
- toolbox-залежності без явного обґрунтування;
- приховані глобальні параметри, які фактично керують variation;
- зовнішні adaptive rules як заміну генотипній self-adaptation.

Якщо під час роботи виявлено, що запропонований алгоритм не є SAGA:

```text
STOP
do not implement as SAGA
write message to chat
explain failed criterion
offer only two valid paths: classical GA or formal SAGA redesign
```

Дозволені межі роботи:

- класичний GA baseline;
- SAGA з `θ_base` у генотипі;
- тести SAGA-критерію;
- sandbox для GA vs SAGA;
- звіти з чесним маркуванням результатів.

## 23. Фінальна формула

```text
SAGA = GA where I = (x, θ_base),
θ_base ∈ genotype,
θ_base changes through variation,
selection acts on (x, θ_base),
and no external parameter update is used.
```

Коротка назва:

```text
General SAGA + GA Research Template
```
