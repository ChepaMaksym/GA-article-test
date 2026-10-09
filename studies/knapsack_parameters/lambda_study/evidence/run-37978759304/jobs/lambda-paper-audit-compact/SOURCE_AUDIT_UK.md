# Обмежений аудит джерел λ

Статус: `BOUNDED_SOURCE_AUDIT`. Числове відтворення: `NOT_EXECUTED`; повний допуск: `BLOCKED`.

Одержання та перевірки виконуються лише у GitHub Actions. Для успішно перевірених джерел маніфест звіряє кожний файл із Git blob SHA-1 за фіксованим commit і записує SHA-256 та довжину. Збережені ліцензії та помилки одержання перелічено в audit-report.json.

Доступність: `{"author_sources_verified": true, "input_sources_verified": true, "ising_all_verified": true, "paper_acquired": true, "licenses_preserved": true, "bounded_pilot": true}`.

Очікувано 1400 файлів ISG для n∈{16,25,36,49,64,81,100}, індексів 0–199; перевірено 1400, з них аналізованих 700 із 700 індексів 100–199. Для успішних записів перевірено формат, топологію та енергію записаного свідка; глобальна мінімальність незалежно не доведена.

Python-журнали містять base seed; фактичний seed кожного run дорівнює base+run для random і numpy. C++ cfg/dat зберігають batch seed, кількість рядків, split parts, відкидання перших 100 ISG і аналізове цензурування на 2 100 000 000. Цензурування не є правилом зупинки replay. Один RNG проходить попередні run; їх пропуск або рання зупинка змінюють наступний стан.

`source_semantics` фіксує Python ties-to-even, C++ half-up, повний пул мутантів Python, 1.1067 у C++, reset, подвійне додавання нового найкращого на нічиїх і hardcoded graphs. eval_limit читається через atoi(int), потім size_t: запис 100 млрд не підтверджує фактичний ліміт.

Повний каталог конфігурацій і seed: `audit-report.json`; checksums: `source_manifest.json` та `file_manifest.json`. Paper coverage відокремлено від числової реплікації. PDF SHA-256 зафіксовано після одержання з реєстрованої URL; PDF не комітиться.

## Невирішені умови повної серії

- full execution and resources are not authorized by this protocol
- paper-to-config/seed/input/raw-statistic mapping is not yet complete for every experiment
- printed algorithm and Python/C++ source semantics require explicit separate profiles
- original compiler/standard-library RNG environment is not established
- large declared C++ limits pass through atoi(int); actual historical limit is unverified
- exact C++ batch RNG requires prior runs and original stopping semantics, not analysis censoring
- hardcoded plot values and processed Graphs/Landscape_experiments need exact raw-batch/seed mapping
- no independently proven optimum preprocessing provenance for supplied Ising energy metadata
- retained inputs, licenses and CI artifact expiry require retention review before cleanup
