# Case playbook: <property>

## Frame before running

- Falsifiable completion predicate: <...>.
- Covered files/functions and pinned revision: <...>.
- State, actors, faults, domains and known calibration bugs: <...>.
- Assurance tier and why it fits consequences/scale/ownership: <...>.
- Stage route and any allowed omissions: <...>.
- Owner, assigned writable paths, inputs/hashes, budget and stop conditions: <...>.
- Strongest original evidence; what an expert would check beyond this brief: <...>.
- Independent evidence beyond author self-report: <...>.

## Design the sequence

Resolve the riskiest unknown first. Establish the buggy baseline, then split into independently checkable units with one output owner each. Record each stage's input, procedure, exit evidence and rollback destination. S4 (calibrate and align traces) and S5 (attack model fidelity and gate strength) stay mandatory.

## Experiment record

- Actual UTC and prediction, before running: <...>.
- Hypothesis and smallest change: <...>.
- Exact command, artifact hashes, guard and limits: <...>.
- Expected / actual / explanation for any mismatch: <...>.
- Evidence paths; state/action coverage; completion status: <...>.
- VERIFIED / NOT VERIFIED / INCONCLUSIVE: <...>.

After repeated failures sharing a premise, test that premise. A gate defect is a separate repair, not a reason to bypass it. Write the decision trail as work proceeds.

## Handoff

- PASS / ISSUES / BLOCKED against the completion predicate: <...>.
- Completed paths and hashes; unresolved items and scope limits: <...>.
- Process groups created and confirmed exited: <...>.
- Next concrete action and rollback tickets: <...>.
