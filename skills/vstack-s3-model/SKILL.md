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

1. Fill [the case playbook](../../templates/case-playbook.md). Bind every action, descriptor and ledger method to source lines and revision.
2. Extract constants from pinned source when possible; do not let a correct verdict hide a transcribed constant error.
3. Preserve atomicity: two separately visible shared writes are two model steps. Name actions; make `Next` their disjunction; keep deadlock checking and an explicit legitimate terminal action.
4. Use switches for historical bugs and repair components in one model. `Bug*` needs a real historic revision; use `Mut*` otherwise. Check complete switch combinations against the source revision.
5. Give critical paths reachability witnesses. Declare unchecked mapping dependencies in one `ASSUMES` header and ensure every using configuration checks them; this comment is not permission to add proof axioms.
6. Finish invariant discovery and have the coordinator pin its full definition before deductive proof. Prove this calibrated model; prove bridges from proof-layer helpers to its pinned definitions. Do not replace the model.

## 3. Exit checks

- Check every source anchor. The source workflow has case-specific checkers; no generic anchor checker is bundled.
- Review action boundaries, named `Next`, termination and deadlock settings manually.
- `scripts/assumptions_check.sh MANIFEST` checks the supported header/config syntax. `scripts/op_mirror.sh` checks only its documented record-update dialect; neither is a semantic TLA+ parser.
- Confirm that frozen inputs remain unchanged.

## 4. Rollback

A missing writer returns to S0 with its source location. A contract defect returns to S2. Do not patch upstream artifacts to fit the new model. Use [a rollback ticket](../../templates/rollback.md).

## Concrete Examples

In a PD KV slot lifecycle, dequeue accounting and the following status check may be separately visible. Preserve that interleaving instead of merging both into one atomic model step.
