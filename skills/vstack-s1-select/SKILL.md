---
name: vstack-s1-select
description: "Choose verification tools and assurance tiers per property using state, scale, ownership and consequences."
---

# S1 — Split obligations and select methods

Read [Layer 0: shared operating rules](../../docs/layer-0.md), this stage and the assigned input bundle.

## Role and write scope

The coordinator owns the design and obligation matrix; the property owner approves the scope.

## 1. Input

Control, data and boundary maps, the settled resource matrix and verified anchors from S0, with hashes.

## 2. Procedure

1. Read each [unit](../../docs/method-selection.md#units-planes-and-edges) from a resource-matrix row group. Record it in the [unit table](../../templates/unit-table.tsv): resource, writing or holding subsystems, their distinct count `k`, plane, property clauses, pillars, formal classes and methods. Start from the resources, never from combinations of subsystems: a resource with `n` writers or holders has `n(n-1)(n-2)/6` triples, and a census that reaches three-subsystem resources does not call for a model of every triple. Choose each resource's units by steps 3 and 4.
2. Use the [method-selection table](../../docs/method-selection.md#property-classes-and-the-seven-pillars) by plane and formal class. Split by property, not module or processor type: route control questions to a state machine and model checker; route data questions to SMT over dispatch descriptors, an exhaustive sweep or a differential test on real functions. Give every boundary a [contract card](../../templates/contract-card.md).
3. Plan `k <= 3` by default. For resources with more writers, split by deployment tier: default-on writers form the unit; declare the rest as environment or separate units adding one feature each, so a resource yields units per feature added, not per pair or triple of writers. A unit with `k >= 4` is allowed under the [search budget](../../docs/run-review.md#run-order-and-budget). If exhaustive search at the smallest scale reaching the concurrency witness does not finish within that budget, record `over_budget` and do not report an exhaustive result.
4. Order units by the [two danger axes](../../docs/danger-grading.md#use-when-choosing-units), recording `entry_kind` and deployment `tier`; ordinary client traffic under the default configuration comes first.
5. Record each obligation's difficulty, finite or unbounded scale, code ownership, change rate and failure severity.
6. Map ledger, protocol, computation, alignment and fallback guarantees. Identify which row supports each promise and which is weakest.
7. Record each property's assurance tier, rationale, available tools and skipped stages. Require S4 and S5. Skip S6 only for new code destined for deductive proof.

## 3. Exit checks

- Manually check that every hazardous transition and consumer precondition has an obligation.
- Documented-only: review unit rows against the settled resource matrix, including `k`, plane, property/method routing, boundary contracts, deployment splits and priority order. Record the search budget and `within` / `over_budget` / `not_run` result in the [case playbook](../../templates/case-playbook.md#frame-before-running); keep the unit table consistent with run evidence. `scripts/check_unit_table.py` checks status, evidence, one unit first and gaps against the plan; no budget checker is bundled.
- Account for every gap in the guarantee matrix; no generic checker is bundled.
- Record scope and design approval. Limit each guarantee to its weakest supporting evidence.

## 4. Rollback

Missing maps return to S0. If no small clean proof core exists, propose the smallest interface separation before proving tangled orchestration code. Use [a rollback ticket](../../templates/rollback.md).

## Concrete Examples

PD KV slot reuse is a state-machine obligation: finite exploration finds interleavings; an arbitrary-scale claim needs a corresponding design-model theorem plus explicit model/code alignment.
