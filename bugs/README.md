# Verified AI Infra Bugs (`vstack`)

[`verified-bugs.csv`](verified-bugs.csv) is the canonical source for the live [Verified AI Infra Bugs](https://docs.google.com/spreadsheets/d/1FL5QqgzEpja9k8Zw6GmIQDtHveddjj1coHe1MJ3Ts-Q/edit?gid=0#gid=0) tracker. Merged pull requests to `verified-bugs.csv` are synced one-way into per-system tabs (`SGLang`, `vLLM`) on the read-only Google Sheet via [`scripts/sync_bugs_sheet.py`](../scripts/sync_bugs_sheet.py).

The ledger records real defects that `vstack` workflows caught in AI infra code. `method` says how a row was found; `human_verifier` says whether it is verified. Only a row with `method = model_check` that passes [Gate 1a and Gate 1b](../docs/exposure-gate.md#gate-1-formal-exposure) may be described as "caught by model checking". [`scripts/check_docs.py`](../scripts/check_docs.py) checks the column values below.

## Formal Specification Pillars (`violated_spec`)

| Pillar | Class | Meaning |
| :--- | :--- | :--- |
| **`Isolation`** | Safety (`□`) | Live requests never overwrite, read, or alias another request's KV/state slots. |
| **`Integrity`** | Safety (`□`) | A request's own KV blocks, recurrent state, cache keys, and adapter weights remain uncorrupted across steps and reloads. |
| **`Conservation`** | Safety (`□`) | Slot allocations, reference counts, reserved indices, and clear hooks stay exact. |
| **`Agreement`** | Safety (`□`) | Ranks, control plane, and execution plane agree on active generation/memory state. |
| **`Progress`** | Liveness (`~>`) | Admissible requests eventually run without livelock, deadlock, or queue starvation. |
| **`Finality`** | Bounded-response safety (`□`) | Aborts, disconnects, and expired leases terminate and reclaim resources in bounded steps. |
| **`Invariance`** | Equivalence (`≡`) | Output is invariant across batch composition (`M=1` vs `M>1`) and streaming chunking. |

[Property classes](../docs/method-selection.md#property-classes-and-the-seven-pillars) gives each pillar's formal class and preferred route.

## Method (`method`)

One of `model_check`, `smt`, `exhaustive_sweep` or `experiment`, as defined in the [method classes](../docs/exposure-gate.md#method-classes) of the exposure gate. `checker` names the tool or test behind it (`TLC`, `Z3`, `Diff test`, `Replay`, `Code audit`). `method` records how a row was found; it is not a Gate 1 verdict.

## Human Verifier (`human_verifier`)

| Value | Meaning |
| :--- | :--- |
| `In Progress` | A candidate awaiting review. |
| `@github_handle` | Verified: the row passed every [exposure gate](../docs/exposure-gate.md) that applies to its method, including a real-engine reproduction next to a passing control (Gate 3 at level `real engine`), recorded in `evidence`. |

## Prior Status (`prior_status`)

| Value | Meaning |
| :--- | :--- |
| `Unknown` | Unreported upstream prior to the `vstack` formal scan. |
| `Partly Known` | A narrower symptom or crash was reported upstream, while the deeper corruption or root mechanism was unreported. |
| `Known` | Previously reported in an upstream Issue or unmerged PR (still present on `main` at scan time) and independently rediscovered by `vstack` without reading GitHub reports. |

## Found (`found_on`)

UTC date when the finding was first recorded in our repository (the first model counterexample log or the date an earlier entry entered the bug ledger), rather than the upstream issue or PR date.

## How to Contribute a Verification or New Bug

1. **Verify an `In Progress` candidate:** Pick a row with `human_verifier = In Progress`, reproduce it on real hardware (or refute it by showing an outer guard in live `main`), and open a PR updating `human_verifier` to your `@github_handle` (plus `upstream_label` / `upstream_url` if you file an upstream Issue or fix PR).
2. **Validate an open fix PR or contribute a new formally caught bug:** Run `vstack` on an AI infra repository, confirm a model counterexample on real code/hardware, and submit a row to `verified-bugs.csv` with its `method`. A row may be marked verified only if it passes the [exposure gate](../docs/exposure-gate.md).
3. **Required PR evidence:** Include (a) target repo & commit SHA, (b) exact reproduction command or unit test, and (c) observed failure vs. control output in your PR description. Run `python3 scripts/check_docs.py` before opening the PR.
4. **Responsible disclosure:** Never submit public PoCs for unfixed cross-request or cross-tenant silent data corruption; report those privately to upstream maintainers first.
