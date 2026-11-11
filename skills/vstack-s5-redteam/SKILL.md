---
name: vstack-s5-redteam
description: "Audit calibrated verification through independent attacks on fidelity, property/gate strength and scope extrapolation."
---

# S5 — Attack model fidelity and gate strength

Read [Layer 0: shared operating rules](../../docs/layer-0.md), this stage and the assigned input bundle.

## Role and write scope

Red team reads reviewed artifacts and mutates only its own copies. It reports findings; the coordinator verifies them and assigns fixes.

## 1. Input

The complete S4 bundle and its scope statement, with hashes.

## 2. Procedure

1. When delegation is available and authorized, assign independent attacks: test fidelity with missing or extra behaviors; test properties and gates with bad models, weak specs and forged output; test scale with one larger configuration.
2. For each finding record exact command, actual output, intended output, source anchors and confidence. Mark findings as execution-supported when a run supports them, or as reproduced on real code. Items without run evidence remain leads.
3. The coordinator reruns findings and merges common causes. Keep every independently confirmed failure, not just one reviewer's list.
4. Turn a successful bypass into a mechanical check where feasible and record its ablation. Rerun the corresponding attack after gate changes.

## 3. Exit checks

- Resolve each execution-supported or reproduced finding, or file a rollback ticket. The coordinator reviews these manually.
- Update the attack-to-enforcer table with evidence and remaining gaps.
- Run the corresponding attack regressions for every gate change. The source has an ASSUMES selftest; a complete generic attack suite is not bundled.
- S5 is mandatory; a model author's success report is insufficient.

## 4. Rollback

Return fidelity defects to S3 and a weak ideal to S2 with property-owner approval. Assign weak verdicts or gates to the coordinator for repair. Never modify the reviewed originals from the red-team role. Use [a rollback ticket](../../templates/rollback.md).

## Concrete Examples

For PD KV slot ownership, attack a copied ideal action, an unchecked mapping assumption and an implementation that silently discards a posted write. These exercise mirror, ASSUMES and specification-mutation checks.
