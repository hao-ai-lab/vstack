---
name: vstack-s0-decompose
description: "Map a pinned system into control, data and boundary views and build evidence-backed historical anchors before verification."
---

# S0 — Reconstruct and separate the system

Read [Layer 0: shared operating rules](../../docs/layer-0.md), this stage and the assigned input bundle.

## Role and write scope

Assigned investigators own separate maps and candidate files; a verifier and coordinator check evidence. Target source is read-only.

## 1. Input

A fixed source revision, existing anchors for deduplication, and existing maps and catalogues when available. Project-specific catalogues stay in the project.

## 2. Procedure

1. Build a control map of mutable state, owners and **all** writers. Label every in-scope subsystem `control`, `data` or `both`, stating each slice for `both`; use the [plane definitions](../../docs/method-selection.md#units-planes-and-edges). Write the subsystem list as an ownership table of rules by path, class and function, the most specific rule winning, and check before any census that it partitions the in-scope code: every file, and every class or function of a file that subsystems split, maps to exactly one subsystem or is marked shared with the sharing subsystems named. Settle overlaps in this table, so that two censuses attribute one site to the same subsystem.
2. Fill the [resource matrix](../../templates/resource-matrix.tsv): one row per shared mutable resource and subsystem that touches it, with code sites and the feature or switch conditions. Set `access` to `write` (changes it), `hold` (keeps it so others must not change or free it) or `read`. The matrix is the main table of the census; units are derived from it resource by resource in S1. Attribute sites by these rules:
   - The subsystem whose own code performs the write owns the site, by the ownership table. A subsystem that only calls another subsystem's method is a caller, not a writer, and gets no `write` row for that call. Exception: when the obligation is about what every holder must do, such as returning what it took exactly once, list every holder with `access = hold`.
   - Count a constructor write by the lifetime of the object it initialises. It is shared state only when the object is not created for one request or one call, lives across requests or steps (a server-wide pool, cache, scheduler or backend, or a batch object reused from step to step), and another party later reads or writes the field. A constructor of a per-request or per-call object (a request's output parser or stop detector, a per-forward metadata builder) is not shared state; later writes to such an object by another party are ordinary write sites. Record the lifetime (`service`, `request` or `call`) of every constructor site you classify.
   - Search all assignments before saying a field has one writer: search each field and method by its bare name (`.slots =`, `free(`), not only a qualified form, across the whole package rather than the files read for a property.

   For Python sources, use [check_anchors.py](../../scripts/check_anchors.py) with the [anchor table](../../templates/anchors.tsv) and review its coverage limits.
3. Map data and computation consumers and their unchecked preconditions. At each boundary, map the producer, consumer, execution context, overwrite time and synchronization. Classify every in-scope file. Classify each boundary as a [state or parameter edge](../../docs/method-selection.md#units-planes-and-edges), recording the criterion and any value range used.
4. Run the writer census as a task of its own: a census worker does not also write property clauses or unit rows in that task. Have two workers independently perform each resource's writer census and boundary classification without seeing each other's output. The coordinator lists and settles every difference, classifying each as a missed shared write, not shared state, or one site attributed to different subsystems (settled by the ownership table); a count of extra sites in one census is not a count of missed writers. Retain both censuses and the settlement record. Every later correction of a census row (by the settlement, a second pass or a review) goes into a [census-correction record](../../docs/gates.md#census-corrections) (`scripts/check_census_fixes.py --template`): who, which row, the wrong and the right value, its kind and `path:line` evidence; then apply it to the table.
5. Record facts with `path:line@commit` and short source excerpts. Keep unsupported inferences explicitly unverified.
6. Search the target and related systems by component. Record every examined candidate, rejection reason and search coverage. Confirm buggy triggers and fixed behavior on the stated revisions; a closed issue is not evidence that a fix merged.
7. Test critical physical and synchronization assumptions on the real system before treating them as axioms, using authorized resources.
8. For the full [adequacy readout](../../docs/model-adequacy.md#denominator-i_u), freeze each slice's historical-fix denominator `I_U` with its exclusion reason codes and SHA-256. The coordinator then draws the calibration set by a published seed and seals the blind set `H`, removing every trace of `H` from the maps handed downstream.

## 3. Exit checks

- Require zero evidence schema errors and a positive checked-item count. The source KB checker is repository-specific and is not bundled.
- Have the verifier and coordinator review original source and bind review marks to its content. This review is manual.
- Classify every file, label unsupported claims and deduplicate upstream identifiers. These checks have no generic automation.
- Documented-only: review every subsystem's plane slices, the ownership table's partition, resource accesses and conditions, constructor lifetimes, boundary kind and criterion, and the two independent censuses with all differences settled and classified. No generic completeness or partition checker is bundled.
- Partly manual: run `check_anchors.py` for Python sources and review the resource matrix against source; its scan does not establish a complete writer census or correct edge classification.
- Mechanical: `scripts/check_census_fixes.py FIXES.tsv --table NAME=MATRIX --source SOURCE` refuses a correction without its evidence or one the table does not hold yet; `scripts/check_names.py SOURCE MATRIX --column ...` refuses a row naming a class, function or field absent from the pinned source ([name check](../../docs/gates.md#name-check)).
- Keep disproved anchors. Rename an unsupported historical `Bug*` switch to `Mut*`; do not count it as historical calibration.

## 4. Rollback

An invalid physical assumption reopens the boundary map. A downstream report of a missing state writer returns here with the pinned source location. Use [a rollback ticket](../../templates/rollback.md).

## Concrete Examples

For a PD KV slot, map every writer of ownership and in-flight state, then record the producer-to-consumer handoff. An unsupported historical-bug claim stays a mutation hypothesis until pinned code supports it.
