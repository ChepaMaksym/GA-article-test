# Preregistration: новий cohort adaptive GA (12 досліджень)

Статус: frozen search-and-reproduction protocol, amended to v1.2
Дата заморожування: 2026-08-06
Дата amendment v1.1: 2026-08-06, до freeze рейтингу і до reproduction runs
Дата amendment v1.2: 2026-08-06, до freeze eligibility/ranking і до published-result runs
Гілка: `research/cohort-2026-12`

## 1. Мета

Знайти 12 нових, не присутніх у попередньому 15-кандидатному cohort, досліджень adaptive/self-adaptive GA для прямих optimization tasks, виконати однаковий eligibility audit, ранжувати лише `hard_pass`, а потім послідовно відтворювати їх до першого `PASS_FULL` або вичерпання всіх preregistered eligible candidates.

Негативні результати EU-001 і USA-001, архів `old/` та immutable evidence не змінюються.

## 2. Квота і межі пошуку

- рівно 12 первинних записів: 6 USA + 6 EU;
- дата публікації: 2020-01-01 - 2026-08-06;
- peer-reviewed journal article або peer-reviewed conference paper;
- географія визначається за афіліацією щонайменше одного автора на момент публікації;
- EU означає державу-члена ЄС на дату публікації; UK не зараховується без окремої EU-афіліації;
- DOI, exact title і source revision використовуються для дедуплікації;
- усі 15 попередніх кандидатів та їхні дублікати виключаються;
- допускаються лише прямі optimization tasks;
- inverse problems, inversion, system identification, source reconstruction, hidden-state reconstruction і parameter estimation із observed data через forward model виключаються;
- benchmark function optimization, scheduling, routing, design optimization, controller tuning, feature selection і classification допускаються, якщо GA безпосередньо оптимізує явно заданий objective та виконує всі інші hard criteria;
- виключений через інверсність запис не може бути замінений послабленням критеріїв: пошук продовжується до заповнення квоти 6 USA + 6 EU неінверсними дослідженнями.

## 3. Hard inclusion criteria

Кандидат отримує `hard_pass` лише якщо одночасно виконано все:

1. Є законно доступний повний текст саме потрібної версії публікації.
2. Оптимізований solution vector має щонайменше 11 реальних decision variables. Population size, generations, crossover/mutation probabilities, tournament size й elitism не рахуються як decision variables.
3. Під час виконання змінюється щонайменше один GA hyperparameter або GA operator: mutation, crossover, selection/tournament, elitism, replacement або operator-selection probability. Одночасна адаптація кількох операторів дозволена.
4. Адаптація surrogate/fitness/forward model без зміни GA parameter/operator не відповідає вимозі.
5. Відомі формула або повністю виконуваний алгоритм адаптації, initial/min/max values, update frequency, update order, trigger/feedback metric і boundary behavior.
6. Відомі fitness/objective function, representation, constraints, initialization, selection, crossover, mutation, replacement/elitism і termination.
7. Є законні inputs або повністю визначений synthetic-data generator; немає залежності від недоступного CFD/FEM, закритого hardware experiment чи платного зовнішнього solver.
8. Є числовий published-result target, який можна перевірити без зчитування значень лише з нечіткого графіка.
9. Відомі або відтворювані run count, stochastic protocol і достатній provenance для чесного порівняння.
10. Clean-room MATLAB implementation є технічно реальною; source-native run має бути можливим, якщо авторський код заявлено як reproduction artifact.

Окремий scope gate застосовується до всіх hard criteria: задача має бути прямою оптимізацією, а не інверсією; objective обчислюється без відновлення прихованих фізичних параметрів, джерел або станів із вимірювань через forward model. Scope gate не змінює нумерацію визначення adaptive GA у пунктах 3-10.

Якщо хоча б один hard criterion не доведений, статус - `conditional_noneligible` або `hard_fail`; score не обчислюється.

## 4. Пошук і source hierarchy

Порядок доказів:

1. publisher/DOI record і офіційний full text;
2. institutional repository або author manuscript;
3. official supplementary material/data repository;
4. author-owned GitHub/GitLab/Zenodo commit або release;
5. upstream dataset/model documentation.

Не використовуються paywall bypass, неофіційні копії, неперевірені дані або source без зрозумілого походження. Для кожного PDF, dataset, code snapshot і configuration фіксуються URL, access date, revision/commit, license, byte length і SHA-256.

## 5. Registry та score

Для кожного з 12 записів заповнюється канонічна схема попереднього registry. Лише `hard_pass` отримує score з 100:

| Компонент | Max |
|---|---:|
| Математичний опис | 15 |
| Параметри експерименту | 10 |
| Законні дані | 10 |
| Seeds і run count | 10 |
| Відкритий код | 10 |
| Ліцензія коду | 10 |
| Проміжні результати | 10 |
| Адаптивні параметри | 10 |
| Порядок оновлення | 5 |
| Baseline GA | 5 |
| Ablation study | 5 |
| **Разом** | **100** |

Tie-break: (1) reproducible inputs, (2) executable official code, (3) numeric intermediate checkpoints, (4) complete seeds/raw runs, (5) lower runtime and dependency risk.

## 6. Preregistered execution order і stopping rule

- ranked `hard_pass` виконуються строго за score і tie-break;
- один кандидат активний за раз;
- для кожного кандидата published-result gates заморожуються до перегляду власних outcomes;
- дозволено максимум три diagnostic profiles після primary run, і лише якщо кожний варіант прямо підтриманий source;
- outcome-informed fitting, вигадування формул/seeds/inputs або підбір tolerance за результатом заборонені;
- цикл зупиняється на першому `PASS_FULL` або після вичерпання всіх preregistered `hard_pass`.

## 7. Середовища

| Environment | Роль | Мінімальна вимога |
|---|---|---|
| Source-native | Перевірка official artifact | Pinned OS image, language/runtime, dependency lock, exact commit/release |
| MATLAB R2026a | Канонічна clean-room реплікація | `main`, `run_unit_tests`, `run_reproduction`, `run_sandbox`; adapter до `verification/` |
| Python reference | Незалежний numerical oracle | Pinned Python + NumPy/SciPy; реалізація critical formulas без копіювання MATLAB control flow |
| GNU Octave | Compatibility check, коли toolbox-free kernel сумісний | Не є обов'язковим gate, якщо paper-faithful implementation потребує MATLAB toolbox |

Мінімум для спроби: source-native + MATLAB. Якщо source-native є MATLAB, другим незалежним середовищем стає Python reference. Cross-environment comparison використовує однакові frozen inputs і, де алгоритм дозволяє, однакові pre-generated random variates.

## 8. Implementation contract

Структура активного кандидата:

```text
candidates/<ID>/
  source_manifest/
  environments/native/
  environments/matlab/
  environments/python/
  tests/
  preregistration/
  results/
  reports/
```

Перед першим run заморожуються source revision, data hashes, numerical endpoints, tolerances, seed ledger, adapter files/configuration, run IDs, budgets і environment locks.

MATLAB candidate інтегрується через `fastverify.bind_adapter`; checkpoint, full resume state, RNG state і provenance є частиною контракту.

## 9. Test pyramid

1. Static/provenance: hashes, licenses, schema, dependency locks.
2. Unit tests: formulas, boundaries, operator probabilities, encoding/decoding, objective.
3. Property tests: feasibility, invariants, probability normalization, no NaN/Inf, deterministic resume.
4. Micro-oracle tests: hand-computable instances і exhaustive checks для малих search spaces.
5. Cross-environment tests: objective, one-generation transition і fixed random-tape equivalence.
6. Deterministic integration: frozen seeds/instances/checkpoints.
7. Stochastic protocol: preregistered run count, mean/SD/quantiles/success rate.
8. Published-result gates: лише заздалегідь визначені numeric endpoints.

## 10. PASS/FAIL semantics

- `PASS_FULL`: усі required structural, deterministic/stochastic, cross-environment та published-result gates пройдені.
- `FAIL_DECISIVE`: незворотний required milestone провалено; пізні stages не запускаються.
- `INCONCLUSIVE`: source не дозволяє сформувати discriminating gate; кандидат не може бути оголошений відтвореним.

Tolerance встановлюється до run:

- deterministic rounded table value - published rounding interval плюс documented floating-point tolerance;
- exact raw/checkpoint value - source-defined tolerance;
- stochastic mean/rate - preregistered equivalence margin, run count і confidence procedure; 5% не застосовується автоматично, якщо source precision або variance потребує іншого правила;
- figure-only qualitative agreement не може самостійно дати `PASS_FULL`.

## 11. Failure handling

Після невдачі спочатку зовнішньо зберігаються:

- primary і diagnostic profiles;
- seed/run ledgers, gate tables, environment manifests;
- source/data/code hashes;
- compact raw evidence, достатній для незалежного перерахунку;
- narrative root-cause analysis і рядок загального Failure Log;
- pre-deletion hash inventory.

Лише після перевірки evidence manifest активну implementation folder можна видалити. Recorded failed outcome не переписується. Архів `old/` і `failure_logs/USA-001_evidence/` не редагуються.

## 12. Success-only work

Тільки після `PASS_FULL`:

- fixed-GA baseline;
- operator ablations;
- sensitivity і robustness analysis;
- runtime/quality comparison;
- Excel workbook із inputs, outputs, gates, runs, statistics і graphs;
- повний reproducibility package та академічний report із чітким поділом `article_reported`, `exact_reproduction`, `synthetic_validation` і `new_analysis`.

## 13. Acceptance checklist

- 12 унікальних кандидатів, 6 USA + 6 EU;
- жодного кандидата зі старого cohort;
- для кожного твердження є source і fact/inference label;
- `hard_pass` не означає reproduced;
- score є тільки для `hard_pass`; arithmetic перевірена автоматично;
- жоден outcome не переглянуто до freeze gates/seeds/tolerances;
- однакові candidate IDs у registry, folders, logs і reports;
- усі generated tables відтворюються script-ом;
- негативні результати зберігаються так само ретельно, як позитивний.
