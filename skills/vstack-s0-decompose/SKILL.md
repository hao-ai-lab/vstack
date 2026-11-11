---
name: vstack-s0-decompose
description: "Map a pinned system into control, data and boundary views and build evidence-backed historical anchors before verification."
---

# S0 — Reconstruct and separate the system

Read [Layer 0: shared operating rules](../../docs/layer-0.md), this stage and the assigned input bundle.

## Role and write scope

Assigned investigators own separate maps and candidate files; a verifier and coordinator check evidence. Target source is read-only.

## 1. Input

A fixed source revision and existing anchors for deduplication.

## 2. Procedure

1. Build a control map of mutable state, owners and **all** writers. Search all assignments before saying a field has one writer.
2. Map data and computation consumers and their unchecked preconditions. At each boundary, map the producer, consumer, execution context, overwrite time and synchronization. Classify every in-scope file.
3. Record facts with `path:line@commit` and short source excerpts. Keep unsupported inferences explicitly unverified.
4. Search the target and related systems by component. Record every examined candidate, rejection reason and search coverage. Confirm buggy triggers and fixed behavior on the stated revisions; a closed issue is not evidence that a fix merged.
5. Test critical physical and synchronization assumptions on the real system before treating them as axioms, using authorized resources.

## 3. Exit checks

- Require zero evidence schema errors and a positive checked-item count. The source KB checker is repository-specific and is not bundled.
- Have the verifier and coordinator review original source and bind review marks to its content. This review is manual.
- Classify every file, label unsupported claims and deduplicate upstream identifiers. These checks have no generic automation.
- Keep disproved anchors. Rename an unsupported historical `Bug*` switch to `Mut*`; do not count it as historical calibration.

## 4. Rollback

An invalid physical assumption reopens the boundary map. A downstream report of a missing state writer returns here with the pinned source location. Use [a rollback ticket](../../templates/rollback.md).

## Concrete Examples

For a PD KV slot, map every writer of ownership and in-flight state, then record the producer-to-consumer handoff. An unsupported historical-bug claim stays a mutation hypothesis until pinned code supports it.
