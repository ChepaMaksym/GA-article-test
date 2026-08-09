# EU26-14 amendment 001: static pickle reducer scope and verifier hardening

**Recorded:** 2026-08-09, after implementation and before PR publication

**Scope:** parser semantics and verifier/CI fail-closed controls only

**Endpoint/claim effect:** none

## Why this amendment exists

The frozen preregistration was internally inconsistent: it required parsing
the selected NumPy protocol without executing constructors, but also said that
every reducer and object-construction path must reject. The frozen payload uses
`REDUCE` and `BUILD`, so a static, non-executing interpreter cannot both parse
the payload and literally reject every such opcode. Commit
`aaefd1605d49e85077c59f44c2eb45018c88fe30` rewrote the two frozen Markdown
files after implementation to clarify this point. That edit obscured timing.
Those files are restored byte-for-byte here, and this separately dated
amendment records the only permitted interpretation.

This amendment also records hardening findings discovered during independent
pre-PR review: contract constants must be byte-frozen; exact pickle state must
reject Python numeric type confusion; ancestor symlinks must reject; the
cross-language finalizer must authenticate its report structure and digest;
and the complete artifact integration must be an automatic PR gate.

## File identity and timing

| File | Frozen SHA-256 (`7be60d2`) | Transient post-freeze SHA-256 (`aaefd16`) | Live disposition |
|---|---|---|---|
| `preregistration/eligibility_audit.md` | `31b24b2ee88edddb068ddaf4d9aeea23ba33baaee049dfe38ce846b3ff2dc766` | `5a0fadddb0e009c307e6502871774f92e775208d9aa7910b30201bf191dc9026` | restored to frozen bytes |
| `preregistration/verification_contract.md` | `86ae5e44d28fbb067d26c244e77d5d5b2a490a3e0010694084179ea9e9f96069` | `f2b4427f74d451b99d6b89b7214c9c8e14ac6f76307cd695351913f5d63596ec` | restored to frozen bytes |

The machine-readable contract frozen at preregistration had SHA-256
`10febdfe91283540714e5cd17523912af24cf3e7df21f238825ac1eb320ba748`.
The live contract supersedes it only to encode this amendment and the exact
static-parser/cross-language identities; its new SHA-256 is recorded below
after the amended contract is frozen.

## Narrow parser interpretation

No upstream callable may be imported or executed. The local stack interpreter
may interpret only these exact forms:

- `numpy.dtype(code, False, True)` for exact code `"i8"` or `"f8"`, producing
  a local symbolic dtype value;
- dtype `BUILD` state `(3, "<", None, None, None, -1, -1, 0)`, with exact
  per-slot Python types (`int`, `str`, `None`, `int`) and with `bool` rejected
  where an integer is required;
- `numpy._core.numeric._frombuffer(buffer, dtype, shape, "C")`, producing a
  local decoded array value.

Every other `REDUCE`, `BUILD`, global, extension, persistent reference,
dynamic global, instance, unexpected type, or object-construction form fails
closed. Symbolic references are never resolved to executable objects.

## No hidden goalpost change

This amendment does not change the selected archive, member, seed, dimension,
algorithm, run, numeric endpoint, stop-semantic conflict, paper mapping, or
claim ceiling. `PASS_FULL`, source-native equivalence, literal-paper mapping,
historical-environment proof, and paper-budget-exhaustion claims remain
forbidden. It narrows the parser to the already selected payload and strengthens
the evidence gates; it cannot promote `TARGETED_ARTIFACT_REPLAY_ONLY`.

## Live contract identity

The amended machine-readable contract is schema `1.1.0`, SHA-256
`47ac507e09bb9ad705fa934af672763bd6e2fd02d8b18fe74fedb1498b39ff49`.
The loader rejects every other byte sequence before interpreting any field.
