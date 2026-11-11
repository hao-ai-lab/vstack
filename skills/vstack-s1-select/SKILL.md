---
name: vstack-s1-select
description: "Choose verification tools and assurance tiers per property using state, scale, ownership and consequences."
---

# S1 — Split obligations and select methods

Read [Layer 0: shared operating rules](../../docs/layer-0.md), this stage and the assigned input bundle.

## Role and write scope

The coordinator owns the design and obligation matrix; the property owner approves the scope.

## 1. Input

Control, data and boundary maps and verified anchors from S0, with hashes.

## 2. Procedure

1. Use [method selection](../../docs/method-selection.md). Split by property, not module or processor type.
2. Record each obligation's difficulty, finite or unbounded scale, code ownership, change rate and failure severity.
3. Map ledger, protocol, computation, alignment and fallback guarantees. Identify which row supports each promise and which is weakest.
4. Record each property's tier, rationale, available tools and skipped stages. Require S4 and S5. Skip S6 only for new code destined for deductive proof.

## 3. Exit checks

- Manually check that every hazardous transition and consumer precondition has an obligation.
- Account for every gap in the guarantee matrix; no generic checker is bundled.
- Record scope and design approval. Limit each guarantee to its weakest supporting evidence.

## 4. Rollback

Missing maps return to S0. If no small clean proof core exists, propose the smallest interface separation before proving tangled orchestration code. Use [a rollback ticket](../../templates/rollback.md).

## Concrete Examples

PD KV slot reuse is a state-machine obligation: finite exploration finds interleavings; an arbitrary-scale claim needs a corresponding design-model theorem plus explicit model/code alignment.
