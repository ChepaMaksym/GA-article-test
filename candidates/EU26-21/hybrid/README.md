# HYBRID blocked until EU26-21 OLD passes

This directory is intentionally documentation-only.

No executable PR #8 hybrid may be added until:

1. the pinned CHC-QX source campaign passes the preregistered Census-Income numerical gate;
2. an independent printed-paper CHC-QX implementation is completed and verified;
3. source/paper divergences are explicitly resolved;
4. the candidate receives `PASS_OLD_FULL`.

A successful smoke seed or source-only pass is not sufficient.

The later hypothesis, if OLD passes, is to freeze the CHC-QX data, surrogate, classifier, split, control frequency, and evaluation budget, then replace only the binary feature-mask optimizer with the verified PR #8 `(1+(lambda,lambda))` mechanism. That hypothesis is not implemented here.
