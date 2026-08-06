# Amendment v1.2: машиночитне визначення adaptive GA

Дата: 2026-08-06
Застосовується до: `plans/cohort-2026-12-preregistration.md`
Момент внесення: до freeze eligibility/ranking і до будь-якого published-result reproduction run.

## Причина

Булевий прапорець `adaptation_within_run` та короткий опис `adaptive_locus` не доводять, що дослідження має повністю визначений і відтворюваний adaptive GA. Вимоги користувача 3-10 мають перевірятися незалежними шлюзами.

## Рішення

- Direct-only / no-inverse залишається окремим scope gate і не зсуває нумерацію hard criteria 3-10.
- Для кожного кандидата створюється окрема оцінка `g3`-`g10` зі станом `pass`, `unresolved` або `fail`, фактичним доказом і blocker-ом.
- `g5` окремо фіксує rule/algorithm, initial/min/max, frequency, order, trigger/feedback і boundary behavior.
- `g6` окремо фіксує objective, representation, constraints, initialization, selection, crossover, mutation, replacement/elitism і termination; явно відсутній оператор позначається як justified `not_applicable`, а не пропускається.
- `g7` забороняє required closed/paid/unavailable inputs, CFD/FEM, hardware experiment або solver.
- `g8` потребує literal numeric target з однозначним protocol cell; назва таблиці чи нечіткий графік не є target.
- `g9` потребує run count, seed/RNG rule, independence unit, budget/stopping, aggregation/analysis і достатній provenance.
- `g10` розділяє MATLAB clean-room feasibility та source-native replay feasibility. Source-native є required, якщо авторський код заявлений як reproduction artifact.

## Статус і score

- `hard_pass` дозволено лише коли scope gate, criteria 1-2 та всі `g3`-`g10` мають `pass`.
- Невідомий або суперечливий доказ дає `conditional_noneligible`; незворотна невідповідність дає `hard_fail`.
- `final_score` залишається `null` для обох неeligible статусів.
- Eligibility не є reproduction outcome. Formula-only implementation не може автоматично стати `PASS_FULL`.
