# Швидка fail-closed перевірка GA

Цей каталог містить новий prospective verification harness. Він не
переписує історичні USA-001/EU-001 результати й не відновлює видалені
candidate implementations.

## Що було повільним

У USA-001 primary та Q1–Q3 один run 8 споживав 90–92% часу кожного
профілю, бо після вже пропущеного published deadline на generation 2000
він продовжувався до generation 100000. Повний історичний algorithm time
становив 8529.1 s, або 142.2 min.

Новий порядок:

1. усі незмінні run IDs, instances і три algorithmic RNG streams
   виконуються до generation 1000;
2. P1 перевіряється точно на published checkpoint;
3. лише unresolved runs продовжуються до generation 2000;
4. якщо required P2 хибний, повертається `FAIL_DECISIVE`;
5. generation 100000 запускається лише якщо всі попередні required
   milestone gates пройдено;
6. лише terminal stage може повернути `PASS_FULL`.

Qualification не має стану `PASS`: дозволені лише `PROCEED` та
`FAIL_DECISIVE`. Тому скорочення може раніше довести невдачу, але не може
створити хибний успіх. Final run count, три algorithmic seeds, maximum
budget і tolerances не змінені. Окремий сталий `analysisSeed=202234500`,
який уже є в retained raw ledgers, лишається non-algorithmic metadata.

## Налаштування для цього ПК

- Dell G3 3579, Intel i5-8300H: 4 physical / 8 logical cores;
- 31.86 GiB RAM, приблизно 20 GiB були вільні під час аудиту;
- MATLAB R2026a Update 4, Parallel Computing Toolbox, limit 4 workers;
- рекомендовано один `parpool("Processes",4)` на весь suite;
- 3 workers — якщо ПК має залишатися responsive;
- 8 workers і nested `parfor` не використовуються;
- GTX 1050 зараз недоступна MATLAB через `OldDriver` і не входить у план;
- на SSD C: лишалося 13.04 GiB, workspace синхронізується OneDrive, тому
  checkpoints записуються атомарно в `tempdir`, а не live-CSV у workspace.

Session measurement від 2026-07-30 на 12 deterministic GA-like runs
(однаковий checksum; це не універсальний benchmark):

| Mode | Workers | Time, s | Speedup | Checksum |
|---|---:|---:|---:|---|
| serial | 1 | 4.231843 | 1.000× | identical |
| processes | 2 | 2.530294 | 1.672× | identical |
| processes | 3 | 2.119984 | 1.996× | identical |
| processes | 4 | 1.805608 | **2.344×** | identical |
| threads | 4 | 1.995641 | 2.121× | identical |

Retained-ledger projection: 15.1 min staged serial, theoretical
barrier-model lower bound 4.7 min, greedy-LPT projected makespan 5.3 min,
empirical compute estimate about 6.4 min, and roughly 7–9 min end-to-end
with pool startup, tests, cache validation and hashing. Це estimate, не
обіцянка runtime.

## Команди

```matlab
cd verification
run_fast_verification_tests
verify_retained_evidence
analyze_historical_runtime
run_fast_verification_demo(true)
```

`verify_retained_evidence` перевіряє SHA-256 усіх 25 manifest-listed
evidence files (плюс читає сам manifest), арифметику P1–P4 та final
failure status за секунди, не запускаючи видалений алгоритм.

## Adapter contract

Для майбутнього candidate, допущеного новим пошуком або re-audit:

```matlab
checkpoint = adapter(runId, frozenSeedLedger, targetGeneration, priorCheckpoint)
options.AdapterFiles = ["my_adapter.m"; "my_algorithm.m"];
options.AdapterConfiguration = struct("profile", "paper_faithful");
contract = fastverify.bind_adapter(contract, adapterHandle, options);
report = fastverify.run_staged(adapterHandle, contract, options);
```

Adapter мусить повернути run/full-seed-ledger identity, reached generation,
first-perfect generation, reported iteration, objective, evaluation
count, terminal flag, повний resume state та RNG state. Harness:

- canonicalizes results by frozen run order;
- writes no shared worker files;
- commits each MAT checkpoint atomically with a SHA-256 sidecar;
- rejects missing, truncated, corrupted, wrong-seed or wrong-contract
  cache;
- hashes the declared adapter wrapper/implementation files and immutable
  adapter configuration into the contract and cache key;
- derives a typed SHA-256 over the complete checkpoint state instead of
  trusting an adapter-supplied digest;
- continues only from an integrity-checked previous state.

Для canonical state hash підтримуються numeric, logical, char, string,
struct і cell values; інший MATLAB type відхиляється fail-closed.

`fastverify.usa001_contract()` is the exact P1/P2/P3/P4 example. Actual
USA-001 MATLAB sources were previously deleted as required, so an
end-to-end timing claim for that implementation cannot be rerun without a
backup/OneDrive restore. The harness is ready to integrate into the next
candidate admitted by a new search or documented re-audit. If a different
pool type is already open, the harness fails explicitly instead of silently
reusing it.
