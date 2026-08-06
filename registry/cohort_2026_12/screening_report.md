# Screening report: 12 direct adaptive-GA records

Дата аудиту: 2026-08-06
Протокол: `plans/cohort-2026-12-preregistration.md`, amendment v1.2

## Висновок

Пошук сформував точну квоту 6 USA + 6 EU без інверсних задач. Після застосування user-defined hard gates 3-10 жодна стаття не має достатнього evidence package для `hard_pass`. Ранжування і published-result reproduction не запускаються.

Позначення: `P` = pass, `U` = unresolved, `F` = fail. Детальні значення, межі, update order, targets і provenance містяться в `hard_gate_assessments.json`.

| ID | Region | Adaptive GA locus | G3 | G4 | G5 | G6 | G7 | G8 | G9 | G10 | Eligibility |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| USA26-01 | USA | mutation-rate population | P | P | P | P | P | P | U | U | conditional |
| USA26-02 | USA | mutation threshold + step threshold | P | P | P | P | F | F | P | F | hard fail |
| USA26-03 | USA | self-adaptive bit-mutation rate | P | P | U | P | P | U | U | P | conditional |
| USA26-04 | USA | bandit-selected mutation rate | P | P | U | P | P | P | U | P | conditional |
| USA26-05 | USA | crossover + mutation rates | P | P | U | P | U | P | U | P | conditional |
| USA26-06 | USA | crossover + mutation rates | U | P | F | F | F | P | F | F | hard fail |
| EU26-01 | EU | mutation strength/operator policy | P | P | U | P | P | P | P | U | conditional |
| EU26-02 | EU | crossover/local-search action policy | P | P | P | P | P | U | U | P | conditional |
| EU26-03 | EU | local mutation-operator probabilities | P | P | P | P | U | P | U | U | conditional |
| EU26-04 | EU | mutation/restart/selection parameters | P | P | U | U | P | U | U | U | conditional |
| EU26-05 | EU | crossover operator probabilities | P | P | P | P | U | U | U | P | conditional |
| EU26-06 | EU | scheduled mutation probability | P | P | U | U | U | P | U | U | conditional |

## Найважливіші блокери

- **USA26-01 / GESMR:** математична state transition відтворювана, але camera-ready raw runs, exact environment і однозначний stochastic protocol відсутні; paper має конфлікти 5/40 seeds і d=10/30. Тому можливий лише formula validation.
- **USA26-02:** native result залежить від спеціального S1 hardware, а literal numeric endpoint поза figure regeneration не заморожено. Це прямо порушує gates 7, 8 і 10.
- **USA26-06:** pseudocode має overlapping branches, cross-variable assignment і не задає initial/bounds; виконання потребувало б вигадування семантики.
- **EU26-01:** raw Zenodo data сильні, але exact policy ще не заморожена, а clean checkout author code зламаний absolute symlinks і unpinned IOHexperimenter.
- **EU26-02:** paper budget = 1 hour, official generator/archive = 3 hours; published table не можна однозначно прив'язати до одного protocol cell.
- **EU26-03:** A-NTGA має повну paper-level формулу local operator selection, але author artifact не містить exact paper configuration, seed ledger, raw 30-run outputs або LICENSE; inspected factory також не відтворює заявлений CreditRoulette selector буквально.
- **Виправлене виключення:** [L2-AGE optical-mode-sorter](https://repository.tudelft.nl/file/File_a1ff69e2-5aad-428b-8c6d-0421250aa314) (`10.1145/3583131.3590479`) вилучено, бо сама стаття визначає задачу як inverse problem / inverse design.

## Інженерне рішення

1. Не присвоювати score і не створювати штучний ranking.
2. Не запускати дорогі stochastic reproduction runs.
3. Зберегти GESMR як незалежну перевірку формул у Python та MATLAB/Octave з fixed random tape.
4. Повернутися до eligibility лише після отримання від авторів/архівів конкретного missing artifact або після пошуку нового direct-only кандидата, який проходить усі gates 3-10.
