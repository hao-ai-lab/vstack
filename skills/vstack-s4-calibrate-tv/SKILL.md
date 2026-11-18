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

1. Timestamp predictions. Run four calibration checks: the historical bug violates the expected property by the expected mechanism; the fix completes within bounds; removing each repair component causes a violation; reachability witnesses are reached and their negations fail. Aggregated over the frozen denominator `I_U`, these results give the numerators `Cov_expr` and `Cov_emergent` of the [adequacy readout](../../docs/model-adequacy.md#numerators).
2. Repeat two-sided contract calibration at the minimum scale and one increment above it. A component outside the abstraction is unverified, not a pass.
3. Apply [trace-conformance checklist](../../docs/trace-validation.md) to real traces. Keep observation, instrumentation, completion and safety evidence separate. Report [readout 1](../../docs/model-adequacy.md#readout-1-trace-and-baseline-agreement): `TAR` with its negative-mutant rejection rate (or the agreement rule's stateful-test readout or labeled model-only exception), and clean-baseline counterexamples as `Confirmed Bug`, `Model Defect` and `Unjudged (pending repro)` counts.
4. Classify every NOT_CONSUMED at the first divergence; never edit a trace to make it count as accepted.
5. Complete the [agreement record](../../docs/model-adequacy.md#readout-1-trace-and-baseline-agreement) for the pinned baseline and every calibration mutant, clause by clause. Apply each mutant to an unmutated row that passes at the same scale, with the known repairs switched on when the pinned baseline already violates, and confirm that its counterexample takes the mutated action. Resolve differing verdicts before S6 counts anything from this model: model pass/code violation returns to S3 with the code location; a model counterexample not reproduced by code needs a directed real-code check constructing its trace preconditions before it counts; fix a harness defect and rerun the row.
6. Review every run with [the seven questions](../../docs/run-review.md). Follow [run order and budget](../../docs/run-review.md#run-order-and-budget).

## 3. Exit checks

- Check expected verdicts and mechanisms for the bug, fix, repair ablations and paired witnesses. Mechanism review remains partly manual; [the TLC log gate](../../docs/gates.md#tlc-run-verdict) checks the supported action-coverage formats mechanically.
- Supply evidence and state covered and untested scope for every trace checklist item.
- Mechanical: [scripts/check_agreement.py](../../scripts/check_agreement.py) checks the agreement TSV, including same-clause agreement and each mutant's passing unmutated row at the same scale. Reviewing mutant coverage, `mutation_reached`, evidence and mismatch resolution is partly manual; a nonempty resolution alone does not establish agreement.
- Require agreement with the coordinator's clean reruns. Timeout, unknown, empty exploration and zero required coverage cannot pass.
- Complete S4 even when an S7 proof is planned.

## 4. Rollback

Return a wrong property to S2 and an overly narrow or broad model to S3. Repair instrumentation errors and record new traces within S4. Send real code failures to S6. Carry the trace hash, event index and source anchor. Use [a rollback ticket](../../templates/rollback.md).

## Concrete Examples

A PD slot model can pass its configured safety checks while rejecting a real slot-reuse trace. Diagnose the first divergence before using that model to justify a repair.
