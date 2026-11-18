# Task brief: <unit id>, triage of check failures that no known row explains

<!-- Domain template: judge, one by one, the failures of checks derived from specification sentences. Generate the
brief with `python3 scripts/make_brief.py FIELDS --out BRIEF.md` and a fields file whose `template:` line names this
file. Give the number of failures as a computed count over the violation tables, so that it is recounted with each
file's own header skipped. -->

## Goal and why

Checks derived from specification sentences failed at places that no row of the known table explains. A failing
check means "the check fails here", not a defect. Judge each of the <failures: the failures to judge, as a computed row count over the violation tables> from the code: a defect of the code under check, a defect of the
sentence (it asks more than the code or its documentation promises), an artefact of the check, or unclear; how it
is reached; what it breaks; and whether it has the same root as a row of the known table. A wrong defect verdict
costs more than an honest unclear one.

<context: a paragraph on where the failures come from and what the verdicts feed, with the source revision, or nothing>

## Inputs

<violation tables: one list item per violation table with the check it comes from>
- `<known table: absolute path of the table of known defects and leads>`: the known rows, for the same-root question.
- `<source tree: absolute path of the pinned source tree>`: the code under check, read-only.
<inputs: further list items (the checks' folders and reports, the specification table, earlier verdicts as a model), or nothing>

## Writable paths

- `<output dir: absolute path of this worker's own output directory>`
<writable: further list items such as a scratch directory, or nothing>

## Forbidden paths and actions

- Blind: no
- Every path outside the writable paths is read-only.
- No git commands that change state, no network, no sub-agents; never read `.env` files.
- Do not use a session scratchpad or any temporary directory outside the writable paths; keep every draft there.
- To look at a failure again, copy its check into your writable path first and run the copy; no finding records.
<forbidden: further list items, one per forbidden path or action with the reason, or nothing>

## What to produce

Write each output file as you go, so that a partial result is usable.

- `TRIAGE.tsv`: header `violation	verdict	root	same_as	reach	impact	evidence	note`, one row per judged failure.
  `verdict` is `code_defect`, `sentence_defect`, `check_artefact` or `unclear`; `root` names the cause, the same
  name on every row with that cause; `same_as` is one id of the known table, or `none`; `reach` is
  `default settings`, the options needed, or `unknown`; `evidence` lists the sites read as `path:line@revision`.
- ref: `TRIAGE.tsv` column `same_as` -> `<known table>` column `<known id column: the id column of the known table>`
- `REPORT.txt`: per root, two or three lines (what happens, why the verdict, what would settle an unclear one); the
  number of failures judged and skipped, with the reason for each skip.

## Done evidence

Run each command before handing back and fix what it reports. Save its complete output to a log in your writable
paths.

- command: `/usr/bin/awk -F'\t' 'FNR == 1 {next} NF {n++; if ($2 !~ /^(code_defect|sentence_defect|check_artefact|unclear)$/) bad++} END {printf "judged=%d bad_verdicts=%d\n", n, bad}' <output dir>/TRIAGE.tsv`
  last line matches: `judged=[1-9][0-9]* bad_verdicts=0`
<checks: further checks, each a list item with command and the exact command in backticks, then an indented expected last line, or nothing>

## Hand-back

End the reply with this block, one field per line. Repeat `check`, `log` and `last line` for every command of the
done evidence, in that order; repeat `version` and `written` as needed. A block that does not parse is sent back
unread.

Above the block, reply <reply: the language and length of the reply>: the verdicts by kind, the roots, which
failures reach other requests or the service as a whole, and which match a known row.

<!-- The coordinator checks the reply with `python3 scripts/parse_handback.py REPLY.txt --brief BRIEF.md`, which
also refuses a `same_as` id that is not in the known table. -->

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
