# EU26-17 amendment 002 — algorithm-addition object resolution

Recorded: 2026-08-09, after the first authenticated Git-object probe and before
committing the implementation.

The original contract records the supplied algorithm-addition revision token
`cefd949488dbe23c030f17bb50b6c7c73a44ae3`. That token contains 39 hexadecimal
characters, so it is a Git object-name prefix rather than a full SHA-1.

Against the authenticated author repository, the prefix resolves uniquely to:

- full commit: `cefd949488dbe23c030f17bb50b6c7c73a44ae3a`;
- tree: `0146522f95e1ae49cb2bfac1b082e972056e5ea6`.

The tree is exactly the tree frozen in the original contract. No algorithm
source identity, transition equation, eligibility gate, or claim boundary
changes. Overall status remains **`HARD_FAIL`** because G8 still lacks a
literal unambiguous numeric optimizer result cell.

## Effective verification rule

The verifier must retain the original 39-hex token as
`requested_revision`, resolve it through the candidate author repository, and
require all of the following:

1. the resolved object is a commit;
2. the resolution is unique in that object database;
3. its full SHA-1 is exactly
   `cefd949488dbe23c030f17bb50b6c7c73a44ae3a`;
4. its tree is exactly
   `0146522f95e1ae49cb2bfac1b082e972056e5ea6`;
5. the authenticated SAGA1 member identities still match the auditor-freeze
   member identities.

Both the requested prefix and resolved full SHA must appear in the evidence
report. A missing object, ambiguous prefix, different full object, different
tree, or different member is a hard source-identity failure. The prefix must
never be printed or described as a full commit SHA.
