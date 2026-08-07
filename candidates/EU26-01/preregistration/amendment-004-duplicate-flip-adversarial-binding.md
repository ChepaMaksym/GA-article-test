# Amendment 004 — duplicate-flip adversarial fixture binding

Recorded: 2026-08-07, before the source commit and all formal archive and
portability profiles.

Source audit in Amendment 003 identified the discriminating paper/source
case: paper `flip_l` requires `l` distinct flipped bits, while the unpinned
source dependency may return repeated indices whose flips cancel. The
fixed-tape fixture now contains an explicit `l=2`, indices `[0,0]` case and
requires both Python and MATLAB/Octave to reject it as non-paper-faithful.

This is adversarial test hardening only. It changes no paper cell, endpoint,
archive identity, published target, rounding rule or tolerance. It supersedes
only the formula/fixture digests listed in Amendment 002:

- fixture file SHA-256:
  `a9736e73557e89cf46cb5ea11c627fe24059419cd43d88af4fdda8d452f54fa6`;
- fixture result SHA-256:
  `556f836b2c851ad8e7eedaf9f962d28c1d63af68589340acf775d85108255381`;
- 64-case correctness digest:
  `f85ec78935f701bc7572a5fe78e7ce4cca7890fd7dcd158f04f19e6b611c7650`;
- 512-case timing formula digest:
  `e32f200a313633a53d67c262798b49d0a7478881ca3cfd78055fa3c42a0dea51`;
- combined timing endpoint digest:
  `3e25b9a9248c2e0a71b7b7085508fc539cc3987a11a73795665970a1a57dd124`.

All archive completion/statistics bindings in Amendment 002 are unchanged.
The paper-level status remains `BLOCKED_SOURCE_NATIVE_REPLAY`, eligibility
remains `conditional_noneligible`, and `PASS_FULL` remains forbidden.
