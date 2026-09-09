# Межа внеску та перевірка пов'язаних досліджень

Стан перевірено 2026-09-08. PR використано для навігації до версіонованого коду
й протоколів, не як наукові першоджерела. Інші PR не змінювалися.

| Дослідницька лінія | Першоджерело та роль | Відмінність від нового PR19 bridge |
| --- | --- | --- |
| PR8 / EU26-07 | Hevia Fajardo–Sudholt: керування параметрами `(1+(λ,λ))`, у репозиторії — відтворення на Jump | Теоретична й механістична база; не новий результат вибору ознак Census |
| PR19 / EU26-21 | Altarabichi et al.: CHC-QX та qualitative approximation для вибору ознак | Новий bridge порівнює гармонізовані пошукові компоненти зі спільною WBA-ціллю, не повний pipeline QX |
| Закритий PR23 / EU26-27 | Ye et al.: адаптація мутації GSEMO в багатокритеріальному пошуку | Відтворення TwoRate на OneMinMax; інші стан пошуку, objective та критерій завершення |
| PR26 / EU26-27 v3 | Протокол доповнює TwoRate керуванням розміром потомства | Зберігає TwoRate mutation, добирає cap на development seeds і перевіряє holdout; це не mutation/crossover-пошук масок Census |
| Закритий PR27 | Попередній рукопис для EU26-27 | Організаційно пов'язаний документ, не незалежне наукове підтвердження PR19 |

Перевірені ревізії: PR8 `e981c13bc4763b26f2e00da9c30047fc38eb9a29`,
PR23 `a45d37d80500fbe87c9099d0e1b591b78e8a68e4`,
PR26 `d505ec09dee0cad079757786e6e95adae5b5eb60`,
PR27 `eb072d8290c0dfa40d187962e3a55d8f5bd54273`.
Для PR26 прочитано [версію протоколу v3](https://github.com/ChepaMaksym/GA-article-test/blob/d505ec09dee0cad079757786e6e95adae5b5eb60/candidates/EU26-27/hybrid_v3/preregistration/PROTOCOL.md).

Запозиченими є сам GA, множинні mutation/crossover фази, правило успішності
1/5, CHC, дерево рішень та bootstrap. Їх не оголошуємо винаходом. Власний
інкрементальний внесок — специфікація перенесення, спільна одиниця оцінки,
контрольований paired-протокол, перевірювані моделі й емпірично визначена межа
застосовності висновку. Подібне правило оновлення λ в PR26 означає спільне
джерело параметричного керування, а не тотожний алгоритм або експеримент.

Цей огляд розрізняє конкретні репозиторні роботи. Він не є вичерпним світовим
систематичним оглядом і не доводить абсолютного пріоритету комбінації.
Формулювання «перший у світі», «новий фундаментальний GA», «доведене
універсальне прискорення» не підтримуються.

Першоджерела:

1. Hevia Fajardo, M. A.; Sudholt, D. *Theoretical and Empirical Analysis of
   Parameter Control Mechanisms in the (1+(λ,λ)) Genetic Algorithm*.
   [DOI 10.1145/3564755](https://doi.org/10.1145/3564755),
   [авторський повний текст](https://mhevia.com/assets/pdf/journal_oplclga.pdf).
2. Altarabichi, M. G.; Nowaczyk, S.; Pashami, S.; Mashhadi, P. S. *Fast Genetic
   Algorithm for feature selection – A qualitative approximation approach*.
   [DOI 10.1016/j.eswa.2022.118528](https://doi.org/10.1016/j.eswa.2022.118528),
   [авторський повний текст](https://arxiv.org/pdf/2404.03996).
3. Ye, F.; Neumann, F.; de Nobel, J.; Neumann, A.; Bäck, T. *Towards
   Self-adaptive Mutation in Evolutionary Multi-Objective Algorithms*.
   [Авторський запис і повний текст](https://arxiv.org/abs/2303.04611).
