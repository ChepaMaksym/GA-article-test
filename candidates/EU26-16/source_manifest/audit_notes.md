# EU26-16 source and data audit

Audit date: 2026-08-09.

## Source revision

The official repository's `v3.0` tag resolves to commit
`a800162492ee8ccb4e20f692b879610cb607db07`, tree
`8377a7be53e33bc6759cf079f22f30126dd50f83`, committed on 2020-09-24.
The paper links the repository but does not pin this tag or commit as its
historical execution revision. The candidate therefore calls it a selected
publication-era revision, not proven execution provenance.

The root `LICENSE.md` is the GNU GPL version 3. The verifier authenticates the
license and `Alg.java` plus the Yeast config/data members. No upstream bytes
are copied into this branch.

## Source semantics

`Alg.doControl()` rounds current best fitness, updates the historical best,
updates the historical population mean and guarded operator probabilities,
then checks for termination. The historical average is assigned before the
improvement guard, so a blocked rate update still records the new best
average. Equality follows the non-improvement branch.

The source implements guards, not saturation. Repeated updates from the
configured `.5/.5` point produce lattice endpoints near `.96/.04`, but the
source accepts an off-lattice `.95/.05` state and moves to `.97/.03`.
Candidate code and documentation keep that distinction explicit.

## Yeast manifest gap

The authenticated `cfg/Yeast.xml` declares three seeds: `10`, `20`, and
`100`. It references two train/test pairs. Only the two fold-1 ARFF members are
present. The fold-2 paths are absent, and folds 3–5 are not referenced.

The paper, by contrast, states that every reported result is averaged over a
random five-fold cross-validation procedure and ten seeds (50 executions).
It does not enumerate those ten seeds. Therefore the shipped config is not a
Table 7 execution manifest.

The fold-1 files are structurally coherent: their attribute declarations
contain 103 numeric inputs followed by the 14 binary labels listed in
`Yeast.xml`; 1,933 train rows plus 484 test rows equal the paper's 2,417
instances. This only authenticates one shipped partition.

## License boundary

The repository license is sufficient to inspect and test the authors' code.
The KDIS dataset page provides downloadable multi-label data and partitions,
but the audited page/repository does not state an upstream Yeast dataset
license or a chain of authority for redistributing/relicensing the input
records. The verifier therefore records `DATASET_LICENSE_UNRESOLVED` and uses
the data only for non-empirical structural inspection. It makes no Table 7
metric claim.
