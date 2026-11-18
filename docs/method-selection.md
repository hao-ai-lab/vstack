# Choose by the property

Use two independent axes: the mathematical difficulty determines the representation; scale and the assurance objective determine the verification tier. Execution hardware is not the decision boundary.

| Difficulty | Approach |
|---|---|
| Small owned state with severe consequences if corrupted | Isolate a small state-machine model; check its contracts and keep environment assumptions and the implementation-alignment gap explicit. |
| Asynchronous interleavings, messages, timeouts, faults, hardware interpretations | TLA+ state machine, TLC exploration, trace alignment and reproduction; escalate the same model when needed. |
| Stateless dispatch over input dimensions or modes | Z3 constraints over anchored descriptors; compare descriptors to real functions. |
| Algebraic correctness and floating-point reduction order | Separate formula correctness, reduction structure and dispatch; check composition. Handwritten descriptors remain an abstraction boundary. |

Record each obligation's difficulty, bounds, code ownership, change rate and failure severity. Map the obligation to ledger, protocol, computation, alignment and fallback guarantees. State the weakest link in every public claim.

## Units, planes and edges

Label subsystem responsibilities `control` when they decide who may touch what and when (ownership, order and lifecycle), `data` when they compute or move data given legal handles and parameters, or `both` with the slice of each stated. Many subsystems are `both`: these labels slice responsibilities; they are not a verified partition of the system.

A `state` edge has both sides read or write the same mutable resource, or lets one side's guard read the other's state; check the sides together. A `parameter` edge carries only a value, and the receiver's property holds for every value in a stated range, so it permits a cut. An edge that is both is a state edge. Record the criterion for each classification. A parameter cut depends on that value range actually holding; liveness also needs conditions on progress and fairness, and two-run properties need conditions relating the values and behavior across both runs.

A unit is one shared mutable resource together with the subsystems that write or hold it, read from a row group in the [resource matrix](../templates/resource-matrix.tsv). The resource matrix is the main table of the census: units are derived from its resources, never enumerated as combinations of subsystems. Count distinct participating subsystems as `k` and record the unit in the [unit table](../templates/unit-table.tsv). [S0](../skills/vstack-s0-decompose/SKILL.md#2-procedure) settles the census and edges; [S1](../skills/vstack-s1-select/SKILL.md#2-procedure) sizes and orders units and routes each property by plane and formal class using the table below.

## Property classes and the seven pillars

The bug ledger names each violated property by one of seven pillars. Route each by its formal class.

**Single-trace properties.** Every trace property is the intersection of a safety property and a liveness property (Alpern and Schneider, *Information Processing Letters* 21(4):181–185, 1985). A safety violation shows on a finite prefix; no finite prefix violates a liveness property. Check the two parts separately.

**Relational properties.** A property that compares two executions is a hyperproperty and in general not a trace property (Clarkson and Schneider, *Journal of Computer Security*, 2010).

| Pillar | Formal class | Form | Preferred route |
|---|---|---|---|
| `Isolation`, `Integrity`, `Conservation`, `Agreement` | State or action safety | `□I`, `□[A]_v` | TLC; Apalache for larger symbolic domains; TLAPS for unbounded claims |
| `Finality` | Bounded-response safety | `□(Pending ⇒ steps ≤ N)` over a step or lease counter | TLC invariant over the counter; no fairness assumption |
| `Progress` | Liveness | `◇P`, `P ~> Q` | TLC liveness with explicit fairness on engine actions only (S3 [open environment](../skills/vstack-s3-model/SKILL.md#open-environment)) |
| `Invariance` | 2-safety hyperproperty or relational equivalence (`≡`) | Same output over two executions or two code paths | Exhaustive property sweep or differential test on the real functions; Z3 over dispatch descriptors; TLA+ self-composition only when concurrent interleavings matter |

As the ledger states it ("in bounded steps"), `Finality` is bounded response: the bad thing, the bound passing without termination, is visible on a finite prefix, so it is safety and needs no fairness. An unbounded "eventually reclaims" property is liveness; route it like `Progress`.

`Invariance` covers two shapes. Batch invariance (one request alone and with batch partners) is a 2-safety hyperproperty: a violation needs two executions (Terauchi and Aiken, SAS 2005), and self-composition reduces it to safety of the composed system (Barthe, D'Argenio and Rezk, CSFW 2004). Equivalence of two code paths or configurations (streaming vs. non-streaming, CUDA graph on vs. off) is a relational property between two programs, checked on a product program (Barthe, Crespo and Kunz, FM 2011); it becomes a hyperproperty only when the configuration is an input of one system. Either way, prefer real-code sweeps and descriptors first.

## State-machine tiers

1. **Explicit state checking:** TLC explores configured finite domains and gives counterexamples. Appropriate for evolving code and small hardware-fixed participant counts; include deadlock, liveness and alternative hardware readings where relevant.
2. **Symbolic checking:** Apalache or Z3 tests larger symbolic domains or falsifies inductive invariants with a single transition. A bounded symbolic verdict is not an unbounded proof.
3. **Deductive proof:** TLAPS for the existing TLA+ design model. A claim beyond finite deployment bounds needs a corresponding unbounded theorem. Do not rewrite a calibrated TLA+ model in another language merely to upgrade tools.

Confirm tool availability before committing to a tier. Do not copy historical installation status from a case into a new project. S4 and S5 still apply before a proof upgrade.

## Safety and IndInv are different artifacts

The property owner approves **Safety**, the observable promise; the coordinator freezes it. Discover **IndInv** with named strengthening facts before deductive proof, then have the coordinator hash-pin the complete invariant and specification. A forward run from Init does not establish inductiveness. Later strengthening requires new pins, Init and affected preservation checks in the same proof tree, and renewed full acceptance.

In a scratch wrapper, check:

```text
Initiation:  Init => IndInv
Consecution: IndInv /\ Next => IndInv'
Implication: IndInv => Safety
```

Configure the tool version and finite domains for your project, then use these Apalache commands from the source workflow:

```sh
apalache-mc check --config=APTarget.cfg --init=Init --inv=IndInv --length=0 APTarget.tla
apalache-mc check --config=APTarget.cfg --init=IndInv --inv=IndInv --length=1 APTarget.tla
apalache-mc check --config=APTarget.cfg --init=IndInv --inv=Safety --length=0 APTarget.tla
```

For every consecution counterexample, decide whether the predecessor is reachable. If reachable, investigate a bug; if unreachable, record the named conjunct that excludes it, then rerun all three checks. Add type annotations only in scratch copies when the wrapper needs them. Do not import those wrappers into the delivered proof.

In one shared module tree, prove preservation for every invariant conjunct under every action. Follow [S7 — Upgrade to a proof](../skills/vstack-s7-prove/SKILL.md) for projections, action effects, frame facts and local contexts. Proof-layer abstractions need proved bridges to the pinned definitions; do not replace the calibrated model. Never cite a TLC or Apalache success as justification for a TLAPS proof step.

Require all [proof acceptance gates](gates.md#deductive-proof-acceptance): pinned definitions, explicit premises, root-reachable coverage, no omissions and one complete strict result per module. A verified slice certificate can supply that result. Bind results to source, import closure and toolchain; treat runtime, memory and repetitions as operating data. Keep calibration and mutation evidence distinct from mathematical proof acceptance. This package supplies guidance and spec pinning, **not a generic proof-integrity checker**.
