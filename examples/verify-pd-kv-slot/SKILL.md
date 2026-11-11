---
name: verify-pd-kv-slot
description: "Illustrate an S8 (package and maintain regression) regression skill for PD KV slot ownership, release and reuse; use as a project adaptation example."
---

# PD KV slot lifecycle: regression skill example

This is a redacted workflow example, not an executable verification bundle. Supply the project's approved models, source tree, trace corpus, mutation suite, expected verdicts and runner before treating any check as runnable. No experimental results or raw evidence are included.

## Observable promise

A decode slot must not be released for reuse while writes from its earlier owner can still land. An abort acknowledgment must carry the promised drain evidence; a timeout alone must not silently stand in for it.

Map ownership, generation, in-flight accounting, abort, acknowledgment and release actions to pinned source locations. Record where separately visible operations become separate model steps. Declare transport assumptions, finite domains, fault modes and all unobserved state.

## Five-step regression

| Step | Project input | Acceptance evidence |
|---|---|---|
| pins | Trusted manifests for specs, models, configs and expectations | Hash agreement before any counted run; a mismatch stops it |
| drift | Covered methods, all state writers and last aligned revision | Every change classified, including moved methods and new writers |
| model checks | Source-derived model variants and historical calibration jobs | Expected property and mechanism; required reachability witnesses |
| trace conformance | Pinned real traces, instrumentation and trace configs | Whole-trace completion assessed separately from safety; every mismatch triaged |
| mutation regression | Pairs of mutants and traces, with predictions | Each designated regression gives its frozen expected verdict and first divergence; survivors remain explicit gaps |

The original runner accepts a source-tree selection and a required-fix option. In a project adaptation, record the exact local command in the skill. A known-bug baseline can match all expected results while still violating safety. Require the fixed-state contract before claiming a repair.

## Code changes

Run unchanged first. Classify each covered change as no effect, model drift, intentional promise change or possible code bug. Update the model from code evidence, recalibrate, then advance the synchronized revision. Promise changes go through a rollback ticket and owner approval.

## Break/restore drill

In a source copy, remove the drain guard or disrupt lifetime accounting. Timestamp the expected result before running. Drift and source-derived model checks must expose the change; restore the source and recover the baseline. Record failed predictions too.

Frozen trace and mutation jobs check their pinned model and traces. They can stay unchanged after a live source edit, so they cannot substitute for drift and source-derived checks. A missing abort path also needs a reachability witness: fewer unsafe behaviors can mean missing functionality.

## Result boundary

Report in sync, updated, bug or blocked, with model, code and trace hashes and bounds. A blocked run never advances the aligned revision. A design-model proof is separate from evidence that the current implementation follows that model.
