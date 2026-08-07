# Amendment 003 — paper `flip_l` versus unpinned source dependency

Recorded: 2026-08-07, before the source commit and all formal archive,
Work4, Work8 and GitHub4 profiles.

This amendment records a source audit finding. It changes no target,
statistic, tolerance, archive identity, fixed tape or acceptance gate.

The paper defines `l` as the number of flipped bits and states that
`flip_l(x)` flips `l` bits chosen uniformly at random. The clean-room formula
kernel therefore requires `l` distinct indices, as already frozen in v1.

Frozen `src/gsemo.hpp` defines a distinct-index helper `bitflip_index`, but the
actual optimizer calls a different helper, `bitflip`, which iterates over
`ioh::common::random::integers(l,0,n-1)`. The exact IOHexperimenter revision
is not published. In the available IOHexperimenter implementation that API
returns `l` independent uniform integers with replacement, so the same index
can occur twice and two flips can cancel. Because the dependency revision is
unidentified, source behavior cannot be proven equivalent to paper
`flip_l`.

Python and MATLAB/Octave remain paper-faithful on this point: their explicit
tapes reject duplicate flip indices. This supplies formula evidence only and
adds a source-native claim blocker. Overall status remains
`BLOCKED_SOURCE_NATIVE_REPLAY`, eligibility remains
`conditional_noneligible`, and `PASS_FULL` remains forbidden.
