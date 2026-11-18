---
name: vstack-mode
description: Run the Verification Stack for a concurrent, distributed or systems-software property, from source archaeology through calibrated models, red team, proof and maintained regression. Use for /vstack-mode or an end-to-end verification workflow.
---

# vstack mode

Read [Layer 0: shared operating rules](../../docs/layer-0.md). Select one playbook from the request and keep its stage exits visible. The coordinator owns the route, approval records, frozen inputs and final independent review. A worker reads only Layer 0, its own stage and assigned inputs.

| Playbook | Route and purpose |
|---|---|
| [full-verification](playbooks/full-verification.md) | Run S0 through S8; select the proof tier for each property. |
| [hunt-system-bugs](playbooks/hunt-system-bugs.md) | Run S0 through S6 to find and confirm defects with a calibrated model. |
| [build-provable-core](playbooks/build-provable-core.md) | Run S0 through S5, then S7 and S8, for new code committed to deductive proof. |
| [live-regression](playbooks/live-regression.md) | Run the project-local `verify-<case>` produced in S8 and route drift or failures. |

A route from S0 through S5 includes every intervening stage. S4 and S5 cannot be omitted. S6 can be omitted only for newly written code going to deductive proof. If a prerequisite is missing, perform it or report BLOCKED rather than calling the downstream stage complete.

Record each task's property, source revision, tier, input hashes, writable paths, exit checklist, budget and evidence locations. Use [the case playbook](../../templates/case-playbook.md). Read [working principles](../../docs/principles.md) when scoping or reviewing experiments.

Assign work to [vstack-worker](../../agents/vstack-worker.md), independent review to [vstack-redteam](../../agents/vstack-redteam.md), and keep authority with [vstack-main](../../agents/vstack-main.md). Delegate only with available host tools and user authorization. Role documents provide neither scheduling nor sandboxing.

**Coordinating units.** Every route runs its units through the [coordination loop](playbooks/coordinate.md). The coordinator generates each unit's [task brief](../../templates/task-brief.md) from a fields file with `scripts/make_brief.py`, never from another brief, and sends it only after `scripts/check_brief.py` passes, checks every reply's hand-back block with `scripts/parse_handback.py`, and keeps the [unit table](../../templates/unit-table.tsv) as the coverage matrix, checked against the plan by `scripts/check_unit_table.py`. It writes briefs, accepts and merges rows; it does not census, model or write specifications itself. Each unit gets one fresh worker with its own output directory and row copy; workers never share a writable file or see each other's directories. Drain every row to `accepted` or `blocked`, re-spawning a unit once before recording a gap. A row is complete only with evidence paths in its output directory.

**One unit first.** Send one unit of each batch through brief, work, hand-back and acceptance before fanning out the rest, so that a flaw in the brief costs one worker instead of the batch. The unit table marks that unit in `first_of_batch`; its check fails when another unit of the batch leaves `queued` before the first is `accepted`.

**Key units are written twice.** For a unit marked `key`, two workers write it independently from the same brief and frozen inputs, in separate directories. Compare the writings row by row (writer lists, guards, candidate findings) in a [writing-compare table](../../templates/writing-compare.tsv) checked by `scripts/check_writings.py`, pick a base and graft the other's extra rows before either writing is used.

**An error seen twice becomes a check or a template field.** At the end of each batch, read its hand-backs and lessons. An error class seen twice gets a failing check or a required template field in the same round, registered in the [rule registry](../../docs/rule-registry.md); text alone is not a fix ([Layer 0](../../docs/layer-0.md)).

At a failed upstream assumption, issue a [rollback ticket](../../templates/rollback.md), preserving frozen artifacts. A property change needs the property owner's explicit decision and coordinator re-pinning. Deliver PASS, ISSUES or BLOCKED with evidence; incomplete or unknown checks never count as PASS.

The [gate interface guide](../../docs/gates.md) describes actual scripts and their limits. Read it before configuring a project runner; the package does not include a generic solver harness.

## Concrete Examples

Use [PD KV slot lifecycle regression](../../examples/verify-pd-kv-slot/SKILL.md) to see how a slot-release promise becomes pins, drift checks, model checks, trace conformance and mutation regression. This illustrates the workflow, without supplying a runnable case bundle.
