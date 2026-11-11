# full-verification

Complete the property-specific verification route.

Read [Layer 0: shared operating rules](../../../docs/layer-0.md). Use the following stage cards in order; inputs pass upstream exits and carry hashes.

1. [S0 — Reconstruct and separate the system](../../vstack-s0-decompose/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
2. [S1 — Split obligations and select methods](../../vstack-s1-select/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
3. [S2 — Freeze specifications and contracts](../../vstack-s2-spec/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
4. [S3 — Build an anchored model](../../vstack-s3-model/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
5. [S4 — Calibrate and align traces](../../vstack-s4-calibrate-tv/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
6. [S5 — Attack model fidelity and gate strength](../../vstack-s5-redteam/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
7. [S6 — Find and repair bugs](../../vstack-s6-hunt-fix/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
8. [S7 — Upgrade to a proof](../../vstack-s7-prove/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
9. [S8 — Package and maintain regression](../../vstack-s8-package-maintain/SKILL.md). Deliver that stage's four-cell contract and exit evidence.

If deductive proof is not justified, record the S7 selection and bounded guarantee; do not manufacture a proof requirement. S6 may only be skipped under the new-code/deductive-proof rule.

On an upstream defect, send a rollback ticket to that stage; never edit its frozen artifact from a downstream role. The coordinator independently reviews proof certificates under the proof gates and reruns model, trace and mutation checks.
