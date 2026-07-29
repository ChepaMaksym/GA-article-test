# Загальний план дослідження: Adaptive GA для прикладної inverse-задачі

## 1. Призначення документа

Цей документ задає формальний план дослідження та реалізації **Adaptive Genetic Algorithm (Adaptive GA, AGA)** для прикладної inverse-задачі оптимізації.

У межах цього плану дозволені:

- класичний Genetic Algorithm (GA) як baseline;
- Adaptive GA, у якому параметри алгоритму змінюються під час запуску;
- article-aligned варіант, наприклад NMGA, якщо стаття явно задає динамічні правила для `Pc`, `Pm` або інших параметрів GA.

Головна межа плану:

```text
chromosome = solution genes only
algorithm parameters = external algorithm state
```

Тобто `Pc`, `Pm`, `sigma`, selection pressure або інші керуючі параметри не є генами хромосоми, не успадковуються дитиною і не проходять crossover/mutation як частина індивіда.

## 2. Формальна класифікація

Параметри еволюційного алгоритму можна:

1. задати до запуску і не змінювати;
2. змінювати під час запуску за правилом керування;
3. кодувати всередині індивідів.

Цей план використовує другий випадок: **parameter control during the run**.

Практичне визначення для цього проєкту:

```text
Adaptive GA = GA, у якому алгоритм змінює власні керуючі параметри під час еволюції,
але ці параметри не входять до chromosome.
```

Якщо правило залежить тільки від номера покоління, це deterministic schedule. Якщо правило використовує feedback від пошуку, це feedback-adaptive control. Обидва варіанти можуть бути реалізовані, але в документації вони мають бути чітко позначені.

## 3. Формальна модель

Нехай популяція в поколінні `g`:

```text
P_g = {x_1, x_2, ..., x_N}
```

де:

- `x_i` — хромосома, тобто кандидатне рішення inverse-задачі;
- `N` — population size.

Стан керування алгоритму:

```text
Θ_g = (Pc_g, Pm_g, sigma_g, selection_pressure_g, ...)
```

де:

- `Pc_g` — ймовірність кросоверу в поколінні `g`;
- `Pm_g` — ймовірність мутації в поколінні `g`;
- `sigma_g` — сила або масштаб мутації, якщо використовується;
- `selection_pressure_g` — параметр селекції, якщо він адаптується.

Оцінки стану пошуку:

```text
Z_g = metrics(P_g, fitness_g, history_g)
```

Приклади `Z_g`:

- `best_fitness_g`;
- `mean_fitness_g`;
- `fitness_improvement_g`;
- `stagnation_count_g`;
- `population_diversity_g`;
- `feasible_ratio_g`;
- `boundary_hit_rate_g`.

Оновлення параметрів:

```text
Θ_{g+1} = clip(update_rule(Θ_g, Z_g, g), Θ_min, Θ_max)
```

Варіація:

```text
offspring_g = variation(P_g, Θ_g)
```

Селекція:

```text
P_{g+1} = selection(P_g, offspring_g, fitness)
```

Тут `selection` відбирає рішення `x`, а не пари `(x, Θ)`. Стан `Θ_g` залишається станом алгоритму.

## 4. Прикладна постановка inverse-задачі

Inverse-задача має бути задана як оптимізація параметрів моделі за спостереженнями.

Типова форма:

```text
given observed_data y_obs
find x
minimize F(x) = error(forward_model(x), y_obs) + penalties(x)
subject to lb <= x <= ub
```

де:

- `x` — шукані параметри прикладної системи;
- `forward_model(x)` — пряма модель;
- `y_obs` — спостережені або reported дані;
- `F(x)` — fitness/objective;
- `lb`, `ub` — фізичні або інженерні межі параметрів.

Для прикладної роботи важливо не лише показати роботу GA, а й явно описати:

- що саме оптимізується;
- які одиниці вимірювання мають змінні;
- які bounds фізично допустимі;
- які дані є reported, а які synthetic;
- як обчислюється похибка;
- які обмеження накладає forward model.

## 5. Дозволені режими

### 5.1. Classical GA baseline

Baseline має фіксовані параметри:

```text
chromosome = x
Pc_g = Pc_0
Pm_g = Pm_0
sigma_g = sigma_0
```

Цей режим потрібен для чесного порівняння.

### 5.2. Adaptive GA

Adaptive GA має хромосому тільки з рішенням:

```text
chromosome = x
```

А параметри алгоритму оновлюються окремо:

```text
Pc_{g+1} = update_pc(Pc_g, Z_g, g)
Pm_{g+1} = update_pm(Pm_g, Z_g, g)
sigma_{g+1} = update_sigma(sigma_g, Z_g, g)
```

Мінімальний варіант:

```text
Pc_g changes during run
Pm_g changes during run
```

Рекомендований варіант для прикладної задачі:

```text
Pc_g decreases when exploitation should increase
Pm_g increases when stagnation or low diversity is detected
Pm_g decreases when search is unstable or too noisy
sigma_g decreases as convergence improves
```

### 5.3. Article-aligned dynamic GA

Якщо стаття задає формули на кшталт:

```text
Pc_g = Pc_max - (Pc_max - Pc_min) * progress^beta
Pm_g = Pm_min + (Pm_max - Pm_min) * progress^gamma
progress = g / G_max
```

такий алгоритм можна реалізувати як article-aligned dynamic GA або NMGA-style GA.

У звіті його треба називати точно:

```text
generation-scheduled parameter control
```

а не feedback-adaptive control, якщо правило не використовує feedback від fitness, diversity або stagnation.

## 6. Що не робимо

Не використовувати модель, де параметри алгоритму записані в хромосому.

Заборонено описувати схему, де керуючі параметри GA є частиною індивіда, успадковуються від батьків або змінюються як фрагменти хромосоми.

Також не робимо:

- додатковий зовнішній оптимізатор поверх GA;
- гібридну заміну GA іншим метаевристичним алгоритмом без окремого плану;
- багатокритеріальне розширення без потреби;
- обов'язкове розпаралелювання як частину алгоритму;
- claims про універсальну перевагу Adaptive GA;
- приховані параметри, які змінюють variation, але не логуються;
- зміну fitness або budget між baseline GA та Adaptive GA.

## 7. Критерій коректного Adaptive GA

Алгоритм вважається Adaptive GA у межах цього плану, якщо:

- chromosome містить тільки `x`;
- є явний стан керування `Θ_g`;
- хоча б один базовий параметр GA змінюється під час запуску;
- оновлення параметрів виконує окрема функція або чіткий блок коду;
- усі параметри мають bounds;
- історія `Θ_g` логуються для кожного покоління;
- GA baseline і Adaptive GA мають однакові data, bounds, population size, max generations і seed policy;
- у звіті вказано, чи правило є scheduled, feedback-adaptive або змішаним.

Мінімальний критерій:

```text
exists g1, g2 such that Θ_g1 != Θ_g2
AND Θ_g is not part of chromosome
AND Θ_g affects variation or selection
```

## 8. Правила оновлення параметрів

### 8.1. Scheduled update

Правило залежить від покоління:

```text
progress = g / G_max
Pc_g = f_pc(progress)
Pm_g = f_pm(progress)
sigma_g = f_sigma(progress)
```

Це простий і відтворюваний варіант. Він добре підходить, коли стаття явно задає формули.

### 8.2. Feedback-adaptive update

Правило залежить від стану пошуку:

```text
if stagnation_count_g >= stagnation_limit:
    Pm_{g+1} = min(Pm_g * mutation_boost, Pm_max)
else:
    Pm_{g+1} = max(Pm_g * mutation_decay, Pm_min)
```

Можливе правило для diversity:

```text
if diversity_g < diversity_min:
    Pm_{g+1} = min(Pm_g + delta_pm, Pm_max)
    Pc_{g+1} = max(Pc_g - delta_pc, Pc_min)
```

Можливе правило для progress:

```text
if improvement_g > improvement_target:
    sigma_{g+1} = max(sigma_g * sigma_decay, sigma_min)
```

### 8.3. Mixed update

Допускається поєднання:

```text
Θ_{g+1} = scheduled_component(g) + feedback_correction(Z_g)
```

Але в такому разі треба окремо логувати:

- scheduled part;
- feedback part;
- final clipped value.

## 9. Мінімальна структура реалізації

Рекомендована структура:

| Ресурс | Роль |
|---|---|
| `README.md` | короткий опис задачі, запуску, даних і обмежень |
| `main.m` | основний запуск |
| `run_unit_tests.m` | запуск unit tests |
| `run_reproduction.m` | відтворення article-aligned або baseline порівняння |
| `run_sandbox.m` | synthetic/stress сценарії |
| `src/data/` | reported або synthetic data |
| `src/models/` | forward model та objective/fitness |
| `src/optimization/` | GA, Adaptive GA, update rules |
| `src/metrics/` | accuracy, speed, robustness metrics |
| `tests/` | unit tests |
| `sandbox/results/` | Markdown і `.mat` результати |

Для Adaptive GA бажані окремі функції:

```text
ga_options.m
adaptive_ga_options.m
adaptive_rates.m
run_classical_ga.m
run_adaptive_ga.m
run_reproduction_impl.m
run_sandbox_impl.m
```

## 10. MATLAB-вимоги

Бажаний формат — автономний MATLAB-код без обов'язкових toolbox-залежностей.

Базово потрібні:

- MATLAB;
- стандартні MATLAB-функції для масивів і структур;
- `rng` для відтворюваності;
- `save` / `load` для `.mat` результатів;
- `fprintf` для Markdown-звітів;
- `mkdir` для створення `sandbox/results`.

Не робити обов'язковими без окремої причини:

- Global Optimization Toolbox;
- Parallel Computing Toolbox;
- Statistics and Machine Learning Toolbox;
- Optimization Toolbox.

Якщо toolbox потрібен, це треба явно записати в README, verification guide і повідомлення перед запуском.

## 11. План реалізації

### Крок 1. Описати inverse-задачу

Зафіксувати:

```text
x variables
units
bounds
forward_model
objective
penalties
reported_data vs synthetic_data
```

### Крок 2. Реалізувати Classical GA baseline

Baseline:

```text
chromosome = x
Pc = constant
Pm = constant
sigma = constant
```

Логувати:

```text
best_fitness_history
mean_fitness_history
best_x
runtime_seconds
function_evaluations
```

### Крок 3. Додати Adaptive GA state

Структура стану:

```text
state.generation
state.Pc
state.Pm
state.sigma
state.stagnationCount
state.bestFitness
state.previousBestFitness
state.diversity
```

Структура bounds:

```text
rates.PcMin
rates.PcMax
rates.PmMin
rates.PmMax
rates.SigmaMin
rates.SigmaMax
```

### Крок 4. Реалізувати update rule

Окрема функція:

```text
[Pc, Pm, sigma, diagnostics] = adaptive_rates(generation, maxGenerations, state, options)
```

Функція має:

- читати тільки дозволені feedback-змінні;
- застосовувати bounds;
- повертати diagnostics;
- не змінювати chromosome;
- бути детермінованою для однакового state/options.

### Крок 5. Інтегрувати update rule у цикл GA

Порядок у кожному поколінні:

```text
evaluate population
compute search metrics Z_g
update Θ_g
breed offspring using Θ_g
repair/clip offspring to problem bounds
evaluate offspring
select next population
log Θ_g and metrics
```

### Крок 6. Додати логування

Обов'язково логувати:

```text
Pc_history
Pm_history
sigma_history
diversity_history
stagnation_history
best_fitness_history
mean_fitness_history
generation_to_best
function_evaluations
```

Для article-aligned schedule також логувати:

```text
progress_history
scheduled_Pc_history
scheduled_Pm_history
```

Для feedback-adaptive rule також логувати:

```text
feedback_signal_history
update_reason_history
clipping_flags_history
```

### Крок 7. Порівняти режими

Порівнювати:

```text
Classical GA
Adaptive GA
```

Умови мають бути однаковими:

- data;
- bounds;
- objective;
- population size;
- max generations;
- number of seeds;
- number of scenarios;
- initialization policy;
- random seed policy.

## 12. Unit tests

Тести мають перевіряти і числовий результат, і формальний статус Adaptive GA.

Обов'язкові тести Adaptive GA:

1. `chromosome contains solution variables only`.
2. `adaptive parameters are stored outside chromosome`.
3. `adaptive_rates returns Pc and Pm within bounds`.
4. `Pc or Pm changes across generations`.
5. `variation uses current Pc and Pm`.
6. `same seed gives reproducible Adaptive GA result`.
7. `same state gives reproducible adaptive_rates result`.
8. `rate history length equals generation count`.
9. `best fitness history length equals generation count`.
10. `Adaptive GA respects problem bounds`.
11. `Adaptive GA uses same objective as baseline GA`.
12. `Adaptive GA uses same budget as baseline GA`.
13. `control parameters are absent from population matrix`.
14. `no child-specific inherited Pc or Pm exists`.

Для feedback-adaptive rule:

1. `stagnation increases mutation pressure`.
2. `low diversity changes rates in expected direction`.
3. `improvement can reduce mutation strength`.
4. `clipping prevents rates from exceeding bounds`.

Для scheduled rule:

1. `progress starts near zero and ends at one`.
2. `scheduled Pc follows configured monotonic direction`.
3. `scheduled Pm follows configured monotonic direction`.
4. `beta/gamma affect schedule shape`.

Тести Classical GA:

1. `GA uses fixed mutation probability`.
2. `GA uses fixed crossover probability`.
3. `GA output respects problem bounds`.
4. `same seed gives reproducible GA result`.

## 13. Sandbox

Sandbox потрібен для стрес-перевірки, а не для доказу переваги в кожному запуску.

### 13.1. Базові сценарії

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

### 13.2. Сценарії адаптації

```text
low_initial_mutation_probability
high_initial_mutation_probability
low_initial_crossover_probability
high_initial_crossover_probability
low_initial_mutation_strength
high_initial_mutation_strength
stagnation_trigger
low_diversity_trigger
```

### 13.3. Сценарії прикладної стійкості

```text
noisy_observations
missing_observations
biased_forward_model
shifted_true_solution
boundary_solution
ill_scaled_variables
multimodal_objective
flat_fitness_region
```

### 13.4. Обов'язкові sandbox checks

Кожен запуск має перевіряти:

- final fitness є скінченним;
- `x` не порушує bounds;
- `Pc_history` і `Pm_history` записані;
- `Pc_history` і `Pm_history` залишаються в bounds;
- Adaptive GA фактично змінює хоча б один параметр;
- baseline GA і Adaptive GA використовують однаковий budget;
- repeated seeds мають відтворювану поведінку;
- synthetic scenarios не видаються за reported data.

## 14. Метрики

### 14.1. Метрики точності

```text
final_fitness
best_fitness
error_to_known_solution
RMSE
MAE
success_rate
constraint_violation
```

### 14.2. Метрики швидкості

```text
runtime_seconds
generation_to_best
generation_to_threshold
function_evaluations
```

### 14.3. Метрики адаптації

```text
Pc_start
Pc_end
Pc_mean
Pc_min_observed
Pc_max_observed
Pm_start
Pm_end
Pm_mean
Pm_min_observed
Pm_max_observed
rate_change_count
stagnation_trigger_count
diversity_trigger_count
```

Головна метрика Adaptive GA — не просто кращий fitness, а доказ, що зміна параметрів була:

- явною;
- залогованою;
- обмеженою bounds;
- пов'язаною з variation або selection;
- порівняною з baseline на однаковому budget.

## 15. Таблиці звіту

### 15.1. Таблиця точності

| Method | Mean error | Std error | Best | Worst | Success rate |
|---|---:|---:|---:|---:|---:|
| Classical GA | ... | ... | ... | ... | ... |
| Adaptive GA | ... | ... | ... | ... | ... |

### 15.2. Таблиця швидкості

| Method | Mean runtime | Mean generations | Function evaluations | Generation to threshold |
|---|---:|---:|---:|---:|
| Classical GA | ... | ... | ... | ... |
| Adaptive GA | ... | ... | ... | ... |

### 15.3. Таблиця параметрів

| Generation | Pc | Pm | Sigma | Diversity | Stagnation | Best fitness |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | ... | ... | ... | ... | ... | ... |
| 10 | ... | ... | ... | ... | ... | ... |
| 50 | ... | ... | ... | ... | ... | ... |
| 100 | ... | ... | ... | ... | ... | ... |

### 15.4. Таблиця типу control

| Parameter | Control type | Update signal | Bounds | Used by |
|---|---|---|---|---|
| `Pc` | scheduled / feedback / mixed | ... | `[min, max]` | crossover |
| `Pm` | scheduled / feedback / mixed | ... | `[min, max]` | mutation |
| `sigma` | scheduled / feedback / mixed | ... | `[min, max]` | mutation |

## 16. Джерела та пошук

Використовувати тільки легальні й відкрито доступні джерела:

- сторінка статті або технічного опису;
- DOI landing page;
- офіційний PDF або HTML full text, якщо доступний;
- supplementary materials;
- author-provided repository;
- MATLAB documentation;
- офіційна документація MathWorks.

Не використовувати:

- paywall обходи;
- неофіційні копії;
- неперевірені дані;
- джерела без зрозумілого походження.

Пошукові запити:

```text
"adaptive genetic algorithm" "mutation probability" "crossover probability"
"genetic algorithm" "parameter control" "mutation rate"
"evolutionary algorithms" "parameter control" "adaptive"
"dynamic crossover probability" "genetic algorithm"
"dynamic mutation probability" "genetic algorithm"
"adaptive rates" "genetic algorithm" inverse problem
```

Формальна базова класифікація:

```text
A. E. Eiben, R. Hinterding, Z. Michalewicz,
"Parameter control in evolutionary algorithms",
IEEE Transactions on Evolutionary Computation, 1999,
DOI: 10.1109/4235.771166.
```

Це джерело використовується лише для розмежування parameter tuning до запуску та parameter control під час запуску.

## 17. Відтворення

Дані мають бути чітко позначені:

```text
reported_data             -> значення, прямо взяті з відкритого джерела
synthetic_reproduction    -> локальні синтетичні сценарії
```

Не можна видавати synthetic sandbox за оригінальні авторські дані.

Якщо raw data недоступні:

- реалізувати synthetic scenario;
- явно написати, що це не авторські raw data;
- порівнювати тільки з reported summary values, якщо вони доступні;
- не заявляти повну реплікацію експерименту.

## 18. Обчислювальні ресурси

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
- number of scenarios;
- number of repeated seeds;
- bounds задачі;
- fitness function;
- forward model.

Adaptive update rule має бути дешевим відносно fitness evaluation.

## 19. Очікуваний результат

Реалізація Adaptive GA вважається коректною, якщо:

- chromosome містить тільки рішення `x`;
- `Pc`, `Pm`, `sigma` або інші параметри зберігаються як стан алгоритму;
- хоча б один параметр змінюється під час запуску;
- update rule формально описаний;
- параметри не виходять за bounds;
- параметри реально впливають на variation або selection;
- GA baseline і Adaptive GA мають однакові data, bounds, seeds, population size і max generations;
- logs показують зміну параметрів;
- unit tests проходять;
- sandbox reports створюються.

Не потрібно доводити, що Adaptive GA кращий у кожному single case. Потрібно чесно показати:

```text
mean result over repeated seeds and stress scenarios
```

## 20. Правила для чат-бота

Перед реалізацією чат-бот має перевірити:

```text
is_request_classical_ga_or_adaptive_ga(request)
```

Якщо запит стосується Classical GA:

- використовувати фіксовані `Pc`, `Pm`, `sigma`;
- не додавати adaptive update rule без окремого запиту.

Якщо запит стосується Adaptive GA:

- реалізувати `Θ_g` як стан алгоритму;
- додати `adaptive_rates` або еквівалентну функцію;
- логувати історію `Θ_g`;
- не додавати параметри алгоритму в chromosome;
- не змінювати objective/budget між baseline та adaptive run.

Якщо виявлено генотипне кодування параметрів, чат-бот має зупинитися і написати:

```text
Роботу зупинено: цей план вимагає Adaptive GA з параметрами як станом алгоритму, а не параметрами всередині chromosome.
```

## 21. Фінальна формула

```text
P_g = {x_i}
Θ_g = (Pc_g, Pm_g, sigma_g, ...)
Z_g = metrics(P_g, fitness_g, history_g)
Θ_{g+1} = clip(update_rule(Θ_g, Z_g, g), Θ_min, Θ_max)
P_{g+1} = selection(P_g, variation(P_g, Θ_g))
```

Коротко:

```text
Adaptive GA = GA where the algorithm changes Pc/Pm/sigma during the run,
while chromosome remains solution-only.
```

Коротка назва:

```text
Adaptive GA Inverse Research Development Plan
```
