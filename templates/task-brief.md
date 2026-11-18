# Task brief: <unit id>, <title: one line>

<!-- Do not fill this file by hand and never derive a brief from another brief. Write a fields file with one
`name: value` line per slot (or `name:` followed by an indented block), then run
`python3 scripts/make_brief.py FIELDS --out BRIEF.md`: it fills every slot, computes the counts and headers it is
asked for, refuses a field that fills no slot, checks the result with `scripts/check_brief.py` and stamps it.
Domain templates with the same seven sections are in templates/briefs/. Comments like this one are ignored by the
checker and may stay. A brief stands alone: the worker sees this file and the inputs it names, nothing else. -->

## Goal and why

<goal: what the user asked or decided, in one paragraph, and why the result matters; name the unit and its source revision>

## Inputs

<!-- Absolute paths; everything listed here is read-only for the worker. Paste upstream conclusions the unit
depends on in full rather than pointing at another worker's folder. A row count is written as
`N rows of `FILE`` (several files joined by `and`, optionally `where `COLUMN=VALUE``) so that the checker recounts
it, each file's own header skipped; the generator computes it from a `{{rows of FILE ...}}` field. An id family is
declared with `ids: `REGEX` from `FILE` column `NAME`` or `ids: `REGEX` only `ID`, `ID``; every match in the brief
must then be one of those ids. -->

<inputs: one list item per input, an absolute path in backticks, a colon and what it is>

## Writable paths

<!-- Absolute paths only: the worker's own output directory, plus a scratch directory if it needs one. Workers of
one batch never share a writable path. In a tree that several workers change, list the files or globs (`*`, `**`)
this worker owns, and `except` items for files it must leave alone; `scripts/parse_handback.py --changed` refuses a
change outside them. -->

<writable: one list item per absolute path or glob, the worker's own output directory first>

## Forbidden paths and actions

<!-- Keep the line `Blind: yes` or `Blind: no`. With `Blind: yes`, list as items every absolute path the worker
must not open (other workers' folders, answer keys, earlier findings); the worker reports any accidental opening
under `rules broken`. No blind path may contain a path that another section gives the worker. -->

- Blind: <blind: yes or no>
- Every path outside the writable paths is read-only.
- No git commands that change state, no network, no sub-agents; never read `.env` files.
- Do not use a session scratchpad or any temporary directory outside the writable paths; keep every draft there.
<forbidden: further list items, one per forbidden path or action with the reason; with Blind yes, one per absolute path the worker must not open>

## What to produce

Write each output file as you go, so that a partial result is usable.

<outputs: one list item per output file with its format; for a table, its exact header line or a header computed from the template it follows>

<!-- Finding records follow templates/finding-record.tsv. Leave the tier, grade and route to the grader. A text
that looks like a placeholder but must stay (a marker the worker keeps) is declared with `literal: `TEXT``. An output
column that names ids of another table is declared with `ref: `OUTPUT` column `NAME` -> `TABLE` column `NAME``;
the hand-back check refuses an id that is not in that table. -->

## Done evidence

<!-- One `command:` per check and, on the next line, `last line:` (exact), `last line ends with:` (suffix) or
`last line matches:` (a regular expression the whole last line must match, for a line that carries counts). An
exact or suffix line never ends with `=` or `:`. The coordinator re-runs these commands at acceptance. When the
outputs include finding records, one check must be the grader on each record file, for example
- command: `python3 scripts/grade_findings.py /srv/out/U-01/findings.tsv`
  last line ends with: `findings checked`
check_brief.py refuses a brief that produces finding records without it. -->

Run each command before handing back and fix what it reports. Save its complete output to a log in your writable
paths. Every finding record you write must pass `python3 scripts/grade_findings.py` on its file; never fill in a
tier, grade or route by hand.

<checks: for each check, a list item with command and the exact command in backticks, then an indented line with its expected last line>

## Hand-back

End the reply with this block, one field per line. Repeat `check`, `log` and `last line` for every command of the
done evidence, in that order; repeat `version` and `written` as needed. A block that does not parse is sent back
unread.

<reply: what the reply says above the block, or nothing>

<!-- The coordinator checks the reply with `python3 scripts/parse_handback.py REPLY.txt --brief BRIEF.md`. -->

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
