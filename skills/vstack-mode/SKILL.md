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

At a failed upstream assumption, issue a [rollback ticket](../../templates/rollback.md), preserving frozen artifacts. A property change needs the property owner's explicit decision and coordinator re-pinning. Deliver PASS, ISSUES or BLOCKED with evidence; incomplete or unknown checks never count as PASS.

The [gate interface guide](../../docs/gates.md) describes actual scripts and their limits. Read it before configuring a project runner; the package does not include a generic solver harness.

## Concrete Examples

Use [PD KV slot lifecycle regression](../../examples/verify-pd-kv-slot/SKILL.md) to see how a slot-release promise becomes pins, drift checks, model checks, trace conformance and mutation regression. This illustrates the workflow, without supplying a runnable case bundle.
