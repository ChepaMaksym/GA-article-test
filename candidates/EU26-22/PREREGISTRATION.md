# Preregistration - EU26-22 MOEA-ISa

Date: 2026-08-19

## Frozen source identity

- paper DOI: `10.1016/j.asoc.2022.109420`
- paper-linked repository: `xueyunuist/MOEA-ISa`
- source commit: `e0f2f2312d18b9dccde5f707ea84b10a6c030a02`
- `MOEAISa.m` blob: `6d3c2f75731f3b1e5ce67af9ecacb83d9c675e9f`
- `EnvironmentalSelection.m` blob: `370d777362fc45dc49bd05076daa17a17ad13bc0`
- `run.m` blob: `7282ccff1689c0b668776a4bd16faa3085a5a289`
- `main.m` blob: `315c9b6c206ea5ac9a29c9f2c55d959edba04645`

No upstream source or dataset bytes are copied into this repository.

## Frozen experiment facts

- binary feature mask dimension: dataset feature count, 100 to 7,129;
- objectives: classification error and selected-feature ratio;
- population: 100;
- evaluation budget requested by released runner: 10,000;
- independent-run claim: 30;
- classifier/source environment: paper-linked PlatEMO MATLAB profile;
- adaptive locus: crossover cardinality conditioned on Jaccard parent state and a learned state-action success table.

## Gates

- P0 source identity and legal provenance
- P1 dataset identity, dimensions and labels
- P2 fixed-tape formula equivalence
- P3 source-runner defect classification
- P4 deterministic seed and split ledger
- P5 selected paper endpoint and tolerance frozen outcome-blind
- P6 30-run OLD numerical campaign
- P7 independent replay and statistics
- P8 OS/runtime/worker portability

P6 is forbidden until P0-P5 pass. HYBRID is forbidden until P6-P7 pass.

## Acceptance language

Passing P2 establishes only `PASS_OLD_FORMULA_KERNEL`. It does not establish paper-table reproduction, source-native historical equivalence, wall-clock speedup or scientific superiority.
