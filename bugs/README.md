# Verified AI Infra Bugs (`vstack`)

[`verified-bugs.csv`](verified-bugs.csv) is the canonical source for the live [Verified AI Infra Bugs](https://docs.google.com/spreadsheets/d/1FL5QqgzEpja9k8Zw6GmIQDtHveddjj1coHe1MJ3Ts-Q/edit?gid=0#gid=0) tracker. Merged pull requests to `verified-bugs.csv` are synced directly to the read-only Google Sheet.

## Formal Specification Pillars (`violated_spec`)

| Pillar | Class | Meaning |
| :--- | :--- | :--- |
| **`Isolation`** | Safety (`□`) | Live requests never overwrite, read, or alias another request's KV/state slots. |
| **`Conservation`** | Safety (`□`) | Slot allocations, reference counts, reserved indices, and clear hooks stay exact. |
| **`Authority`** | Safety (`□`) | Ranks, control plane, and execution plane agree on active generation/memory state. |
| **`Progress`** | Liveness (`~>`) | Admissible requests eventually run without livelock, deadlock, or queue starvation. |
| **`Finality`** | Liveness (`~>`) | Aborts, disconnects, and expired leases terminate and reclaim resources in bounded steps. |
| **`Invariance`** | Equivalence (`≡`) | Output is invariant across batch composition (`M=1` vs `M>1`) and streaming chunking. |

## How to Contribute a Verification or New Bug

1. **Verify an `Unverified` candidate (`Needs Repro`):** Pick a row with `human_verifier = Unverified`, reproduce it on real hardware (or refute it by showing an outer guard in live `main`), and open a PR updating `human_verifier` to your `@github_handle` (plus `upstream_label` / `upstream_url` if you file an upstream Issue or fix PR).
2. **Validate an open fix PR or contribute a new formally caught bug:** Run `vstack` on an AI infra repository, confirm a model counterexample on real code/hardware, and submit a row to `verified-bugs.csv`.
3. **Required PR evidence:** Include (a) target repo & commit SHA, (b) exact reproduction command or unit test, and (c) observed failure vs. control output in your PR description.
4. **Responsible disclosure:** Never submit public PoCs for unfixed cross-request or cross-tenant silent data corruption; report those privately to upstream maintainers first.
