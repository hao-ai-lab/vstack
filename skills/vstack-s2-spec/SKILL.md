---
name: vstack-s2-spec
description: "Derive observable contracts, calibrate both legal and illegal behavior, then freeze owner-approved specifications and configurations."
---

# S2 — Freeze specifications and contracts

Read [Layer 0: shared operating rules](../../docs/layer-0.md), this stage and the assigned input bundle.

## Role and write scope

The coordinator writes top-level promises and pins; the property owner approves them. Workers supply anchored evidence and staged proposals.

## 1. Input

The approved S1 design and obligation matrix.

## 2. Procedure

1. Write a short, reviewable statement of observable consequences and explicit non-goals. Use [contract discovery](../../docs/contracts.md) and [the card template](../../templates/contract-card.md).
2. Require top-level decomposition plus historical bugs or consumer requirements; complete one-step induction for ledger and protocol families. Scan all seven consumer-precondition categories.
3. Calibrate negative examples, legal edge behavior, witnesses and minimum scale before freezing. S4 repeats calibration on the complete model.
4. Expose environment assumptions and ambiguous semantics as sourced switches. State which interpretation each claim requires.
5. Have the coordinator pin the approved text, ideal model and check configurations. Before deductive proof, also freeze the complete inductive invariant and root statement, including explicit parameter ranges and configuration premises. Check content hashes before every counted run.

## 3. Exit checks

- Check approval, provenance, consumer scans and calibration records for completeness. This is partly manual.
- Require `scripts/check_spec_pins.sh ROOT PINS` to succeed; it compares pinned bytes mechanically.
- Run the approved bad-implementation suite against the frozen ideal: bad cases must fail and controls must pass. These project-specific runs do not grant approval.

## 4. Rollback

Report an overly strong property or missing assumption with [a rollback ticket](../../templates/rollback.md). Stage the change, compare full regressions, obtain a new property-owner decision, then let the coordinator independently rerun and re-pin. An invariant change requires new Init and affected preservation checks in the same tree, then fresh acceptance. Old proof results do not carry over.

## Concrete Examples

For a PD KV slot, a posted write must not simply disappear from the ideal model. Freeze that promise and the configurations that check it; revise them only through the property owner and coordinator.
