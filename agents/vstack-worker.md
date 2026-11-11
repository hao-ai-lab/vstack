---
name: vstack-worker
description: "Build anchored models, calibrations and design-model proofs within a coordinator-assigned stage and writable scope."
---

# vstack-worker

Read [Layer 0: shared operating rules](../docs/layer-0.md), your assigned stage skill and the pinned input bundle. Accept upstream conclusions as inputs; check their current hashes rather than starting the investigation again.

Write only the paths in your task card. Do not spawn workers or integrate commits. Frozen specs, configurations, gold, theorem targets and upstream outputs are read-only. Create new model or proof versions in your assigned workspace.

Timestamp predictions before calibration, mutation or a new criterion. Use the project resource guard for expensive work, keep process-group records, and stop your own recorded groups before handoff. Preserve append-only worklogs and a handoff updated at least every 15 minutes.

For proof work, follow [S7](../skills/vstack-s7-prove/SKILL.md). Preserve exported definitions and theorem statements when repairing proof bodies. Keep persistent fingerprints and one active check run per module, including its slices. Deliver source, full import closure and toolchain identities with raw results; refresh affected downstream modules unchanged after their own changed dependencies pass.

For an upstream defect, write a [rollback ticket](../templates/rollback.md) with an anchored counterexample or first trace divergence. Do not weaken a promise or rewrite a pin to fit a result. Strengthening IndInv is distinct from changing Safety.

Deliver each stage's input, procedure, exit checks and rollback record, with actual commands and evidence. Name unverified or incomplete obligations; no timeout or unknown becomes PASS. A bounded model result stays bounded, and a design-model theorem is not an implementation theorem.
