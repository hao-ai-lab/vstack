# Verified AI Infra Bugs (`vstack`)

[`verified-bugs.csv`](verified-bugs.csv) is the canonical source for the live [Verified AI Infra Bugs](https://docs.google.com/spreadsheets/d/1FL5QqgzEpja9k8Zw6GmIQDtHveddjj1coHe1MJ3Ts-Q/edit?gid=0#gid=0) tracker. Merged pull requests to `verified-bugs.csv` are synced directly to the read-only Google Sheet.

## Formal Specification Pillars (`violated_spec`)

| Pillar | Property Forms | Meaning |
| :--- | :--- | :--- |
| **`Isolation`** | Safety (`□`) / 2-Run | Live requests never overwrite, read, or alias another request's KV or recurrent state slots. |
| **`Integrity`** | Safety (`□`) | Consumers read only complete, generation-matched, and accurately accounted state and budgets. |
| **`Finality`** | Safety (`□`) / Liveness (`~>`) | Cancellations, waits, and admin or admission steps stop or settle cleanly within bounded steps. |
| **`Conservation`** | Safety (`□`) / Liveness (`~>`) | Slot allocations, row bounds, reference counts, and reserved indices stay exact and return once. |
| **`Invariance`** | Hypersafety (`2-Run`) | Output and logprobs remain invariant across batch size, CUDA graph padding, and stream chunking. |
| **`Consensus`** | Safety (`□`) | Distributed ranks and control planes agree on per-round decisions and collective call order. |

## Prior Status (`prior_status`)

| Value | Meaning |
| :--- | :--- |
| **`Unknown`** | Unreported upstream prior to our verification pass. |
| **`Known`** | Tracked in an existing upstream Issue or unmerged PR on `main`, with a formal counterexample or new hardware reproduction contributed here. |

## How to Contribute a Verification or New Bug

1. **Verify an `Unverified` candidate (`Needs Repro`):** Pick a row with `human_verifier = Unverified`, reproduce it on real hardware (or refute it by showing an outer guard in live `main`), and open a PR updating `human_verifier` to your `@github_handle` (plus `upstream_label` / `upstream_url` if you file an upstream Issue or fix PR).
2. **Validate an open fix PR or contribute a new formally caught bug:** Run `vstack` on an AI infra repository, confirm a model counterexample on real code/hardware, and submit a row to `verified-bugs.csv`.
3. **Required PR evidence:** Include (a) target repo & commit SHA, (b) exact reproduction command or unit test, and (c) observed failure vs. control output in your PR description.
4. **Responsible disclosure:** Never submit public PoCs for unfixed cross-request or cross-tenant silent data corruption; report those privately to upstream maintainers first.
