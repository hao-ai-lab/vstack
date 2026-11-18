# Exposure gate: when a finding counts as caught by formal checking

One rule for what may be reported as "caught by model checking": in the bug ledger, in a report, in a talk. It exists
because a counterexample alone proves little. A model can restate a bug it was told about, re-create a known bug with a
switch, or describe code that does not behave that way on a real engine.

A finding is listed as verified only when every gate that applies to its [method](#method-classes) holds, each with a
pointer to its evidence. Each gate is checked at one stage, so no single stage has to clear all four:

| Gate | Checked at | By |
| :--- | :--- | :--- |
| [1a, 1b](#gate-1-formal-exposure) and `found_by` | [S6 exit checks](../skills/vstack-s6-hunt-fix/SKILL.md#3-exit-checks) | S6 worker |
| [2](#gate-2-red-team) | [S5 exit checks](../skills/vstack-s5-redteam/SKILL.md#3-exit-checks); S6 findings return to the red team | Red team |
| [3](#gate-3-real-engine) | [S6 step 4](../skills/vstack-s6-hunt-fix/SKILL.md#2-procedure) | S6 worker |
| [4](#gate-4-coordinator-re-verification) | [Coordinator acceptance](../agents/vstack-main.md) | Coordinator |

## Gate 1: formal exposure

A checker violates a named property on a model of the real mechanism. Gate 1 has two parts.

### Gate 1a: zero injected switches

Required for net-new findings. Every injected-bug and mutation switch (`Bug_*`, `Mut_*`) is off. The model takes local
behaviour from the source: "this function releases the slot only when the request has no session" is read from
`file:line@commit` and written into the model as the code's own rule.

### Gate 1b: non-shell emergence

Required for net-new findings and for the historical-revert and mutant runs scored by the
[model adequacy readout](model-adequacy.md), which need a switch and so never pass Gate 1a.

- The violating and the passing configuration do not differ only in a shell constant that restates the defect.
- The checker derives the violation from several local steps: under which combination of components, options and
  orderings the system-level property breaks.
- A control configuration that differs only in something a deployment can vary (an option, a scale, an environment
  freedom) passes, and the model passes once the guard or fix is added.

What does not pass Gate 1:

| Case | Fails | Why |
| :--- | :--- | :--- |
| Shell model | 1b | The violating and the passing configuration differ only in a constant that restates the defect ("this kernel stores padding rows"). The checker adds nothing to reading the code. |
| Experiment only | 1 (no model) | A failure met while running a test, whose mechanism is in no model. Report it as an experimental finding, not as a formal one. |
| Calibration | 1a | A violation that needs a `Bug_*` or `Mut_*` switch, used to check that the model can reproduce a known historical bug. It shows the model is sensitive; it is not a finding. When it also passes 1b it counts in the [adequacy readout](model-adequacy.md#numerators). |

## Method classes

Each finding, and each ledger row's `method`, names one class. The class decides which gates apply and how the finding
may be described.

| Method | What ran | Gate 1 | Report as |
| :--- | :--- | :--- | :--- |
| `model_check` | A model checker (TLC, Apalache) on a code-anchored state machine | 1a and 1b | "caught by model checking" once every gate holds |
| `smt` | An SMT solver (Z3) on an anchored descriptor of real dispatch or computation | 1a and 1b, with the descriptor as the model | "caught by SMT checking" once every gate holds |
| `exhaustive_sweep` | An `Exhaustive Property Sweep`: enumeration or differential testing of the real code over a declared input domain, with no abstract model | Not applicable | An exhaustive-sweep finding, never model checking |
| `experiment` | A test, replay, engine run or code audit of the real code, without a model or a declared input domain | Not applicable | An experimental finding |

Gates 2, 3 and 4 apply to every method.

## Gate 2: red team

An independent pass tried to refute the finding and failed: no outer guard makes it unreachable, it is not documented
as intended, and the trace does not rely on a freedom the real system does not have.

A refutation is a claim too. One that rests only on reading code (an outer guard, a defensive copy, a check in
another function) is a lead until a run of the trigger shows that the cited guard stops it on this path; until then
the finding stays open. A reading that the finding stands is likewise a lead, settled by [Gate 3](#gate-3-real-engine).
Independent readings of the same code can both be wrong, so re-judge a sample of refuted leads with known bugs of the
same code mixed in: a known bug judged refuted shows that the refutation method misses. Search for a guard, a copy or a
writer by the bare function or field name (`replace(`, `.slots =`), not only by its qualified form
(`module.replace(`); calls through an alias, an instance method or a re-export are otherwise missed.

## Gate 3: real engine

The failure is reproduced on a real engine, in the same run as a control that behaves correctly. The evidence states
the level reached, counts with their unit (runs, requests, positions) and kind (random, directed, selected), the
control, every non-default flag or injected delay, the model served and the commit. Put the level, entry point,
default and actual launch commands, non-default settings, preconditions, injection details, counts with their unit
and kind and control arms in the
[finding record fields](../templates/finding-record.tsv); prose alone no longer suffices for those facts.
Keep the served model and run commit in the supporting evidence.

Levels are kept apart and never rounded up: `model only`, `CPU replay of real code`, `real engine`. The gate holds only
at `real engine`. A named `human_verifier` requires a real-engine record.

## Gate 4: coordinator re-verification

Someone other than the author re-runs the check from a clean copy, reads the model and the test, and confirms the
counts from the raw result files.

## Anti-vacuity checks

Defined here once; stage cards link to this section. Every property, and every finding's model, carries:

| Check | Requirement |
| :--- | :--- |
| Negative mutant | Remove the guard (or weaken the update) in the model: the property is violated. |
| Reachable witness `W_*` | Name the situation the property talks about as `W_<situation>`; it occurs in the passing runs, so `~W_<situation>` checked as an invariant is violated. |
| Fix flip | For a fix: restoring the bug fails and applying the fix passes, in the model and on the code. |

For real traces, the counterpart is the [non-vacuous checker](trace-validation.md) rule: model mutations must reject
the same real traces.

## What to record

- `found_by`: `checker` when the run was expected to pass (or nothing was predicted) and it was violated; `reading`
  when the defect was noticed while reading code for the model and the checker confirmed it and gave the
  interleaving. Both can pass Gate 1. Reports say which one it was; "the checker predicted it" is reserved for
  `checker`.
- The method class, the Gate 1a and 1b results and the Gate 3 level of each finding.
- The [finding record](../templates/finding-record.tsv) fields: entry point and kind; default and actual launch
  commands; computed non-default settings; preconditions; injection and model restriction; hits, runs, unit and
  kind; stock, patched and reference arms and reference kind; consequence and impact; duplicate search and checked
  upstream commit; verdict and independent reviewer; ambiguous facts; computed tier, grade and route. A fact not
  established is `unknown`, never a placeholder. See [danger grading](danger-grading.md).
- A finding that lets one request read or change another request's data, or that ends the service for more than the
  request itself (a process exit, refused new requests, failed in-flight requests), carries the `cross_request_data:`
  or `availability:` marker in `impact`. Its reportable route is then the private security channel, which comes before
  any public text. See [private routing](danger-grading.md#private-routing).
- A bounded pass is written as "no violation within the checked bounds", with the bounds.
- A property added after a failure was already known is marked as such next to its trace.

## Examples

| Finding | Gate 1 | Notes |
| :--- | :--- | :--- |
| Ranks enter different collectives when a rank-local defer decision meets a group-wide gather | pass | Control with the threshold at 0 passes; the fix variant passes at 2 and 4 ranks; reproduced 3 of 3 on a real engine. `found_by: reading`. |
| A model of padded CUDA-graph rows whose configurations differ only in a "stores padding rows" constant | fail 1b (shell model) | Keep as a code-reading lead; do not list it as caught by model checking (if recorded in the ledger from an experiment or code audit, use `method = experiment`, as in `VS-014`). |
| A crash on the first forward after an idle cache flush, found while running another test | fail (experiment only) | A real bug, reported upstream as an experimental finding. |
| A heartbeat defect reproduced by turning on the switch for a known upstream report | fail 1a (calibration) | Prior status is `Known`; the run calibrates the model. |
