# Пілот адаптації ГА

Статус: INCOMPLETE.

Незалежно відтворено 26/40 журналів; перевірено 130000 нових пошукових запитів.

Один технічний seed 86001; без BCa, кореляційної переваги або добору коефіцієнтів. λ заблокований.

Cloned включає SC-s000 із глобальним центром як негативний контроль. Це не частота виходу лише з 14 допущених неглобальних центрів.

| Початок | Метод | Запуски | Кінцеве відставання, % | Виходи |
|---|---|---:|---:|---:|

| Задача | Початок | Тип початкового центра | Метод | Фінальна цінність |
|---|---|---|---|---:|
| SC-s000 | bank | EXCLUDED_GLOBAL_CENTER | classical | 34617 |
| SC-s000 | bank | EXCLUDED_GLOBAL_CENTER | adaptive_mutation | 34599 |
| SC-s000 | bank | EXCLUDED_GLOBAL_CENTER | adaptive_crossover | 34972 |
| SC-s000 | cloned | EXCLUDED_GLOBAL_CENTER | classical | 35617 |
| SC-s000 | cloned | EXCLUDED_GLOBAL_CENTER | adaptive_mutation | 35617 |
| SC-s000 | cloned | EXCLUDED_GLOBAL_CENTER | adaptive_crossover | 35617 |
| SC-s005 | bank | ADMITTED_PLATEAU_LOCAL | classical | 31027 |
| SC-s005 | bank | ADMITTED_PLATEAU_LOCAL | adaptive_mutation | 30609 |
| SC-s005 | bank | ADMITTED_PLATEAU_LOCAL | adaptive_crossover | 31104 |
| SC-s005 | cloned | ADMITTED_PLATEAU_LOCAL | classical | 31841 |
| SC-s005 | cloned | ADMITTED_PLATEAU_LOCAL | adaptive_mutation | 31841 |
| SC-s005 | cloned | ADMITTED_PLATEAU_LOCAL | adaptive_crossover | 31841 |
| UC-s000 | bank | ADMITTED_STRICT_LOCAL | classical | 45898 |
| UC-s000 | bank | ADMITTED_STRICT_LOCAL | adaptive_mutation | 42563 |
| UC-s000 | bank | ADMITTED_STRICT_LOCAL | adaptive_crossover | 45114 |
| UC-s000 | bank | ADMITTED_STRICT_LOCAL | unbalanced_gap | 46041 |
| UC-s000 | cloned | ADMITTED_STRICT_LOCAL | classical | 46510 |
| UC-s000 | cloned | ADMITTED_STRICT_LOCAL | adaptive_mutation | 46510 |
| UC-s000 | cloned | ADMITTED_STRICT_LOCAL | adaptive_crossover | 46510 |
| UC-s000 | cloned | ADMITTED_STRICT_LOCAL | unbalanced_gap | 46510 |
| WC-s001 | bank | ADMITTED_STRICT_LOCAL | classical | 26857 |
| WC-s001 | bank | ADMITTED_STRICT_LOCAL | adaptive_mutation | 26506 |
| WC-s001 | bank | ADMITTED_STRICT_LOCAL | adaptive_crossover | 26833 |
| WC-s001 | cloned | ADMITTED_STRICT_LOCAL | classical | 27585 |
| WC-s001 | cloned | ADMITTED_STRICT_LOCAL | adaptive_mutation | 27585 |
| WC-s001 | cloned | ADMITTED_STRICT_LOCAL | adaptive_crossover | 27585 |

*Невихід не доводить глобальності. Невиконані або пошкоджені записи не замінюються нулями; остаточні runner-хвилини встановлюються після завершення jobs.*
