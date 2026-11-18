# Task brief: <unit id>, a check derived from specification <spec id>

<!-- Domain template: one specification sentence turned into a check on real code, run blind. Generate the brief
with `python3 scripts/make_brief.py FIELDS --out BRIEF.md` and a fields file whose `template:` line names this
file. The method is fixed and comes from the sentence alone: the coordinator fills ids and paths, never the places
to look at or the failures to expect, so an answer key the coordinator has seen cannot leak into the brief. Copy
the sentence with a `{{cell of TABLE column NAME where ID=VALUE}}` field rather than typing it. -->

## Goal and why

The property owner wants to know whether a specification, turned into a check on the real code, finds violations
by itself. Derive a check from the sentence of specification `<spec id>` and from the structure of the code, run it
on the real code of `<source tree: absolute path of the pinned source tree>` at revision `<revision>`, and report
every place where it fails and every place where it passes. The failures are compared with known defects later, by
someone else; that comparison means something only if you work blind.

<context: a paragraph on why this specification is checked now, or nothing>

The specification, as written in `<spec table: absolute path of the specification table>`:

> <sentence: the specification sentence, copied by the generator from the table>

- ids: `<id pattern: a regular expression matching ids of the specification table>` only `<spec id>`

## Inputs

- `<spec table>`: the specification table; read the row of `<spec id>` and its instance rows only.
- `<source tree>`: the code under check with its tests and documentation, allowed in full.
<inputs: further list items, one per input such as the harness that drives the real code, or nothing>

## Writable paths

- `<output dir: absolute path of this worker's own output directory>`
<writable: further list items such as a scratch directory, or nothing>

## Forbidden paths and actions

- Blind: yes
- Every path outside the writable paths is read-only; never write into the source tree.
- No git commands that change state, no network, no sub-agents; never read `.env` files.
- Do not use a session scratchpad or any temporary directory outside the writable paths; keep every draft there.
- Never edit the code under check; a check may patch at run time only to observe, and says so in the report.
<blind paths: one list item per absolute path the worker must not open (known-defect tables, earlier findings, other workers' folders), each with the reason>

## What to produce

Write each output file as you go, so that a partial result is usable.

### Method

1. **Dimensions from the sentence.** Before looking for places, list in `DIMENSIONS.tsv` every input dimension the
   sentence quantifies over or implies (kinds of resource, entry points, configurations, states, orders of actions,
   concurrency) with the values you will vary. A check that never varies the failing dimension passes vacuously.
2. **Places from the code.** Enumerate every place in the code that holds the kind of resource the sentence names,
   not only the instances in the table (the table is incomplete), and write them to `PLACES.tsv` before checking.
3. **A control for each failure.** Drive the real code. Every failure needs a control that passes with the one
   difference removed, so that a failure cannot be an artefact of the harness. Use a second oracle where one exists:
   an assertion of the code, a documented promise, a second implementation.
4. **A refusal is a failure.** A documented operation that is refused, or that reports success without having done
   its work, fails the check; it is not a safe outcome.
5. **Denominators.** Count the places found, checked, failed, passed and not applicable, each with its reason.

A failure of the check is not a defect verdict. Write it as "the check of `<spec id>` fails here", with what a
client or operator must do to reach it (default settings, or which options), as far as the code tells.

- `DIMENSIONS.tsv`: header `dimension	values	why_from_sentence`.
- `PLACES.tsv`: header `place	site	what_it_is	checked	result	note`; `site` is `path:line@<revision>`, `checked` is
  `yes` or `no: reason`, `result` is `pass`, `fail` or `not run`.
- `VIOLATIONS.tsv`: header `id	place	site	what_differs	expected	observed	control	reach	command	log`, with ids
  `<spec id>-V01`, `<spec id>-V02` and so on; `reach` is `default settings`, the options needed, or `unknown`.
- `RUNS.tsv`: header `arm	command	exit	cases	failures	log`, one row per run, with its log under `logs/`.
- The check scripts, runnable arm by arm, and `REPORT.txt`: how the check came from the sentence, the counts, each
  failure in two or three lines, what the check cannot see, and whether you opened a forbidden path.

## Done evidence

Run each command before handing back and fix what it reports. Save its complete output to a log in your writable
paths.

- command: `/usr/bin/awk -F'\t' 'FNR == 1 {next} NF {n++; if ($4 == "yes") c++; if ($5 == "fail") f++} END {printf "places=%d checked=%d failed=%d\n", n, c, f}' <output dir>/PLACES.tsv`
  last line matches: `places=[1-9][0-9]* checked=[0-9]+ failed=[0-9]+`
<checks: further checks, each a list item with command and the exact command in backticks, then an indented expected last line, or nothing>

## Hand-back

End the reply with this block, one field per line. Repeat `check`, `log` and `last line` for every command of the
done evidence, in that order; repeat `version` and `written` as needed. A block that does not parse is sent back
unread.

Above the block, reply <reply: the language and length of the reply>: the counts (places found, checked, failed,
passed, not applicable), each failure in one line with its reach, what the check cannot see, and whether a
forbidden path was opened.

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
