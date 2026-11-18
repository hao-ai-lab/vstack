# Working principles

These are the verification-specific adaptations already used by the source workflow. The original principle names come from Lauren Tan's pstack; attribution is in [NOTICE](../NOTICE.md).

| Principle | Effect on verification work |
|---|---|
| Attack the premise | After two fixes sharing a premise fail the same gate, test that premise before a third attempt. |
| Build the lever | Make repeated comparisons and audits reproducible. |
| Encode lessons in structure | Turn a repeated mistake into a check or a field under [Layer 0](layer-0.md), and register it in the [rule registry](rule-registry.md). |
| Exhaust the design space | Use the [S0 twin census](../skills/vstack-s0-decompose/SKILL.md#2-procedure) and [twin models for key units](../skills/vstack-mode/playbooks/coordinate.md#two-writings-for-key-units) to expose omissions. |
| Explain the number | Identify bounds and bottlenecks and show that the measured work is the claimed work. |
| Fix root causes | Distinguish a legitimate guard from suppressing the failure; ablate repair components. |
| Guard the context window | Store bulk evidence on disk; hand off conclusions and locations. |
| Laziness protocol | Prefer the smallest change supported by evidence. |
| Make operations idempotent | Examine retries, interruption at each step and convergence. |
| Model the domain | Recover explicit state machines from scattered flags and assumptions. |
| Never block on the human | Continue authorized reversible work; record choices. Respect property approval and external-action boundaries. |
| Prove it works | Prove the pinned model and invariant; require fresh full-tree evidence and [independent acceptance](gates.md#deductive-proof-acceptance). Keep implementation validation distinct. |
| Separate before serializing shared state | Keep one output owner, separate worker directories and merge at the report under [Layer 0](layer-0.md). |
| Sequence verifiable units | Integrate each proof unit into one shared module tree and recheck its affected closure through the root; isolated leaf success is provisional. |
| Subtract before you add | Run cheap checks first; use expensive checks only when the [property class](method-selection.md#property-classes-and-the-seven-pillars) needs them. |
| Test behavior, not implementation | State caller-visible promises instead of incidental field values. |
