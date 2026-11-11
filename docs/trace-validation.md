# Trace conformance checklist

Start each conclusion with model modules and hashes, code revision, actual system configuration, real or stubbed execution, and what was not observed. One unanswered item means **partial validation**, not complete conformance.

| Rule | Required evidence |
|---|---|
| Existential completion | At least one model execution consumes the entire trace. With `TraceNotDone == l <= Len(TraceLog)` as an invariant, its violation witnesses completion. A completed exploration without that violation is NOT_CONSUMED. Timeout, error or an exploration cap is INCONCLUSIVE. Do not demand every possible execution complete the trace. |
| Non-vacuous checker | Run model mutations against the **same real traces**. Each mutation must make at least one trace NOT_CONSUMED at the predicted event. Synthetic or CPU replay-only tests do not replace this check. Report a matrix of results for each mutation and trace, with the kill rate. |
| Coverage | Every claimed bug mechanism needs a real trace and a distinction between buggy and fixed model settings. Count actions visited by consumed traces; exclude unvisited actions from the conformance claim. Report distinct behavior classes, not only repeat counts. |
| Observation strength | Map each model variable to an observed event or field, or mark it unobserved. Driver-supplied assertions are not observations. Unobserved variables are unconstrained by the trace evidence. |
| Trustworthy instrumentation | Preserve causal order; timestamp entry to the hooked operation, not log writing. Snapshot shared state at action start. Compare behavior with and without hooks on the same workloads, and record the instrumentation hash. |
| Triage every mismatch | Find the first divergence. Use evidence to classify it as a wrong invariant, a mismatch between model and code, an overly narrow or broad model, an instrumentation error, or a real code bug. Hand-edited, reordered, truncated or field-deleted traces are diagnostic only. |
| Both directions | Sampled code executions accepted by the model do not establish that every model execution is realizable. Reproduce model counterexamples or representative executions on the real system and state the reproduction level. |
| Resist overfitting | After changing a model to match traces, rerun calibration of historical bugs, fixes and repair ablations, the specification mutation suite and the full regression. Record the code-based reason for the change; the coordinator independently repeats checks. |

Separate trace completion from safety verdicts. `VIOLATION:TraceNotDone` is a successful completion witness; a violation of some other invariant does not establish that the whole trace was consumed.

For an independent review, rerun a representative of each scenario class, at least three checker-strength mutations, and every mismatch classified as a real bug in a separate clean output directory. Preserve disagreements and predictions that failed.
