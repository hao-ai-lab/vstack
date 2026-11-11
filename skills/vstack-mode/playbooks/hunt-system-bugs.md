# hunt-system-bugs

Find and confirm defects in existing system code.

Read [Layer 0: shared operating rules](../../../docs/layer-0.md). Use the following stage cards in order; inputs pass upstream exits and carry hashes.

1. [S0 — Reconstruct and separate the system](../../vstack-s0-decompose/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
2. [S1 — Split obligations and select methods](../../vstack-s1-select/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
3. [S2 — Freeze specifications and contracts](../../vstack-s2-spec/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
4. [S3 — Build an anchored model](../../vstack-s3-model/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
5. [S4 — Calibrate and align traces](../../vstack-s4-calibrate-tv/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
6. [S5 — Attack model fidelity and gate strength](../../vstack-s5-redteam/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
7. [S6 — Find and repair bugs](../../vstack-s6-hunt-fix/SKILL.md). Deliver that stage's four-cell contract and exit evidence.

Stop at the S6 deliverable: classified, reproducible findings and validated repairs. S7 (upgrade to a proof)/S8 (package and maintain regression) are subsequent work, not implicitly completed.

On an upstream defect, send a rollback ticket to that stage; never edit its frozen artifact from a downstream role. The coordinator reruns accepted outputs independently.
