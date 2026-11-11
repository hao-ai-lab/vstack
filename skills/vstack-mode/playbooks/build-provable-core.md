# build-provable-core

Build a new small core with a deductive proof and maintained regression.

Read [Layer 0: shared operating rules](../../../docs/layer-0.md). Use the following stage cards in order; inputs pass upstream exits and carry hashes.

1. [S0 — Reconstruct and separate the system](../../vstack-s0-decompose/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
2. [S1 — Split obligations and select methods](../../vstack-s1-select/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
3. [S2 — Freeze specifications and contracts](../../vstack-s2-spec/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
4. [S3 — Build an anchored model](../../vstack-s3-model/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
5. [S4 — Calibrate and align traces](../../vstack-s4-calibrate-tv/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
6. [S5 — Attack model fidelity and gate strength](../../vstack-s5-redteam/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
7. [S7 — Upgrade to a proof](../../vstack-s7-prove/SKILL.md). Deliver that stage's four-cell contract and exit evidence.
8. [S8 — Package and maintain regression](../../vstack-s8-package-maintain/SKILL.md). Deliver that stage's four-cell contract and exit evidence.

Use this S6 (find and repair bugs) omission only when the property concerns newly written code going to deductive proof. Otherwise restore S6. Keep implementation refinement distinct from the design-model theorem.

Before proof work, freeze the specification and complete inductive invariant. Follow the proof stage's single-tree workflow: projections → action effects/frame facts → supported preservation cells → shared family lemmas → root composition. Recheck integrations continuously and require all [proof acceptance gates](../../../docs/gates.md#deductive-proof-acceptance) before packaging a machine-proof claim.

On an upstream defect, send a rollback ticket to that stage; never edit its frozen artifact from a downstream role. The coordinator independently reviews proof certificates under the proof gates and reruns model, trace and mutation checks.
