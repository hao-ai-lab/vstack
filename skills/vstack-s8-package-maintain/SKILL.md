---
name: vstack-s8-package-maintain
description: "Package verified scope into a project-local five-step regression skill and keep it aligned with future code revisions."
---

# S8 — Package and maintain regression

Read [Layer 0: shared operating rules](../../docs/layer-0.md), this stage and the assigned input bundle.

## Role and write scope

One author per case skill; the coordinator owns gold and independently reviews evidence. Only the coordinator integrates changes.

## 1. Input

The accepted artifacts from S4, S5, S6 and S7, as required by the S1 route: models, configurations, traces, mutations, expectations and hashes.

## 2. Procedure

1. Fill [verify-skill](../../templates/verify-skill.md): coverage, synchronized revision, assumptions, bounds, one command, expected results and triage rules.
2. Run five checks in order: pins, drift, model, trace regression, then mutation regression. Keep the regression small and repeatable; measure and report its duration.
3. Break protected logic in a source copy: the check must turn red. Restore it: green with the baseline. Record prediction versus actual, including failed predictions.
4. After upstream changes, run unchanged first. Inspect all changes to covered state, including moved or new writers. Classify each as no effect, model drift, intentional promise change or possible code bug.
5. Update models from source, not from desired verdicts. Recalibrate after alignment changes and update the sync revision only after alignment succeeds. Keep verification and product-fix changes distinct.
6. For deductive claims, retain the frozen proof tree, tool and settings hashes, raw logs and [full acceptance evidence](../../docs/gates.md#deductive-proof-acceptance). Publish the root statement and premises verbatim. Bind every module result, including slice certificates, to its source, full import closure and toolchain. Refresh changed closures through the root; proof-body-only changes permit unchanged downstream reruns with persistent fingerprints, while definition or invariant changes require contract review and renewed acceptance. The five-step regression cannot renew a proof claim alone.

## 3. Exit checks

- Record both break and restore results. Require the independent clean regression rerun to match every expected row. Review deductive evidence under the proof gates without imposing a second same-source proof run.
- Distinguish baseline reproduction from a required-fix check and explain stale frozen trace evidence.
- Report maintenance as in sync, updated, bug or blocked. A blocked run does not advance the synchronized revision.
- Identify the proved design model in deductive claims; describe the implementation as validated against it. An independent reviewer must complete the proof gates before a machine-proof claim.

## 4. Rollback

Return model drift to S3, then rerun S4. Send intentional promise changes to S2 and code violations to S6. Report BLOCKED if tools or alignment are unavailable; do not move the sync commit. Use [a rollback ticket](../../templates/rollback.md).

## Concrete Examples

The [PD example](../../examples/verify-pd-kv-slot/SKILL.md) describes pins, drift, model checks, trace checks and mutations. Frozen trace checks can stay unchanged after a live source mutation; drift and source-derived model variants must detect that change.
