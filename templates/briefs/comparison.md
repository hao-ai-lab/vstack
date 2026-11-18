# Task brief: <unit id>, row-by-row comparison of two writings

<!-- Domain template: compare the two independent writings of a key unit before either is used. Generate the brief
with `python3 scripts/make_brief.py FIELDS --out BRIEF.md` and a fields file whose `template:` line names this
file. The header of the compare table is computed from templates/writing-compare.tsv, the table that
scripts/check_writings.py reads, so the brief and the checker cannot disagree on it. -->

## Goal and why

Unit `<unit id>` is a key unit: two workers wrote it independently from the same brief and the same frozen inputs.
Before either writing is used, compare them row by row, settle each contradiction from the code, and say which
writing is the better base and what to graft from the other. When few rows are the same, say so: the brief was
under-specified and both writings are redone rather than averaged.

<context: a paragraph on what the unit is and what the merged writing feeds, with the source revision, or nothing>

## Inputs

- `<writing a: absolute path of the table of writing A>`: writing A.
- `<writing b: absolute path of the table of writing B>`: writing B.
- `<source tree: absolute path of the pinned source tree>`: the code both writings describe, read-only.
- `<vstack root: absolute path of the frozen vstack copy>`: `scripts/check_writings.py` and its compare template.
<inputs: further list items (the brief both writers had, their notes), or nothing>

## Writable paths

- `<output dir: absolute path of this worker's own output directory>`
<writable: further list items such as a scratch directory, or nothing>

## Forbidden paths and actions

- Blind: no
- Every path outside the writable paths is read-only; never edit either writing.
- No git commands that change state, no network, no sub-agents; never read `.env` files.
- Do not use a session scratchpad or any temporary directory outside the writable paths; keep every draft there.
<forbidden: further list items, one per forbidden path or action with the reason, or nothing>

## What to produce

Write each output file as you go, so that a partial result is usable.

- `COMPARE.tsv`: {{header of templates/writing-compare.tsv}}. One line per pairing of a row of A with a row of B:
  `same`, `narrower` or `broader` (row A claims less or more than row B), `overlap`, or `only_here` with one side
  empty. Mark `contradiction`; for each contradiction read the code and record `who_is_right` (`a`, `b` or
  `neither`) with the site read in `note`. Every row of both writings appears at least once.
- `REPORT.txt`: the counts by relation; each contradiction in one line with its verdict; the base you would keep
  and why; the rows of the other writing to graft.

## Done evidence

Run each command before handing back and fix what it reports. Save its complete output to a log in your writable
paths.

- command: `python3 <vstack root>/scripts/check_writings.py <output dir>/COMPARE.tsv --a <writing a> --b <writing b> --id-column <id column: the column that identifies a row in both writings>`
  last line matches: `OK writings: .+`
<checks: further checks, each a list item with command and the exact command in backticks, then an indented expected last line, or nothing>

## Hand-back

End the reply with this block, one field per line. Repeat `check`, `log` and `last line` for every command of the
done evidence, in that order; repeat `version` and `written` as needed. A block that does not parse is sent back
unread.

Above the block, reply <reply: the language and length of the reply>: the counts by relation, the contradictions
with their verdicts, and the base you would keep.

```text
BEGIN HANDBACK
verdict: PASS, ISSUES or BLOCKED
check: the exact command, as written under Done evidence
log: absolute path of the file holding that command's complete output
last line: the last line of that log, copied exactly
version: each tool, input and source revision used, with its version or hash
written: each file written, as an absolute path
rules broken: none, or one line per rule broken
END HANDBACK
```
