---
name: vstack-s3-model
description: "Construct state transitions or computation descriptors from pinned code without hiding interleavings or unchecked assumptions."
---

# S3 — Build an anchored model

Read [Layer 0: shared operating rules](../../docs/layer-0.md), this stage and the assigned input bundle.

## Role and write scope

The worker owns a new model version and append-only notes, never upstream pins or gold expectations.

## 1. Input

Frozen contracts from S2 and maps from S0, with hashes.

## 2. Procedure

1. Fill [the case playbook](../../templates/case-playbook.md). Bind every action, descriptor and ledger method to source lines and revision. For the full adequacy readout, write each modeled guard and state update as a named operator and list it in the [anchor map](../../docs/model-adequacy.md#anchor-map).
2. Extract constants from pinned source when possible; do not let a correct verdict hide a transcribed constant error.
3. Preserve atomicity: two separately visible shared writes are two model steps. Name actions; make `Next` their disjunction; keep deadlock checking and an explicit legitimate terminal action.
4. Use switches for historical bugs and repair components in one model. `Bug*` needs a real historic revision; use `Mut*` otherwise. Check complete switch combinations against the source revision.
5. Give critical paths reachability witnesses (`W_*`, see [anti-vacuity checks](../../docs/exposure-gate.md#anti-vacuity-checks)). Declare unchecked mapping dependencies in one `ASSUMES` header and ensure every using configuration checks them; this comment is not permission to add proof axioms.
6. Finish invariant discovery and have the coordinator pin its full definition before deductive proof. Prove this calibrated model; prove bridges from proof-layer helpers to its pinned definitions. Do not replace the model.
7. Model the environment by the rules below.

### Open environment

Model each external stimulus `E` (cancel, disconnect, session close, admin pause, cache flush, weight update, timeout expiry) as `Env_*` actions and the engine's responses as `Engine_*` actions; one action may carry both when the code dispatches them together.

| Rule | Requirement |
|---|---|
| Input enabled | For each `E`, define `InputEnabled_<E> == EnvPremise_<E> => ENABLED Handle_<E>` and check it as an invariant. `EnvPremise_<E>` holds while the environment's own finite budget lasts and the object exists from the client's side (for example `nAbort < MaxAbort` and the request is still open for its client). `Handle_<E>` is any action that takes `E`: handles it now, records it as pending, or rejects it by a code branch. TLC evaluates `ENABLED` in invariants; with a checker that cannot, cover every branch explicitly or give each branch a reachability witness. |
| Guard rule | Every enabling guard of every action, `Engine_*` included, is either the condition the code evaluates at its `file:line@commit` anchor or a registered finite bound or `\* ASSUMES:` premise. Anything else is illegal pruning; keep real failure paths, such as a full allocator raising or asserting. |
| Caller contracts | Restrict a call order only when the engine's documentation forbids it and the code rejects it. Name the restriction `EnvContract_<name>`, declare it in the `\* ASSUMES:` header with the documentation quoted verbatim and its source, and run a robustness control without it. Report a violation in that control as a robustness finding outside the documented contract. |
| Fairness | Put `WF`/`SF` on `Engine_*` actions only. Environment actions get no fairness except in a named control. Every liveness check registers `EnvEventuallyQuiet`: a finite total of arrivals, or a named constant after which the environment stops. |
| Restrictions | Named environment timing restrictions follow the [asymmetric rule](../../docs/run-review.md#environment-restrictions-and-freedoms): hunt and control configurations only, never a configuration reported as passing. |

## 3. Exit checks

- Check every source anchor. The source workflow has case-specific checkers; no generic anchor checker is bundled.
- Review action boundaries, named `Next`, termination and deadlock settings manually.
- Check every `InputEnabled_<E>` invariant and every `W_*` witness in each delivered configuration. Review each guard against its anchor or registered bound; this is partly manual.
- `scripts/assumptions_check.sh MANIFEST` checks the supported header/config syntax. `scripts/op_mirror.sh` checks only its documented record-update dialect; neither is a semantic TLA+ parser.
- Confirm that frozen inputs remain unchanged.

## 4. Rollback

A missing writer returns to S0 with its source location. A contract defect returns to S2. Do not patch upstream artifacts to fit the new model. Use [a rollback ticket](../../templates/rollback.md).

## Concrete Examples

In a PD KV slot lifecycle, dequeue accounting and the following status check may be separately visible. Preserve that interleaving instead of merging both into one atomic model step.
