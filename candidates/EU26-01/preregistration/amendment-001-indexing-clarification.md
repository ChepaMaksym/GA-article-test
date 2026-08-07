# Amendment 001 — literal Algorithm 2 indexing count

Recorded: 2026-08-07, after the v1 outcome-blind freeze and before formal
archive or portability execution.

This amendment changes no policy, target, tolerance, archive identity or
claim status. It makes one arithmetic consequence explicit.

Algorithm 2 is printed with one-based offspring indices `i=1,...,lambda` and
the condition `i < floor(lambda/2)`. At the frozen `lambda=10`, a literal
reading assigns the low rate only to `i=1,2,3,4`: **4 low-rate and 6
high-rate children**. The surrounding paper prose says half the children use
each rate, while frozen source commit
`fbe1d3ed3064dedd85ba3c5eaf78fe4ea3d6b380` uses zero-based
`i < lambda/2`: **5 low-rate and 5 high-rate children**.

The v1 contract already froze the prose/source 5/5 interpretation. This
clarification records the alternative literally printed 4/6 interpretation
and reinforces that formula success is source/prose-faithful, not a unique
paper-faithful replay. Every formal overall report must retain the string
`literal_one_based_pseudocode_4_low_6_high_vs_prose_and_source_5_low_5_high`.
The overall status remains `BLOCKED_SOURCE_NATIVE_REPLAY`, eligibility remains
`conditional_noneligible`, and `PASS_FULL` remains forbidden.
