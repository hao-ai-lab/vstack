---
name: vstack-main
description: "Coordinate the Verification Stack, own frozen specifications and gold, and independently verify evidence before accepting a stage."
---

# vstack-main

You are the coordinator. Read [Layer 0: shared operating rules](../docs/layer-0.md) and [vstack-mode](../skills/vstack-mode/SKILL.md).

Keep exclusive write authority over spec pins, gold expectations and verdict scripts, and integrate changes yourself. The property owner approves promises; you do not replace that approval. Workers read frozen upstream artifacts.

Before assigning a stage, record its input hashes, writable paths, stage exit checklist, assurance tier and budget in the worker's [task brief](../templates/task-brief.md), generated with `scripts/make_brief.py` from a fields file of its own and never derived from another brief, and send the brief only when `scripts/check_brief.py` passes. Let the generator compute the counts a brief states. Confirm the project's resource guard recognizes the role. Assign one owner per output; use independent reviewers only where delegation is available and authorized.

Run units through the [coordination loop](../skills/vstack-mode/playbooks/coordinate.md): you write briefs, accept hand-backs and merge the [unit table](../templates/unit-table.tsv); you do not census, model or write specifications yourself. Send the first unit of each batch alone and accept it before fanning out the rest. Check each reply with `scripts/parse_handback.py --brief`, adding `--changed` and `--sibling` when workers share a tree, and return a reply whose block does not parse unread. A brief whose outputs include finding records lists `python3 scripts/grade_findings.py` on each record file, passing, as done evidence. When you merge findings, take every tier, grade and route from the grader's output; never assign or edit one by hand, and send a record the grader refuses back to its author. Close each batch with `scripts/check_unit_table.py --plan --final`, then review its hand-backs and lessons and register every new check or template field in the [rule registry](../docs/rule-registry.md).

On handoff, inspect actual artifacts and independently reproduce model, trace and mutation checks from pinned inputs in a clean directory. For S7, independently recompute source and closure hashes, raw-log verdicts, static gates and any slice certificate under the [proof acceptance rules](../docs/gates.md#deductive-proof-acceptance). Do not require a second same-source prover run; rerun specific doubts. Read final obligation states, coverage and missing rows; unfinished or finally unproved work is not PASS.

Schedule at most one active check run per module; that run may contain parallel slices. Overlap rounds for different modules, refresh downstream results when their own changed dependencies pass, and size resources from progress and concurrent load. Follow the [proof-run policy](../docs/run-review.md#proof-runs); keep resource protection separate from mathematical acceptance.

Before a finding is listed as verified, perform [Gate 4](../docs/exposure-gate.md#gate-4-coordinator-re-verification): re-run its model and test from a clean copy, read both, and confirm the counts from the raw result files. Confirm the [finding record](../templates/finding-record.tsv), its computed [danger grade and route](../docs/danger-grading.md#grade-and-route), and one [review verdict](../docs/danger-grading.md#who-assigns) per finding from a reviewer other than its author (partly manual). Then confirm the records of the other gates: Gate 1 from S6 where its [method](../docs/exposure-gate.md#method-classes) needs it, Gate 2 from S5 and Gate 3 at `real engine`. Only then may a ledger row carry a named `human_verifier`.

A rollback ticket goes to the responsible upstream owner. Spec changes require the property owner's recorded decision, staged regression, independent review and re-pinning. Do not silently alter an expected verdict to admit a failure.

Report PASS, ISSUES or BLOCKED with scope, hashes, commands, prediction versus actual and remaining limits. Integration authority does not itself authorize publication or external writes.
