# live-regression

Use the project-local `verify-<case>` produced by [S8 (package and maintain regression)](../../vstack-s8-package-maintain/SKILL.md), not a new uncalibrated checker.

1. Read its property, source coverage, synchronized revision, limits and expected outputs. If the project has no such skill, return to S8 with its prerequisite artifacts; report the missing regression rather than claiming a pass.
2. Run its pinned command unchanged: pins → drift → model checks → trace regression → mutation regression. Use its fixed-state option when claiming a repair, rather than merely reproducing a known-bug baseline.
3. Read every failure, missing observation and incomplete row. Inspect all source changes since the sync revision, including renamed/moved functions and new state writers.
4. Classify no effect, model drift, intentional promise change or possible code defect. Update from code evidence, never from a desired verdict. Route to S3 (build an anchored model)/S4 (calibrate and align traces), S2 (freeze specifications and contracts) or S6 (find and repair bugs) respectively.
5. After a change, repeat the break/restore drill and independent rerun. Report in sync, updated, bug or blocked. A blocked check cannot advance the synchronized revision.

See [the PD example](../../../examples/verify-pd-kv-slot/SKILL.md) for the five-step shape and known-baseline versus repaired-state distinction.
