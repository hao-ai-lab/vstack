---
name: vstack-s4-calibrate-tv
description: "Calibrate buggy/fixed/ablated behaviors and validate model conformance using real traces, witnesses and explicit mismatch triage."
---

# S4 — Calibrate and align traces

Read [Layer 0: shared operating rules](../../docs/layer-0.md), this stage and the assigned input bundle.

## Role and write scope

Model and trace workers own distinct outputs; the coordinator consolidates the checklist and independently reruns representatives.

## 1. Input

Models, configurations, source anchors and witnesses from S3.

## 2. Procedure

1. Timestamp predictions. Run four calibration checks: the historical bug violates the expected property by the expected mechanism; the fix completes within bounds; removing each repair component causes a violation; reachability witnesses are reached and their negations fail.
2. Repeat two-sided contract calibration at the minimum scale and one increment above it. A component outside the abstraction is unverified, not a pass.
3. Apply [trace-conformance checklist](../../docs/trace-validation.md) to real traces. Keep observation, instrumentation, completion and safety evidence separate.
4. Classify every NOT_CONSUMED at the first divergence; never edit a trace to make it count as accepted.
5. Review every run with [the seven questions](../../docs/run-review.md).

## 3. Exit checks

- Check expected verdicts and mechanisms for the bug, fix, repair ablations and paired witnesses. Generic mechanism and action-coverage automation is missing.
- Supply evidence and state covered and untested scope for every trace checklist item.
- Require agreement with the coordinator's clean reruns. Timeout, unknown, empty exploration and zero required coverage cannot pass.
- Complete S4 even when an S7 proof is planned.

## 4. Rollback

Return a wrong property to S2 and an overly narrow or broad model to S3. Repair instrumentation errors and record new traces within S4. Send real code failures to S6. Carry the trace hash, event index and source anchor. Use [a rollback ticket](../../templates/rollback.md).

## Concrete Examples

A PD slot model can pass its configured safety checks while rejecting a real slot-reuse trace. Diagnose the first divergence before using that model to justify a repair.
