# Find contracts before freezing them

One card per contract family. Describe observable consequences, not the implementation that happens to exist.

| Source | Required work |
|---|---|
| Top-level decomposition | Trace the contract to an approved system promise. Always required. |
| Historical bugs | Negate an evidenced bad state; record what the fix actually establishes at pinned buggy and fixed revisions. |
| Consumer requirements | At every handoff, work backward from unchecked consumer preconditions to the producer's Requires and Ensures. |
| One-step induction | On a small ledger or protocol model, classify each counterexample: a reachable predecessor indicates an operation defect; an unreachable one needs a strengthening fact. |

Top-level decomposition is mandatory, together with historical bugs or consumer requirements. Ledger and protocol contracts must complete one-step induction before freezing, including all three induction checks. Computation descriptors instead need differential checks against the actual functions.

## Consumer scan: seven categories

At every cross-component, cross-thread, device or stream boundary check:

- indices and offsets: who establishes bounds;
- value ranges: legal identifiers, positions and lengths;
- overwrite points: all writers and their ordering;
- execution context: producing and consuming streams or threads, event placement;
- lifetime: how long an asynchronously consumed allocation remains alive;
- aliases and views: whether retained data is a copy or a mutable view;
- initial values: whether anything can read a location before valid initialization.

## Two-sided calibration

For each contract, supply a violating execution, accepted reachability witnesses and legal edge behaviors, and the minimum scale exposing its failure. Explain why smaller bounds miss the failure. Run both the minimum and one increment. Add normal and fault-injected real traces when available.

Calibrate contracts in S2 before freezing them. Repeat calibration on the full model and add runtime alignment in S4; do not postpone all calibration to S4.

Before freezing, require cards for all in-scope models, consumer scans for every boundary, fully classified ledger and protocol induction counterexamples, recorded calibration and minimum bounds, and property-owner approval. The coordinator pins specs **and configurations**. Before deductive proof, pin the full inductive invariant and root statement too. Put parameter ranges and the proved configuration in explicit root `ASSUME … PROVE` premises and publish them verbatim; do not add module-level axioms. The card checklist is partly manual; the hash comparison is mechanical.

Discover strengthening before proof begins. A later invariant change requires new pins, Init and affected preservation checks in the same module tree, and renewed [proof acceptance](gates.md#deductive-proof-acceptance). Auxiliary definitions stay in the proof layer with proved bridges to the pinned model.
