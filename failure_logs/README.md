# Failure evidence

Цей каталог зберігає канонічні записи двох невдалих числових
реплікацій:

- [`EU-001_failure.md`](EU-001_failure.md);
- [`USA-001_primary_failure.md`](USA-001_primary_failure.md);
- [`Failure_Log.csv`](Failure_Log.csv).

## USA-001 compact bundle

[`USA-001_evidence/`](USA-001_evidence/) є immutable compact evidence
bundle. Його 25 manifest entries перевіряються за byte length і SHA-256.
CSV-файли навмисно зберігаються Git byte-for-byte, оскільки hashes
включають початкові line endings.

`USA-001_evidence/source_manifest.md` є історичним snapshot опису
ізольованого source archive до видалення candidate folder. Згадані там
PDF, XML, Git checkout, implementation та instance files не присутні в
поточному bundle; їхні pre-deletion hashes лишилися в manifests.

Не редагуйте файли всередині bundle без окремої процедури re-manifest і
чіткої причини: звичайне форматування зламає evidence hashes.

## EU-001 limitation

Для EU-001 збережено narrative failure record і summary row, але немає
compact raw-evidence bundle, повного hash inventory або локальних raw
runs. Тому числовий висновок EU-001 не можна незалежно перерахувати лише
з поточного репозиторію.
