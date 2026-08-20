# Тимчасовий професорський аудит USA26-09

Дата: 2026-08-20

Статус документа: `TEMPORARY_AUDIT_RETAINED_AS_REJECTION_EVIDENCE`

## Підсумковий висновок

```text
CANDIDATE: USA26-09
OLD: REJECTED_INVALID_PUBLISHED_ENDPOINT_MAPPING
HYBRID: BLOCKED_AND_UNSUPPORTED
SCIENTIFIC_NOVELTY: CONCEPTUALLY_INTERESTING_BUT_NOT_EMPIRICALLY_ESTABLISHED
MASTER_THESIS: PROHIBITED_FOR_THIS_CANDIDATE
PR19_NUMERICAL_EVIDENCE_USED: false
```

Кандидат тематично підходить до напряму дослідження, але поточна
реконструкція не може вважатися відтворенням OLD і не створює чесної бази для
порівняння з HYBRID. Проблеми є методологічними, а не косметичними, тому
зміна tolerance, seed або формулювання висновку не може їх виправити.

## Професорська оцінка

| Критерій | Бал зі 100 | Коментар |
|---|---:|---|
| Відповідність темі та розмірності | 85 | 49 маршрутних genes, min-max mTSP, адаптивний пошук |
| Автентичність джерела | 55 | Є стаття й авторський GitHub, але немає project-wide license та історичного seed ledger |
| Вірність OLD статті | 20 | Реалізовано спрощений GA, а не повний HGA статті |
| Коректність числового endpoint | 10 | Одне instance порівнюється із середнім для 100 instances і 10 запусків на кожному |
| Чесність OLD-HYBRID бюджету | 20 | HYBRID отримує змінний неврахований surrogate-пошук |
| Статистичний дизайн | 35 | Є paired seeds, але endpoint, coverage rule і censoring потребують виправлення |
| Якість реалізації | 45 | Ядро Split акуратне, але є algorithm drift, dead code та неповне accounting |
| Тести | 30 | Є micro-oracles, але немає тестів головних наукових тверджень і негативних controls |
| CI/CD | 25 | Матриця запускається, але відсутній cross-job binder і fail-closed scientific gate |
| Наукова новизна | 40 | Потенційна двошарова адаптація цікава, але ефект не доведено |

Рекомендована академічна оцінка поточної версії: **незадовільно, з правом
перепроєктування на іншому кандидатові**.

## 1. Фундаментальні проблеми OLD

### P-OLD-01 - несумісні експериментальні одиниці

Table 2 статті для Set I, `N=50`, `m=10` повідомляє `HGA-avg=1.82` як
середнє для 100 незалежно згенерованих uniform instances. HGA запускається 10
разів для кожного instance. Поточний протокол порівнює це число з медіаною 30
search seeds на одному instance `20240809`.

```text
published unit: mean over 100 instances x 10 HGA runs
current unit:   median over 1 instance x 30 search runs
```

Ці величини не є статистично взаємозамінними. Gate
`abs(median - 1.82) <= 0.02` не підтверджує відтворення статті.

### P-OLD-02 - anchor доступний до запуску HGA

Тест `test_frozen_instance_and_nearest_neighbor_anchor` фіксує, що звичайний
nearest-neighbor порядок на вибраному instance вже має objective
`1.8288547696784496`, тобто практично збігається з published average `1.82`.
Близькість OLD до anchor тому не доводить роботу авторського HGA.

### P-OLD-03 - спрощення авторського HGA

Стаття використовує:

- variable population control `mu=10`, `lambda=20`;
- sorting за fitness і diversification factor;
- tournament size 2;
- Similar Tour Crossover;
- exact Split;
- intersection removal;
- enrichment між турами та exhaustive 2-opt;
- adaptive random local search з 100 або 1000 повторів;
- nearest-city restriction;
- diversification після 1000 generations без покращення;
- stop після 2500 generations без покращення або cutoff time.

Поточний OLD натомість використовує population 40, top-12 selection,
three-way tournament, generic order crossover, один guided move і budget 1500
logical calls. Це новий surrogate optimizer, а не незалежна реалізація
Algorithm 1 статті.

### P-OLD-04 - невірна семантика roulette reward

У статті roulette count збільшується після фактичного локального покращення
поточний solution окремим move під час багатократного education loop. У
поточному OLD reward визначається порівнянням остаточного child із parent до
crossover. Це змішує ефекти crossover, surrogate education і local move.

### P-OLD-05 - невідтворений stopping rule

`1500 logical NFE` не є еквівалентом `ItNI=2500` generations без покращення.
Немає bridge-аналізу між цими бюджетами та published runtime protocol.

### P-OLD-06 - довільний acceptance interval

Tolerance `0.02` не виведено з reported dispersion, standard error або raw
rows статті. Оскільки Table 2 містить rounded mean без variance, цей tolerance
не може підтвердити statistical reproduction.

## 2. Фундаментальні проблеми HYBRID

### P-HYB-01 - неврахована різна обчислювальна робота

OLD обирає найкращий із фіксованих шести surrogate proposals. HYBRID для
кожного з `L` edits у кожному mutant переглядає
`max(4, round_half_up(lambda))` proposals. При зростанні lambda прихована
робота приблизно росте як `lambda^2 * L`, але в logical NFE не входить.

Через це менша кількість exact Split calls не означає вищу загальну
ефективність. Потрібні щонайменше три budgets:

```text
exact objective calls
surrogate proposal evaluations
normalized total work / wall-clock diagnostic
```

### P-HYB-02 - протокол обіцяє accounting, але код його не зберігає

Amendment зазначає, що surrogate education записується окремо. `RunResult` не
містить `surrogate_evaluations`, `applied_edits`, `cache_hits`,
`cache_misses` або `split_computations`.

### P-HYB-03 - відхилення від перевіреного paper-profile PR #8

Поточний final pool містить усі mutants та crossover candidates. Перевірений
paper-profile PR #8 використовує selected best mutant плюс crossover
candidates та окремі правила exclusion. Тому формулу lambda перенесено, але
повну семантику алгоритму не перенесено.

### P-HYB-04 - одночасно змінено кілька механізмів

Lambda одночасно контролює mutation depth, offspring count, crossover edit
selection і surrogate proposal count. Без ablations неможливо визначити, який
механізм створив ефект.

### P-HYB-05 - reset не активний у primary profile

Якщо lambda не доходить до cap, primary experiment не може підтримувати
reset-specific novelty. Stress test може підтвердити виконання гілки reset,
але не причинність primary improvement.

## 3. Проблеми коду

- `best_mutant_value`, `best_mutant`, `best_edits` обчислюються, але не
  використовуються.
- `generate_initial_population` має необмежений `while` без fail-closed ліміту.
- Or-opt може створювати no-op move; це не маркується окремо.
- `ObjectiveCounter` рахує cache hit як logical call, але не записує окремо
  actual Split computations і cache statistics.
- `RunResult.canonical()` не містить lambda trace та effort accounting.
- Відсутні перевірки empty seed ledger, `workers<=0`, `resamples<=0`,
  non-finite target/rows та duplicate seeds.
- Exact float equality використовується для `equal` і cross-platform digest.
- Dependencies задані як `numpy>=1.26`, `pytest>=8`; scientific environment не
  pinned і не має lock/constraints file.
- Немає explicit clean-room license для нової реалізації.
- PR body містить superseded positive numbers, тоді як repository docs мають
  `FROZEN_NOT_RUN_V2` і `BLOCKED_BY_FRESH_OLD_V2`.

## 4. Проблеми тестів

- Немає тесту повної Algorithm-1 state transition OLD.
- Немає test oracle для Similar Tour Crossover, diversification,
  intersection removal, enrichment і 100/1000 education schedule.
- Worker test перевіряє лише workers 1 та 2, три pilot seeds і budget 180.
- Немає workers=4 full-ledger equivalence test.
- Немає tests для paired summary, coverage `24/30`, bootstrap boundaries,
  duplicate seeds, malformed rows і censoring.
- У коді coverage обчислено як `ceil(0.75*n)`, що для `n=30` дорівнює 23, а
  preregistration вимагає 24.
- Немає mutation tests, які повинні вбити неправильні `lambda/n`, `1/lambda`,
  reset timing, reward timing, NFE і surrogate accounting.
- Немає negative controls, де scientific hypothesis чесно FAIL, але protocol
  залишається валідним.
- Тест nearest-neighbor anchor закріплює методологічно невдалий instance
  замість перевірки article endpoint.

## 5. Проблеми CI/CD

- Workflow має `push` і `workflow_dispatch`, але немає `pull_request` gate.
- Дев'ять jobs лише завантажують profile JSON; немає binder job, який
  завантажує всі artifacts і порівнює scientific digests.
- Матриця змішує OS, Python і workers, тому фактори не ізольовані.
- Немає required current-head conclusion або PR comment з immutable run URL.
- Немає full confirmatory OLD gate і автоматичного блокування HYBRID.
- Немає coverage, Ruff critical gate, Bandit, dependency audit, Vulture або
  mutation testing.
- Немає artifact manifest і SHA-256 binder.
- Немає fail-closed перевірки відсутнього/порожнього profile.
- Після reconstruction з workflow видалено load-profile і finalizer jobs.
- `issues: write` не потрібен поточній workflow і завищує permissions.
- GitHub не повертає check/status context для current head на момент аудиту.

## 6. Оцінка наукової новизни

### Потенційно допустима гіпотеза після коректного OLD

> Розроблено двошарову адаптивну архітектуру HGA, у якій
> success-weighted roulette адаптує вибір локального оператора, а
> self-adjusting lambda-controller адаптує інтенсивність породження та
> рекомбінації кандидатів за незмінного objective і benchmark protocol.

Це формулювання описує architecture proposal, але не результат.

### Тимчасово допустиме формулювання для поточного стану

> Запропоновано та формально специфіковано експериментальне перенесення
> self-adjusting lambda-control до permutation HGA. Числове твердження про
> покращення не сформовано, оскільки аудит виявив несумісність OLD endpoint і
> нерівність повного обчислювального бюджету.

### Заборонені шаблонні фрази

- `Запропонований метод довів свою перевагу.`
- `HYBRID підвищує ефективність на 49.66%.`
- `Кількість ітерацій зменшено без втрати якості.`
- `Вперше у світі поєднано ...`
- `Reset забезпечив покращення.`
- `OLD повністю відтворює статтю.`
- `Результати підтверджено на різних машинах.`

### Академічно безпечні фрази

- `Наукова новизна має інкрементальний інтеграційний характер.`
- `Твердження обмежено конкретним замороженим протоколом.`
- `Logical NFE не ототожнюється з wall-clock time.`
- `Негативний результат OLD-gate збережено без post-hoc зміни критеріїв.`
- `Кандидат відхилено до етапу HYBRID через невалідне зіставлення з published endpoint.`

## 7. Шаблонні відповіді на запитання професора

### Чому не можна використати 1.82 як контрольну точку?

Тому що 1.82 є rounded mean для 100 instances і десяти HGA запусків на
кожному, а наша величина була медіаною на одному instance. Це різні
експериментальні одиниці.

### Чому logical NFE недостатньо?

Тому що HYBRID виконував змінну кількість surrogate proposals, які не входили
до NFE. Порівняння exact Split calls без effort ledger могло систематично
переоцінити HYBRID.

### Чому не виправити tolerance?

Зміна tolerance після перегляду результатів є outcome-informed tuning. Вона
зруйнувала б preregistration і не усунула б mismatch між одним instance та
100-instance average.

### Чи є сама ідея HYBRID науковою?

Так, як гіпотеза двошарової адаптації. Ні, як доведений результат на цьому
кандидатові, бо OLD baseline і budget fairness не пройшли аудит.

### Чому кандидат відхилено, а не допрацьовано?

Щоб відтворити статтю, потрібно реалізувати інший, значно повніший HGA і
1000-run Set-I design. Це вже не локальне виправлення поточного коду. За
правилами проєкту дешевше й науково чистіше перейти до кандидата з exact
public endpoint, seeds/raw rows і повною source semantics.

## 8. Рішення щодо репозиторію

1. Зберегти цей аудит, source manifest і короткий rejection record.
2. Видалити executable implementation та candidate workflow, щоб їх не
   сплутали з accepted evidence.
3. Оновити PR як `REJECTED` і закрити без merge.
4. Наступний кандидат має починатися безпосередньо від PR #8 base.
5. До нового preregistration вимагати exact endpoint unit, raw/seed ledger,
   повну operator map, legal provenance і effort accounting.
