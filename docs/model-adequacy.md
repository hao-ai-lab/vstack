# Model adequacy readout

How closely does a model follow the code it claims to describe? This readout answers with three numbers, each with
its denominator. It is partly mechanical and otherwise a documented procedure. It reports; it is not a gate. It sets
no pass thresholds and assigns no quality labels: at the sample sizes one slice yields, the intervals of good and poor
models overlap ([readout 3](#readout-3-blind-detection-recall)).

Terms defined elsewhere: [Gate 1a and 1b](exposure-gate.md#gate-1-formal-exposure), the
[anti-vacuity checks](exposure-gate.md#anti-vacuity-checks) with their `W_*` witnesses, and
[trace conformance](trace-validation.md).

## Tracks

| Track | Always required | Readout |
| :--- | :--- | :--- |
| [`hunt-system-bugs`](../skills/vstack-mode/playbooks/hunt-system-bugs.md) | The [exposure gate](exposure-gate.md), [`InputEnabled_<E>`](../skills/vstack-s3-model/SKILL.md#open-environment) invariants and `W_*` witnesses | Readout 1, where `TAR` may be `N/A (no trace harness)`. No historical denominator, no blind matrix. |
| [`full-verification`](../skills/vstack-mode/playbooks/full-verification.md), [S8](../skills/vstack-s8-package-maintain/SKILL.md) regression skills, benchmark evaluations | Everything the hunt track requires | All three readouts. |

A model reported with `TAR = N/A` supports findings, not a high-assurance claim.

## Readout 1: trace and baseline agreement

- **Trace acceptance rate** `TAR = M_consumed / M_traces`: real traces that some model execution consumes completely
  (existential completion in [trace conformance](trace-validation.md)), over the traces offered. CPU replay traces of
  real code and real-engine traces both count; state which. Without traces, write `TAR = N/A`; never count `0/0` as
  100%.
- **Negative-mutant rejection rate**, required wherever `TAR` is reported: the fraction of paired negative mutants (a
  tampered trace or a weakened guard) that the model rejects. Trace acceptance is existential: a wider model accepts
  more, so deleting a guard never lowers `TAR`. Only the rejection rate exposes that.
- **Clean-baseline counterexamples**: count every counterexample on the fixed source baseline once as
  `Confirmed Bug` (reproduced, with its [Gate 3](exposure-gate.md#gate-3-real-engine) level), `Model Defect` (triaged as a
  model error) or `Unjudged (pending repro)`. Report all three counts.

Without a TLA+ model, readout 1 becomes:

| Method | In place of `TAR` | Negative check |
| :--- | :--- | :--- |
| Z3 descriptor | Differential agreement of the descriptor with the real dispatch function over the declared input domain. Compare dispatch results (kernel, branch), not floating-point values. Expect 100%; it means nothing outside that domain. | A mutated descriptor branch must disagree. |
| Exhaustive property sweep | `N/A`: there is no abstract model. Report stub fidelity: each stubbed function and its sampled differential agreement with the real one, and the gap between the swept input domain and inputs reachable in deployment. | A mutated real-code site must fail the sweep. |

## Readout 2: historical fix coverage

### Denominator `I_U`

S0 freezes `I_U`, the historical fixes slice `U` should cover:

1. **Unit.** A fix pull request merged into the main branch. Unfixed issues go to the hunting pool, not here. Reverts,
   relands and follow-ups of one root cause count once.
2. **Window and paths.** Merged in `[pin - 24 months, pin]`; filter by changed file paths, never by titles. Exclude
   fixes that change only docs, tests, CI configuration, benchmarks, examples or Docker files. Fixes only to kernels,
   quantization or weight mapping go to a separate numeric pool. `Invariance` dispatch and parser fixes get their own
   denominator, so the numeric pool does not absorb them.
3. **Survival.** Keep a fix only if the functions or anchors it changed still exist at the pin; record the rest as
   `code_gone`.
4. **Slice.** A surviving fix belongs to `I_U` when the functions it changed intersect the S0 anchor functions of `U`
   and two readers, independently and from a frozen closed set of classes, judge it a state or protocol fix. Report
   their agreement rate. Give every excluded fix a reason code from a closed set; hash the list with its reasons
   (SHA-256).

Engine-wide coverage `Cov_total` measures how much of the engine has models. Report it as progress; it says nothing
about the quality of one model.

### Numerators

Both numerators aggregate the four S4 calibration checks over the frozen `I_U`; there is no second set of criteria.

- `Cov_expr(U)`: the fraction of `I_U` whose pre-fix logic, restored by `.cfg` operator overrides alone (no `.tla`
  change, see [anchor map](#anchor-map)), violates a frozen property.
- `Cov_emergent(U)`: the fraction of `I_U` that is in `Cov_expr(U)` and also passes
  [Gate 1b](exposure-gate.md#gate-1b-non-shell-emergence). A restored bug needs a switch, so Gate 1a never applies here.

Report both over the same denominator. Attribute every fix outside `Cov_emergent(U)` to one residual class:
`Single-Site Guard`, `Unmodeled Anchor`, `Cross-Slice Coupling` or `Sub-Step Numeric`. Many real fixes are single-site
guards, which a faithful model can only restate, so a gap between the two numerators is expected and a low
`Cov_emergent` alone does not show a poor model.

## Readout 3: blind detection recall

### Calibration and blind sets

After S0 freezes `I_U`, the coordinator draws `max(2, ceil(0.2 * |I_U|))` fixes with a published random seed as the
white-box calibration set for S2 and S3. The rest is the sealed blind set `H`: share only its hash, and remove every
trace of `H` from the S0 maps and S2 documents handed to S3. A role that did not build the model unseals `H` to score.

Public issues and pull requests in `H` may be in a modelling LLM's training data. Only a historical time point `t_0`
later than that LLM's training cutoff, with `git blame` confirming each defect existed at `t_0`, rules this out;
otherwise label `BDR_revert` possibly contaminated. Synthetic mutants do not have this problem.

### Anchor map

S3 writes each guard and state update it actually models as a named operator used by its actions (`G_A12 == ...`,
`U_A13(x) == ...`) and lists each in `ANCHORS.tsv`. Code the model leaves out needs no row.

```text
file    line_start-line_end    commit    kind (guard | update | order)    operator
```

### Scoring

1. **Confirm on real code.** Mutants (single-site guard or counter changes, drawn by seed from in-scope functions) and
   reverts of fixes in `H` enter the denominator `N` only after a CPU unit test or replay of the real code shows that
   the change breaks the target behaviour. This drops equivalent mutants and reverts masked by newer guards.
2. **Map mechanically.** A script compares the changed lines with `ANCHORS.tsv`. A change inside a registered operator
   becomes a TLC configuration override, for example `CONSTANT G_A12 <- MutTrue`, with the replacement defined in a
   generated wrapper module that `EXTENDS` the model. A confirmed change on unregistered lines, or one that splits two
   steps the model merged into one, scores `0` (`Unmodeled Anchor` or `Atomicity Gap`).
3. **Run without editing.** The examiner runs every pre-registered configuration with the override and never edits
   the `.tla`, widens a bound or chooses configurations. Score `1` when some configuration violates a frozen property,
   the violation passes Gate 1b and the run without the override passes.
4. **Report separately.** `BDR_revert = K_rev / N_rev` over reverts from `H` and `BDR_mutant = K_mut / N_mut` over synthetic
   mutants, each with its Clopper–Pearson 95% interval. Never add them. With `N = 10` the interval is wide: 8/10 gives
   [0.44, 0.97] and 3/10 gives [0.07, 0.65]. Mutants drawn from the same guards are not independent, so the effective
   sample is smaller still.
