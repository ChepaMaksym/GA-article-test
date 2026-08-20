# Amendment 002 - Intel macOS portability runner

Date: 2026-08-20

This amendment is committed before any EU26-25 optimizer row exists.

The machine-readable portability matrix originally named `macos-14`. PyVRP
0.5.0 predates the current arm64 runner/wheel ecosystem. To test the frozen
release rather than an unrelated architecture port, the macOS member is changed
to the Intel runner `macos-13`.

The three independent operating-system families remain:

```text
ubuntu-24.04
macos-13
windows-2022
```

No OLD seed, iteration budget, BKS, formula, acceptance gate, HYBRID boundary or
statistical rule changes. Portability remains an engineering smoke test and is
not used as evidence of equal wall-clock speed.
