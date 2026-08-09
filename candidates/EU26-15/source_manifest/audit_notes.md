# EU26-15 source audit notes

## Repository identity and chronology

The audited repository is <https://github.com/Greco-Lab/GARBO>. The current
audited head is commit `9727e017371484dd5837a0859b41c195a87fd8d0`
(tree `995ee6c51315ea52d0e82211fb708e32b45800bb`). That commit only added the
GPL-3.0 `LICENSE` on 2024-11-05.

The preceding commit
`1854385ffb0be85ef8deeeda45980aaed6e50207`, dated 2020-01-25, is the
paper-era source snapshot. Its `GARBO.py` and `runGARBO.py` Git blobs and
SHA-256 hashes are identical to those at the licensed revision. It has tree
`2c5240ae8ec6396db3a3ff15586cb23c7be83ed3` and no license file. There are
no tags or GitHub releases, so the later licensed commit is the executable
source identity for this audit and the earlier commit is identity evidence,
not a separately licensed checkout claim.

No functional source commit follows the January 2020 upload. Therefore no
post-paper algorithm change was found; the relevant drift is packaging and
licensing chronology rather than changed fuzzy logic.

## Exact transition loci in `GARBO.py`

- sampled universes and membership functions: source lines 37–118;
- antecedent interpreters: lines 120–140;
- crossover 9-rule system: lines 142–169;
- mutation 9-rule system and `intFV(ft_input)` quirk: lines 171–198;
- insertion/deletion systems and substitution calculation: lines 200–262;
- feature-rank 9-rule system: lines 264–291;
- pairwise Jaccard similarity: lines 456–472;
- initial `cxpb`, `mutpb`, `mutop`: lines 655–658;
- population statistics and strict similarity override: lines 823–841.

Line numbers refer to the exact 35,668-byte `GARBO.py` in the manifest.

## RNG and replay audit

`runGARBO.py` calls `random.seed(64)` and derives floating Python seeds for
each island. `GARBO.island` calls `random.seed(seed)`. This does not seed
NumPy's independent global RNG, although GARBO uses `np.random` for initial
chromosome lengths, binomial masks, feature choices, crossover decisions,
and other operators. Consequently the released driver is not exactly
repeatable even when its visible Python seed is held constant.

The repository contains no committed paper fold identities, full seed
ledger, raw island pickle results, or paper aggregation ledger. The README
describes user-created `train_ge_$SLURM_ARRAY_TASK_ID.csv` inputs, but those
split files are absent.

## Data boundary

At the licensed revision, `data_ccle_erl_ge.csv` has 217 data rows and 1,600
header fields; the final field is `class`. `load_data_layer` removes that
field and exposes the remaining 1,599 columns to feature selection. This is
adequate to establish the decision dimension.

The code's GPL-3.0 file does not by itself establish the upstream provenance
and redistribution terms of the biological measurements. The CSV is not
copied into this candidate package, the test suite does not require it, and
the optional structure probe cannot promote its license status.

## Runtime boundary

The README requires Python 2.7 and names sklearn, deap, NumPy, scikit-fuzzy,
SciPy, pandas, and other modules without versions. `cPickle` imports prevent
direct Python 3 execution. The clean-room verifier therefore checks only the
deterministic formula transition and never claims source-native empirical
replay.
