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

1. When delegation is available and authorized, assign independent attacks: test fidelity with missing or extra behaviors; test properties and gates with bad models, weak specs and forged output; test scale with one larger configuration. Attack the [open-environment rules](../vstack-s3-model/SKILL.md#open-environment): a stimulus whose `InputEnabled_<E>` is missing or vacuous, a guard that is neither a code condition nor a registered bound, a pruned failure path, fairness on an environment action, an `EnvContract_*` without a documentation quote, and a named restriction inside a passing configuration.
2. For each finding record exact command, actual output, intended output, source anchors and confidence. Mark findings as execution-supported when a run supports them, or as reproduced on real code. Items without run evidence remain leads, and so does a refutation that rests only on reading code ([Gate 2](../../docs/exposure-gate.md#gate-2-red-team)). A reviewer other than the author records one [review verdict](../../docs/danger-grading.md#who-assigns) per finding in the [finding record](../../templates/finding-record.tsv).
3. The coordinator reruns findings and merges common causes. Keep every independently confirmed failure, not just one reviewer's list.
4. Turn a successful bypass into a mechanical check where feasible and record its ablation. Rerun the corresponding attack after gate changes.
5. On the full adequacy track, confirm each seeded mutant and each revert from the blind set on real code before it counts, then hand scoring to a role that did not build the model ([scoring](../../docs/model-adequacy.md#scoring)).

## 3. Exit checks

- Resolve each execution-supported or reproduced finding, or file a rollback ticket. The coordinator reviews these manually.
- Update the [rule registry](../../docs/rule-registry.md) with evidence and remaining gaps.
- Run the corresponding attack regressions for every gate change. The source has an ASSUMES selftest; a complete generic attack suite is not bundled.
- S5 is mandatory; a model author's success report is insufficient.
- Apply [Gate 2](../../docs/exposure-gate.md#gate-2-red-team) to every finding S6 hands back: record the refutation attempt (outer guard, documented intent, a freedom the real system lacks) and whether it failed. Record the independent reviewer and one [review verdict](../../docs/danger-grading.md#who-assigns) per finding (partly manual: the script checks the fields, the reviewer checks the claim). A finding without this record cannot be listed as verified.

## 4. Rollback

Return fidelity defects to S3 and a weak ideal to S2 with property-owner approval. Assign weak verdicts or gates to the coordinator for repair. Never modify the reviewed originals from the red-team role. Use [a rollback ticket](../../templates/rollback.md).

## Concrete Examples

For PD KV slot ownership, attack a copied ideal action, an unchecked mapping assumption and an implementation that silently discards a posted write. These exercise mirror, ASSUMES and specification-mutation checks.
