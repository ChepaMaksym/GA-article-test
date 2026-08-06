# Direct adaptive-GA cohort 2026

Цей каталог містить рівно 12 нових primary records: 6 USA + 6 EU. Усі задачі пройшли окремий direct-only scope gate; inverse problems, parameter estimation через forward model і hidden-state/source reconstruction не займають місце у cohort.

## Визначення adaptive GA

Канонічні hard gates 3-10 збережені в `gate_definitions.json` і застосовані окремо до кожної статті в `hard_gate_assessments.json`:

3. фактична зміна GA parameter/operator під час run;
4. не лише surrogate/fitness/forward-model adaptation;
5. повна семантика адаптації: rule, initial/min/max, frequency, order, trigger і boundaries;
6. повний GA pipeline;
7. законні відтворювані inputs без required closed hardware/solver/CFD/FEM;
8. literal numeric published target;
9. run count, stochastic protocol і provenance;
10. MATLAB clean-room feasibility та, коли заявлено авторський artifact, source-native replay.

`pass` означає, що всі складові конкретного gate доведені. `unresolved` означає evidence gap або source conflict. `fail` означає доведену невідповідність замороженому правилу.

## Поточний результат

- `hard_pass`: 0;
- `conditional_noneligible`: 10;
- `hard_fail`: 2;
- `ranking.csv`: навмисно порожній, крім заголовка;
- published-result reproduction runs: не запускаються, бо немає eligible candidate.

GESMR (`USA26-01`) має окремий Python + MATLAB/Octave clean-room scaffold для перевірки формул. Це `FORMULA_VALIDATION_ONLY`, а не reproduction outcome.

## Перевірка

```bash
python registry/cohort_2026_12/validate_registry.py
python registry/cohort_2026_12/tests/run_registry_tests.py
```

Validator fail-closed перевіряє квоту, унікальність DOI/ID, відсутність дублів старого cohort, direct-only scope, dimension >=11, повноту gate fields, derivation статусу, заборону score для noneligible records і точну відповідність порожнього ranking нульовій множині `hard_pass`.

Candidate-specific immutable revision/hash audits зберігаються в `audits/`; вони не перетворюють evidence gap на `pass`.
