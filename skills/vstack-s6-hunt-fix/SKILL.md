---
name: vstack-s6-hunt-fix
description: "Search within a trace-validated model scope, classify counterexamples and validate fixes in both the model and real code."
---

# S6 — Find and repair bugs

Read [Layer 0: shared operating rules](../../docs/layer-0.md), this stage and the assigned input bundle.

## Role and write scope

Workers write new search and repair artifacts; approved properties and prior patches stay read-only.

## 1. Input

The model reviewed in S5, restricted to the scope actually trace-validated.

## 2. Procedure

1. Write timestamped predictions for each bug family before running. Enable known repairs so shallow known failures do not hide deeper ones; record every switch.
2. Parameterize hardcoded constants first. At the old values, require matching verdicts and state counts; only then increase one dimension.
3. Classify each counterexample as model defect, known bug or new candidate. Attach code steps and a minimal trigger.
4. Reproduce progressively: source-level reasoning, real control-code replay with stubs, controlled timing on the real system. State the actual level as [Gate 3](../../docs/exposure-gate.md#gate-3-real-engine) names it (`model only`, `CPU replay of real code`, `real engine`), never rounded up, and any injected behavior. A named `human_verifier` requires `real engine`.
5. Compare repair candidates in the model: the original failure disappears, other safety and liveness properties hold, and removing the repair restores the failure. Then change code and check unpatched N/N versus patched 0/N under the declared trigger.

## 3. Exit checks

- Triage every candidate and record its reproduction scope.
- For every finding, record its [method class](../../docs/exposure-gate.md#method-classes), its [Gate 1](../../docs/exposure-gate.md#gate-1-formal-exposure) result (1a and 1b separately) and `found_by` (`checker` or `reading`). A finding that fails 1a or 1b is not reported as caught by formal checking. Gate 2 belongs to S5 and Gate 4 to the coordinator; S6 does not wait for them.
- Require repair controls and the full regression to match frozen expectations.
- A known-bug baseline matching expectations is not the same as a repaired implementation passing; require the fixed-state contract when validating a repair.

## 4. Rollback

Return an unrealizable counterexample to S3, or to S2 if the promise or assumption is wrong. A repair requiring a weaker promise returns to S2 for approval. Use [a rollback ticket](../../templates/rollback.md).

## Concrete Examples

For PD KV slot reuse, compare repairs that preserve in-flight accounting across reuse. Check both safe release and eventual release, then remove each repair component to test its role.
