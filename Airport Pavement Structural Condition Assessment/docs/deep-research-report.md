## 1. Стаття, ресурс і бібліографічні дані

**Назва статті:** *Using Genetic Algorithms to Improve Airport Pavement Structural Condition Assessment: Code Development and Case Study*

**Автори:** Alessia Donato, David Carfi

**Журнал:** *Information*, 2023, Volume 14, Issue 5, Article 286

**DOI:** `10.3390/info14050286`

**Офіційний ресурс статті:** https://www.mdpi.com/2078-2489/14/5/286

**DOI URL:** https://doi.org/10.3390/info14050286

**Локальний XML-файл статті:** `Using Genetic Algorithms to Improve Airport Pavement Structural Condition Assessment Code Development and Case Study.xml`

**Локальний Appendix A extraction:** `appendix/appendix_a_raw.xml`

Стаття описує MATLAB-підхід для оцінювання структурного стану гнучкого аеродромного покриття за даними виміряних прогинів поверхні. Основна задача полягає у зворотному розрахунку модулів пружності шарів покриття за допомогою Genetic Algorithm та моделі багатошарової пружної системи.

## 2. Основна суть статті

Стаття розглядає інженерну задачу типу **inverse problem**, або **back-calculation**. Відомою є реакція покриття на навантаження, тобто виміряні прогини поверхні. Невідомими є поточні модулі пружності шарів покриття `E1`, `E2`, `E3`.

Мета методу:

- використати виміряні deflections від HWD/FWD-тесту;
- задати геометрію покриття, навантаження та положення датчиків;
- за допомогою forward model розраховувати прогнозовані прогини для кандидатних `E1`, `E2`, `E3`;
- за допомогою Genetic Algorithm знайти такі `E1`, `E2`, `E3`, які мінімізують різницю між розрахованими та виміряними прогинами.

У продуктовому сенсі стаття описує decision-support інструмент для pavement engineer: система приймає виміряні прогини та параметри конструкції, а на виході надає оцінені модулі шарів, які характеризують structural condition pavement.

## 3. Що означають `E1`, `E2`, `E3`

`E1`, `E2`, `E3` - це модулі пружності шарів покриття, одиниця виміру MPa.

Вони не є різницями, похибками або готовими відповідями таблиці. Це фізичні параметри моделі:

- `E1` - модуль пружності верхнього шару покриття;
- `E2` - модуль пружності базового шару;
- `E3` - модуль пружності нижнього шару, тобто subgrade.

Великі значення `E` означають жорсткіший або міцніший шар. Малі значення `E` означають слабший або більш деформівний шар.

У forward calculation `E1`, `E2`, `E3` є вхідними параметрами, бо модель за ними рахує deflections. У back-calculation вони є невідомими змінними пошуку, які підбирає GA.

## 4. Відомі параметри задачі

У реальному case study зі статті відомими вважаються геометрія, навантаження, положення датчиків і виміряні прогини.

З Table 5:

| Параметр | Значення | Зміст |
|---|---:|---|
| `h1` | `0.155 m` | товщина верхнього шару |
| `h2` | `0.22 m` | товщина базового шару |
| `h3` | `infinity` | нижній напівнескінченний subgrade |
| `nu1` | `0.35` | коефіцієнт Пуассона верхнього шару |
| `nu2` | `0.35` | коефіцієнт Пуассона базового шару |
| `nu3` | `0.45` | коефіцієнт Пуассона subgrade |
| `F` | `164.2 kN` | прикладена сила |
| `a` | `0.15 m` | радіус круглої плити навантаження |

Sensor positions та measured deflections:

| Sensor | `r`, m | `D`, mm |
|---:|---:|---:|
| 1 | `0` | `0.488` |
| 2 | `0.2` | `0.396` |
| 3 | `0.3` | `0.372` |
| 4 | `0.45` | `0.327` |
| 5 | `0.9` | `0.228` |
| 6 | `1.2` | `0.180` |
| 7 | `1.5` | `0.143` |
| 8 | `1.8` | `0.112` |

Ці параметри є нормальними вхідними даними для back-calculation. Товщини шарів зазвичай беруться з проєктної документації, as-built records, pavement management database, core samples або GPR-досліджень. Стаття подає їх як `Data input`.

## 5. Роль плити навантаження

Жовта плита на схемах HWD/FWD не моделюється як окремий шар покриття. У статті вона врахована як спосіб прикладання навантаження до поверхні.

Модель не вводить `E_plate`, `h_plate` або `nu_plate`. Замість цього вона задає:

- `F` - сила навантаження;
- `a` - радіус круглої контактної області.

Для діаметра плити `300 mm` радіус становить:

```text
a = 150 mm = 0.15 m
```

Таким чином, плита входить у модель як boundary condition: рівномірно розподілений тиск на круглій площі. Шари покриття починаються нижче поверхні, а саме:

```text
loading plate -> circular load over radius a
top layer -> h1 = 0.155 m
base layer -> h2 = 0.22 m
subgrade -> h3 = infinity
```

## 6. Методологія статті

Стаття використовує два пов'язані рівні розрахунку.

**Forward calculation**

Forward model приймає `E1`, `E2`, `E3`, геометрію шарів, навантаження та положення датчиків. На виході отримуються calculated deflections.

```text
E1/E2/E3 + h + nu + load + sensors
        -> MLET forward model
        -> calculated deflections
```

**Back-calculation**

Back-calculation виконує протилежну задачу. Відомими є measured deflections, геометрія, навантаження та sensors. Невідомими є `E1`, `E2`, `E3`.

```text
measured deflections + known geometry/load
        -> GA tries candidate E1/E2/E3
        -> forward model computes deflections
        -> fitness compares calculated vs measured
        -> GA returns best E1/E2/E3
```

Fitness function у case study відповідає мінімізації суми квадратів різниць між calculated та measured deflections:

```text
fitness = sum((d_i - D_i)^2)
```

де `d_i` - розрахований прогин, а `D_i` - виміряний прогин у відповідному sensor position.

## 7. Genetic Algorithm у статті

GA використовується як оптимізаційний метод для пошуку модулів шарів. Один кандидат GA є набором:

```text
[E1, E2, E3]
```

Алгоритм:

1. Створює початкову population кандидатних наборів `E1/E2/E3`.
2. Для кожного кандидата викликає forward calculation.
3. Обчислює fitness як різницю між calculated та measured deflections.
4. Обирає кращих кандидатів.
5. Формує нові покоління через reproduction, crossover та mutation.
6. Зупиняється після досягнення tolerance, stall condition або generation limit.

У статті зазначено, що для таких задач хороше рішення часто досягається за малу кількість generations, зазвичай менше 10.

## 8. Validation і case study у статті

**Direct validation**

У Section 4.1 автори порівнюють deflections, розраховані MATLAB-кодом, із KENPAVE. Мета - перевірити forward model.

**Indirect check**

У Section 4.2 автори беруть deflections, отримані з KENPAVE, і перевіряють, чи GA може повернути відомі модулі. Найкращий результат з Table 4:

```text
E1 = 2010.584 MPa
E2 = 99.877 MPa
```

Це близько до очікуваних:

```text
E1 = 2000 MPa
E2 = 100 MPa
```

**Airport case study**

У реальному airport pavement case study Table 6 analysis (5) дає:

```text
E1 = 5850.679 MPa
E2 = 3615.922 MPa
E3 = 208.747 MPa
fitness = 2.34 x 10^-10
```

Reported calculated deflections:

```text
[0.4853, 0.4020, 0.3666, 0.3262, 0.2309, 0.1841, 0.1487, 0.1222] mm
```

Ці значення близькі до measured deflections із Table 5.

## 9. Порівняння з іншими програмами

Table 7 порівнює результати Software GA зі значеннями BackGenetic3D та ELMOD.

| Modulus | BackGenetic3D, MPa | ELMOD, MPa | Software GA, MPa | Error vs BackGenetic3D | Error vs ELMOD |
|---|---:|---:|---:|---:|---:|
| `E1` | `5770.913` | `5024.1` | `5850.679` | `1.3%` | `16.4%` |
| `E2` | `3840.381` | `3756.7` | `3615.922` | `5.8%` | `3.7%` |
| `E3` | `227.527` | `231.5` | `208.747` | `8.2%` | `9.8%` |

Інтерпретація статті: результати ближчі до BackGenetic3D, оскільки BackGenetic3D також використовує genetic algorithm, тоді як ELMOD використовує інший iterative approach.

## 10. Стан локальної MATLAB-реплікації

У локальній папці вже зроблено:

- внесено article-backed constants з Tables 1-7 у MATLAB-файли;
- додано consistency checks проти локального XML;
- додано `run_replication_study.m`, який формує replication report;
- додано `run_ga_surrogate_backcalculation.m`, який реально запускає `MATLAB ga()`;
- додано `sandbox/results/replication_report.md`;
- додано `sandbox/results/ga_surrogate_report.md`.

Поточний GA sandbox виконує реальну оптимізацію, але використовує surrogate forward model, а не повністю відновлений Appendix A MLET solver. Тому його слід трактувати як робочий тестовий стенд GA, а не як повну наукову реплікацію статті.

## 11. Поточні результати локального sandbox

Direct MATLAB vs KENPAVE check:

```text
max difference = 0.0036 mm
max percent difference = 2.18%
```

Indirect GA check from reported Table 4:

```text
E1 error = 0.529%
E2 error = 0.123%
```

Airport case-study deflection comparison:

```text
max residual = 0.0102 mm
SSE from rounded deflections = 2.3484e-10 m^2
reported fitness = 2.34e-10
```

Executable GA sandbox:

```text
method = MATLAB ga()
best E = [5815.222, 3063.328, 266.063] MPa
fitness = 1.01458e-10
max residual = 0.0073 mm
```

Цей результат показує, що GA pipeline працює технічно. Водночас відмінність від Table 6 за `E2` та `E3` підтверджує, що для повної реплікації потрібен саме оригінальний MLET forward model з Appendix A.

## 12. Виявлені зауваження до статті та XML

1. У тексті Section 6 сказано, що population має бути не меншою за 20, але Table 6 analysis (4) використовує population `5`.
2. У Section 6 модулі записані як `5,850,679 MPa`, `3,615,922 MPa`, `208,747 MPa`. За Table 6 і Table 7 очевидно, що коректна інтерпретація: `5850.679`, `3615.922`, `208.747 MPa`.
3. Деякі відсоткові похибки Table 7 не збігаються зі стандартним округленням до одного знака після коми. Ймовірно, вони були усічені або розраховані з прихованою точністю.
4. Appendix A у XML подано як MathML/XML, а не як чистий MATLAB `.m` файл. Це блокує повну автоматичну реплікацію без ручного або програмного відновлення коду.

## 13. Що потрібно зробити для повної реплікації

Для повної наукової реплікації необхідно:

1. Відновити Appendix A у чистий MATLAB-код.
2. Виділити окрему функцію forward model, наприклад `mlet_forward.m`.
3. Підключити `mlet_forward.m` до fitness function.
4. Запустити `ga()` з параметрами Table 4 та Table 6.
5. Порівняти отримані `E1/E2/E3`, calculated deflections і fitness зі значеннями статті.
6. Окремо зафіксувати всі розбіжності між локальним запуском, XML-джерелом і опублікованими таблицями.

## 14. Висновок

Стаття пропонує optimization-based back-calculation метод для оцінювання структурного стану аеродромного покриття. Відомими є геометрія шарів, навантаження, положення датчиків і виміряні прогини. Невідомими є модулі пружності `E1`, `E2`, `E3`, які характеризують поточний стан шарів. Genetic Algorithm підбирає ці модулі, мінімізуючи різницю між розрахованими та виміряними прогинами.

Локальна робота вже формує article-backed replication package і демонструє executable GA workflow. Повна реплікація потребує наступного ключового кроку: відновлення справжнього MLET forward model з Appendix A у робочий MATLAB-код.
