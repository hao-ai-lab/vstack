# Review a checker result

Before running, timestamp the sentence you expect to report. Record input hashes, tools, settings and resource limits. Do not interpret a process exit code as a correctness theorem.

## Model checks and measurements

Read constants, state and action constraints, symmetry, view, properties and worker count. Ask seven questions:

1. Which state-space dimension or resource limits the result?
2. Are compared models using the same constants, constraints and properties?
3. Does the state count make sense, or did Init or the constraints prune the behavior?
4. Were there errors, warnings, memory failures, timeouts or exploration caps?
5. Is the result reproducible? For measurements used to choose between alternatives, alternate at least five runs per side and report the median and range.
6. Does the range include the smallest known trigger?
7. Were fault actions actually explored? Supply coverage and reachability witnesses. For liveness, name the fairness (on `Engine_*` actions only), the `EnvEventuallyQuiet` bound and each assumption about a neighbouring slice, with the deployment switches under which that neighbour's contract fails.

Report **violation found**, **passed within stated bounds** or **INCONCLUSIVE**. Use **no measurable difference** only for measurements. Missing error or coverage evidence, zero required action coverage, unmatched comparison configurations or an unexplained bottleneck prevents acceptance. Unfinished work, unknown and timeout are never success.

Read the final summary of generated and distinct states, not a progress line. Violation counts from multi-worker searches can vary with scheduling; do not silently require exact counts for those rows. The source rerun table distinguishes exact checks from informational state counts.

A killed mutant must violate the expected property **and follow the expected mechanism**. Compare the historic switch combination to the actual pinned revision. A repair component outside the abstraction's reach is unverified, not proved unnecessary. Pair each positive run with its reachability witness under the same constants.

### Environment restrictions and freedoms

| Rule | Requirement |
|---|---|
| Asymmetric restrictions | A named environment timing restriction only removes behaviour. A safety violation found under it, or a liveness violation when fairness is on `Engine_*` actions only, is still a violation without it. Use restrictions in hunt and control configurations; never in a configuration reported as **passed within stated bounds**, a fix check, a [trace-acceptance](model-adequacy.md#readout-1-trace-and-baseline-agreement) run or a [blind-detection](model-adequacy.md#readout-3-blind-detection-recall) baseline. |
| Pairwise freedom coverage | When opening every environment and fault freedom together exceeds the budget (for example a 60-minute wall), split configurations by fault tier so that every pair of freedoms is open together in at least one finished run. List the higher-order combinations that did not finish. Pairwise runs cannot see a defect that needs three freedoms or a specific event order; state that limit. |
| Walls | A run stopped by a timeout, a state cap or a wall is **INCONCLUSIVE**, never passed. |
| Assume-guarantee across slices | Circular discharge between neighbouring slices (A assumes B while B assumes A) is sound for safety only (Lamport, COMPOS 1997). Discharge liveness assumptions in an acyclic order. |

## Proof runs

Use the [deductive proof gates](gates.md#deductive-proof-acceptance) for acceptance. Keep persistent native fingerprint caches enabled during development and final closure refreshes. Seed them with successful obligation results written by strict runs under the same toolchain and libraries, and retain provenance. Successful hits avoid backend work and can skip `normalize_expand`; the frontend must still generate, process and fingerprint obligations. Do not budget a large cached module as a few-minute check without measurements.

### Diagnose a timeout

1. Read the obligation's final status after the configured backend chain finishes. Keep intermediate timeout and failure events for diagnosis; allow a later backend to prove the obligation.
2. Recheck a final timeout with `tlapm --line <line>` or `tlapm --toolbox <start> <end>` in the full unchanged module context, in strict mode with higher `--stretch`. Set a finite step budget cap, for example 300 seconds. Record both preprocessing and backend budgets; stretch is a multiplier, not a duration in seconds.
3. If the step passes within that cap, change only the module's run settings, retain the source, and complete its check. If it still times out at the cap, stop raising the budget and narrow the proof step or supply missing proved facts. Preserve exported definitions and statements; review any required contract change upstream.
4. Let a check that is still advancing with zero final failures continue past its wall-clock estimate. Decide when to stop proof work from single-step diagnosis; do not kill a progressing check because its estimated whole-module deadline expired. Keep resource guards active; after a resource kill, record an incomplete run and retry unchanged under adequate authorized settings.

### Schedule complete checks

Keep small modules in whole-module runs. For large checks limited by serial frontend work, follow the [slice-certificate procedure](gates.md#slice-certificates): cut only between top-level theorems or first-level steps, retain the complete module context, and use separate new caches with `--strict --nofp` for certified slices. Start with one or two backend threads per slice and limit concurrency by aggregate memory.

Count a whole-module invocation or its coordinated slice processes as one check run. Keep at most one active run per module across snapshots and hosts. Retire a superseded run and confirm its recorded process groups have exited before starting its replacement. Overlap rounds on different modules so new snapshots do not queue behind unrelated long tails. Refresh each downstream module as soon as its own changed upstream dependencies have final passing sources.

Estimate with observed obligation counts, cache hits and concurrent load. Multiply isolated wall-clock estimates by a measured contention factor; until calibrated, use the number of overlapping runs sharing resources as a rough factor and label it an estimate. Track completed obligations over total obligations and elapsed time, then revise the remaining-time estimate from actual progress. Progress is a scheduling signal, never acceptance evidence.

Budget aggregate memory and CPU for all active processes and keep reserve capacity under the project guard. Treat allocation failures as resource events, not reasons to rewrite a proof that has no final failed obligations. For sustained frontend savings, split large modules and remove broad `DEF` expansion; neither extra threads nor fingerprints eliminate all frontend work.
