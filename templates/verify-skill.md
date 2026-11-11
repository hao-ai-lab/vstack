---
name: verify-<case>
description: "Check <observable property> for changes to <covered code>; use before and after those edits."
---

# verify-<case>

## Promise and scope

- Approved property, harm and owner decision: <...>.
- Last aligned source revision: <...>.
- Model action/variable => path:line@commit => atomicity: <coverage table>.
- Domains, assumptions, unobserved state and non-goals: <...>.

## Run

<Exact project-local command and expected output. The runtime and dependencies must be measured and recorded.>

Use the project resource guard. Missing inputs, timeout, unknown and incomplete checks never pass.

## Gates

- Pins: compare approved specs, configs, models and gold with trusted hashes.
- Drift: compare covered methods and all writers, including moved/new code, with the aligned revision.
- Model check: calibrated faulty/fixed/ablated behaviors, nonempty exploration and required action witnesses.
- Trace: existential full completion, faults, observation limits and first-divergence triage.
- Mutation: both model and code edits must be detected; restore and require the baseline again.
- Counterexample triage: replay using the actual code; distinguish property, model, instrumentation and code failures.

## Read and maintain

A baseline matching its known violations does not mean the implementation is repaired. State a separate required-fix contract when relevant.

Classify changes as no effect, model drift, intentional promise change or possible code bug. Update models from code evidence. Promise changes need owner approval. Update the aligned revision only after successful alignment and regression.

## Break/restore record

| Mutation | Timestamped prediction | Actual result | Restore result | Evidence |
|---|---|---|---|---|
| <...> | <...> | <...> | <...> | <...> |

## Sources

- <project sources and approval records for this instantiated skill>.
