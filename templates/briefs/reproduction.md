# Task brief: <unit id>, reproduction of lead <lead id> on real code

<!-- Domain template: reproduce one lead from code reading on the real code, with a control and a graded finding
record. Generate the brief with `python3 scripts/make_brief.py FIELDS --out BRIEF.md` and a fields file whose
`template:` line names this file; copy the lead with a `{{cell of TABLE column NAME where ID=VALUE}}` field. Name
a frozen copy of vstack as the vstack root, so that the grader and the record template cannot change mid-batch. -->

## Goal and why

A reviewer read the code at revision `<revision>` and concluded that the sequence of lead `<lead id>` reaches a bad
state. Reading alone passes none of the gates. Find out by running the real code whether it happens: a test that
reaches the bad state every time, with a control that does not, or a clear account of why it cannot be reached,
which refutes the lead and is an equally good result. A claim that turns out wrong is the worst outcome: never bend
the test to make it fail, never stub away a guard, and say exactly what is real and what is replaced.

<context: a paragraph on why this lead is reproduced now and who reads the result, or nothing>

The lead, as written in `<leads table: absolute path of the table of leads>`:

> <lead: the lead's claim and sequence, copied by the generator from the table>

- ids: `<id pattern: a regular expression matching lead ids>` only `<lead id>`

## Inputs

- `<leads table>`: the lead's row; read that row only.
- `<source tree: absolute path of the pinned source tree>`: the code at `<revision>`, read-only.
- `<vstack root: absolute path of the frozen vstack copy>`: the record template `templates/finding-record.tsv`, the
  grader `scripts/grade_findings.py` and the gate documents under `docs/`.
<inputs: further list items (a harness that drives the real code, the lead's citations), or nothing>

## Writable paths

- `<output dir: absolute path of this worker's own output directory>`
<writable: further list items such as a scratch directory, or nothing>

## Forbidden paths and actions

- Blind: no
- Every path outside the writable paths is read-only; never write into the source tree.
- No git commands that change state, no network, no sub-agents; never read `.env` files.
- Do not use a session scratchpad or any temporary directory outside the writable paths; keep every draft there.
- Never edit the code under check; patch it at run time only inside the test, each patch listed in the report.
- If the sequence cannot be driven without replacing the very component the lead is about, stop and report
  `NOT REPRODUCED` with what it needs; never fake it.
<forbidden: further list items, one per forbidden path or action with the reason, or nothing>

## What to produce

Write each output file as you go, so that a partial result is usable.

- `test_lead.py` and the helpers it needs: drives the real code through the lead's sequence and checks the bad state
  with an explicit assertion on real state, not on a log line; prints `RESULT arm=NAME runs=N hits=N` for each arm
  and exits 0 when the run completed. Arms: `stock`, the sequence on unmodified code; `control`, the same sequence
  with the one decisive condition removed, which must show 0 hits or the check is vacuous; and, only when stock
  hits, `patched`, the smallest change that should close the gap, applied inside the test, which must show 0 hits.
- `RUNS.tsv`: header `arm	command	exit	runs	hits	log`, every run reported, with its log under `logs/`.
- `FINDING.tsv`: one finding record in the columns of `<vstack root>/templates/finding-record.tsv`, its header line
  copied exactly; `injected` names every stand-in of the test or says `none`; `review_verdict` is `pending`; leave
  `tier`, `grade` and `route` empty for the grader.
- `REPORT.txt`: the verdict in the first line (`REPRODUCED`, `NOT REPRODUCED`, or `REFUTED` with the guard as
  `path:line@<revision>`); what is real and what is replaced, with why each stand-in does not affect the path; the
  exact sequence; hits and runs per arm; what the test does not show.

## Done evidence

Run each command before handing back and fix what it reports. Save its complete output to a log in your writable
paths. Every finding record you write must pass `python3 scripts/grade_findings.py` on its file; never fill in a
tier, grade or route by hand.

- command: `python3 <vstack root>/scripts/grade_findings.py <output dir>/FINDING.tsv`
  last line ends with: `findings checked`
- command: `/usr/bin/awk -F'\t' 'FNR == 1 {next} NF {n++; if ($1 == "control" && $5 != 0) bad++} END {printf "runs=%d control_hits=%d\n", n, bad}' <output dir>/RUNS.tsv`
  last line matches: `runs=[1-9][0-9]* control_hits=0`
<checks: further checks, each a list item with command and the exact command in backticks, then an indented expected last line, or nothing>

## Hand-back

End the reply with this block, one field per line. Repeat `check`, `log` and `last line` for every command of the
done evidence, in that order; repeat `version` and `written` as needed. A block that does not parse is sent back
unread.

Above the block, reply <reply: the language and length of the reply>: the verdict line, hits and runs per arm, the
list of stand-ins and run-time patches, and what the test does not show.

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
