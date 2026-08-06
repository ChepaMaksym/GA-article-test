# Amendment v1.1: виключення інверсних задач

Дата: 2026-08-06
Застосовується до: `plans/cohort-2026-12-preregistration.md`
Момент внесення: до freeze рейтингу, до вибору active candidate і до будь-якого reproduction run.

## Рішення користувача

До cohort допускаються лише adaptive/self-adaptive genetic algorithms для прямих optimization tasks. Дослідження з inverse problems, inversion, system identification, source reconstruction, hidden-state reconstruction або parameter estimation через forward model виключаються.

## Операційне правило

Запис проходить scope gate лише тоді, коли GA безпосередньо оптимізує явно заданий objective у прямій задачі. Допустимі класи включають benchmark optimization, scheduling, routing, design optimization, controller tuning, feature selection і classification за умови виконання решти hard criteria.

## Вплив на пошук

- Квота залишається рівно 12: 6 USA + 6 EU.
- Інверсний запис не займає місце у дванадцятці.
- Відкинуті інверсні результати пошуку можна фіксувати лише у screening/exclusion log для прозорості.
- Старі негативні reproduction outcomes і immutable evidence не змінюються.

## Захист від bias

Amendment внесено до перегляду нових reproduction outcomes. Він змінює лише предметну область eligibility та не змінює score, published-result gates, tolerances або stopping rule.
