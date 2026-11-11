# Contract: <ID>

## Observable promise

- When <concurrent, exceptional or boundary event> occurs, prevent <caller-visible harm>.
- Promise and parent requirement: <WHAT, not HOW>.

## Sources

- Top-level decomposition, mandatory: <approved top-level promise and derivation>.
- Historical bugs, required unless consumer requirements are supplied: <historical buggy/fixed source anchors and established repair>.
- Consumer requirements, required unless historical bugs are supplied: <producer guarantee => consumer precondition; path:line@commit>.
- Consumer scan: <indices, ranges, overwrites, execution context, lifetime, aliases, initialization>.
- One-step induction, required for ledger/protocol contracts before freezing: <single-step counterexample; reachable or unreachable; named strengthening>.

## Formalization

- Layer: <state ledger / protocol / computation / alignment>.
- Predicate: <model invariant or Z3 constraint>.
- Chain: <upstream Ensures => Requires; Ensures => downstream Requires>.
- Assumptions, scope and unmodeled behavior: <...>.

## Calibration

- Negative execution and expected violation: <artifact, mechanism, command>.
- Positive reachability witness and legal edge behavior: <artifact, command>.
- Normal and fault-injected real traces: <evidence or explicit pending status>.
- Minimum exposing bound and why smaller misses it: <...>.
- Minimum-bound and next-bound results: <...>.
- Initiation / Consecution / Implication: <result and finite domains, if applicable>.

## Freeze record

- Version / UTC / author / reviewer / property-owner decision: <...>.
- Coordinator-owned pin manifest and hash: <...>.
