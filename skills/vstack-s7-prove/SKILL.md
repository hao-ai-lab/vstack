---
name: vstack-s7-prove
description: "Prove pinned design-model properties in one shared TLAPS module tree after invariant discovery, calibration and trace alignment."
---

# S7 — Upgrade to a proof

Read [Layer 0: shared operating rules](../../docs/layer-0.md), this stage and the assigned input bundle.

## Role and write scope

Proof workers own assigned proof modules and auxiliary lemmas in one shared module tree. The coordinator owns theorem statements, invariant pins and accepted tool and settings manifests.

## 1. Input

The calibrated model selected in S1, after S4 and S5, with no unclassified mismatch between model and code. Complete [invariant discovery](../../docs/method-selection.md) first; pin the specification, full inductive invariant, parameter ranges and proved configuration before deductive proof starts.

## 2. Procedure

1. Import the pinned model directly. The root concludes exactly its `Spec ⇒ □Safety`, with parameter ranges and configuration in explicit `ASSUME … PROVE` premises. Add no module-level `ASSUME` or `AXIOM`. Keep auxiliary definitions in the proof layer and machine-check their bridges to pinned definitions. Never rewrite the model to ease proof.
2. Use one module tree and shared definitions from the start. Assign preservation cells for every invariant conjunct under every action, including all strengthening. Do not prove independent model copies and merge or rename them later.
3. Prove projection lemmas `IndInv ⇒ Conjunct`; unfold the full invariant only at this interface. Each preservation cell receives just the old-state conjuncts it needs, including necessary type and domain facts.
4. Expand each action once to prove effect equations and frame facts for unchanged fields. Reuse those facts in subsequent cells. Prove shared effects as family lemmas, retain every action-to-family bridge, and hide large local definitions after proving their interfaces.
5. Split remaining goals by quantified object, updated or unchanged object, or old or new set member. Close Init, every preservation cell, stuttering and `IndInv ⇒ Safety`. Compose only proved results at the root; never use bounded model-checking success as a proof premise.
6. Control facts and definitions separately: `BY ONLY` retains already usable definitions. Pair it with `HIDE DEF` and keep `USE DEF` inside the smallest subproof scope. A renamed large expression still expands unless hidden.
7. Follow the [proof-run protocol](../../docs/run-review.md#proof-runs): keep persistent fingerprints, diagnose timeouts in the full module context with a capped step budget, and parallelize large modules at top-level theorem boundaries. Use `tlapm --toolbox <start_line> <end_line> --threads 1` for each slice; start with one or two backend threads per slice. Accept slices only with the complete certificate defined in the proof gates. For lasting reductions in frontend work, split large modules and narrow `DEF` expansion.
8. Keep at most one active check run per module, across all snapshots and execution hosts. That run may comprise several parallel slice processes; do not run a second whole-module or sliced copy alongside it. Overlap rounds for different modules. Refresh each downstream module unchanged once its own changed dependencies have final passing sources; do not wait for unrelated modules. Preserve exported definitions and theorem statements when repairing proof bodies. Route interface or invariant changes through review and new acceptance; invariant changes also require new pins.

For certified parallel checks, follow the [slice-certificate procedure](../../docs/gates.md#slice-certificates), including native inventory generation, fresh per-slice caches and independent reconciliation of obligation-location multisets.

For proof structure and tool mechanics, consult the [TLAPS guide](https://lamport.azurewebsites.net/tla/tla2-guide.pdf), [practical hints](https://proofs.tlapl.us/doc/web/content/Documentation/Tutorial/Practical_hints.html), [tactics](https://proofs.tlapl.us/doc/web/content/Documentation/Tutorial/Tactics.html), [MongoRaftReconfig proof organization](https://arxiv.org/html/2109.11987v2) and [TLAPS-Bench theorem-range slicing](https://arxiv.org/abs/2611.02849). These references provide no measured performance guarantee for this workflow.

## 3. Exit checks

- Pass all [proof acceptance gates](../../docs/gates.md#deductive-proof-acceptance) on the assembled tree, including bridges and strengthening. Retain one complete strict result per module, from a whole-module run or an independently checked slice certificate. Bind each result to its source, full import closure and toolchain; cached leaves or a green root alone are insufficient.
- Report the root statement and its premises verbatim. Finite-domain induction retains its bounds; an arbitrary-scale claim requires the corresponding quantification.
- The proved object is the design model. Describe implementation evidence as validation against that model, with its alignment limits.
- Treat final unproved, timeout, unknown, omitted, interrupted or inconclusive work as incomplete. Record runtime, memory and repeat runs without making them proof gates. No generic proof-integrity/closure checker is bundled.

## 4. Rollback

Send a reachable induction counterexample to S6. Return a missing premise or invariant change to S2 for review and new pins; do not inherit the old acceptance result. If strengthening fails, revisit S3. Use [a rollback ticket](../../templates/rollback.md).

## Concrete Examples

For PD KV slot release, prove the design-model promise only after checking real interleavings and trace conformance. A theorem about an atomic model step does not establish atomicity in the implementation.
