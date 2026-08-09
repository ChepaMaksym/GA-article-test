# EU26-11 source audit

Audit date: 2026-08-09. The claim and tolerances were frozen before candidate
implementation.

## Identity and licensing

The publisher PDF is 435,554 bytes with SHA-256
`28b1b3741fa03398b0e5fb2e343962540c74944f86240e94e9212e195b191da1`.
It identifies Leiden University, Netherlands, for the authors and states the
paper license as CC BY-NC-ND 4.0.

The paper's archival record is Zenodo `12756059`, DOI
`10.5281/zenodo.12756059`, deposited under CC BY 4.0. The selected point set
and the compact numeric block are individual immutable record members. No
upstream bytes are copied into this repository; CI fetches and authenticates
them in a temporary directory.

The optimizer source is `IOHprofiler/ModularCMAES` tag `v1.0.8`, commit
`ec517cafaca432444f781a1c463b43963bff05eb`, tree
`4200fc05eaa1a8eac4632aee3d0950ddf62cc75c`, under MIT. This is the version
named by the paper artifact scripts.

## Frozen endpoint

Figure 1 reports average base-10 logarithms of L2-star discrepancy. The
selected cell is `OPT-128` in dimension 20, displayed as `-4.16`. The
authenticated `Sub_Sobol_20_128.txt` member has 128 rows and 20 coordinates.
Independent application of the defining equation gives
`6.892638555983242e-05`; its base-10 logarithm is
`-4.1616144949364955`.

The authenticated `discr.pkl` contains a 5-by-20 binary64 data block. The
frozen row and column labels put `OPT-128`, 20D at the same
`6.892638555983242e-05` value. The verifier uses `pickletools` only to locate
the inert 800-byte block and `struct` to decode binary64 values. It never calls
`pickle.load`, pandas deserialization, or any artifact-controlled callable.

## Scope boundary

The paper also supplies a 2,731,257,856-byte `eaf.db` with the stochastic BBOB
runs. It is deliberately excluded from this targeted endpoint. Recomputing a
deterministic point-set statistic cannot validate EAF curves, AUC values,
optimizer performance, or all 24 functions. Successful checks therefore
remain narrower than a paper reproduction.
