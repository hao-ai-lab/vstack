# Task brief: <unit id>, specifications of the shared resources of group <group id>

<!-- Domain template: write the specification instances of one group of shared resources from the code. Generate
the brief with `python3 scripts/make_brief.py FIELDS --out BRIEF.md` and a fields file whose `template:` line names
this file. The rule for draft sentences below and the first check of the done evidence say the same thing; keep
them together when you adapt the template, so that the brief and its validator never disagree. -->

## Goal and why

The property owner wants every shared resource of the code at revision `<revision>` written down as
specifications: each one decoupled so that it involves at most three subsystems, each one true to the code. Your
group holds <resources: the resources of the group, as a computed row count over its resource table>. You write
specifications only; no models and no tests. Precision matters more than volume: a sample of your rows is read
against the code.

<context: a paragraph on what the specifications feed, or nothing>

## Inputs

- `<resources table: absolute path of the group's resource table>`: the shared resources of the group, with the
  subsystems that write, hold and read each.
- `<drafts: absolute path of the group's draft sentences>`: draft sentences from an earlier scan, unchecked; some
  are wrong, duplicated or too coupled.
- `<sites: absolute path of the group's code sites>`: where each resource is written, held or read.
- `<source tree: absolute path of the pinned source tree>`: the code at `<revision>`, read-only.
<inputs: further list items (the shared writing rules, the subsystem list, existing specifications), or nothing>

## Writable paths

- `<output dir: absolute path of this worker's own output directory>`
<writable: further list items such as a scratch directory, or nothing>

## Forbidden paths and actions

- Blind: no
- Every path outside the writable paths is read-only.
- No git commands that change state, no network, no sub-agents; never read `.env` files.
- Do not use a session scratchpad or any temporary directory outside the writable paths; keep every draft there.
- No models, no tests and no experiments in this task.
<forbidden: further list items, one per forbidden path or action with the reason, or nothing>

## What to produce

Write each output file as you go, appending rows after each resource, so that a partial result is usable.

### Method

1. Per resource, read the definition of the state and its write sites, and decide the one subsystem that manages it.
2. Write its specifications, each of exactly one kind: an invariant of the owner, an obligation of a writer (one row
   per distinct obligation, naming every writer it applies to), or an ordering rule across steps. Reuse a draft
   sentence when it is right; fix or split it when it is wrong or too coupled; add what the drafts miss.
3. Give each one an engine-neutral sentence (no class, file or function names) and the instance sentence in the
   code's own terms.
4. Cite at least one anchor per specification and, where one exists, an intent (an assertion, docstring, comment,
   test or document), quoting each line exactly. No intent found is acceptable; an invented citation is not.
5. **Every draft sentence gets exactly one destination.** It is carried into `SPECS.tsv` (named in
   `draft_sentence_ids`) or listed in `DROPPED.tsv` with its reason; a draft you did not reach goes to `DROPPED.tsv`
   with a reason that starts with `not reached:`. The first check of the done evidence enforces this.
6. A resource with no specification goes to `NO-SPEC.tsv` with its reason (`not reached` when time ran out); one
   that needs more than three subsystems goes to `OVER3.tsv`.

- `SPECS.tsv`: <specs header: the exact header of the specification table, which has a draft_sentence_ids column>.
- `CITES.tsv`: header `local_id	kind	site	quoted_code`; `kind` is `anchor` or `intent`; `site` is
  `path:line@<revision>`.
- `DROPPED.tsv`: header `sentence_id	reason	see_local_id`.
- ref: `DROPPED.tsv` column `sentence_id` -> `<drafts>` column `<draft id column: the id column of the draft sentences>`
- `NO-SPEC.tsv`: header `resource_id	reason`.
- `OVER3.tsv`: header `resource_id	what	subsystems	why_not_decomposable`.
- `NOTES.txt`: which resources were hard and why, and any input you found to be false.

## Done evidence

Run each command before handing back and fix what it reports. Save its complete output to a log in your writable
paths.

- command: `/usr/bin/awk -F'\t' 'FILENAME == ARGV[1] && FNR > 1 && NF {want[$1] = 1} FILENAME == ARGV[2] && FNR == 1 {for (i = 1; i <= NF; i++) if ($i == "draft_sentence_ids") c = i} FILENAME == ARGV[2] && FNR > 1 && c {gsub(/ /, "", $c); n = split($c, d, ";"); for (k = 1; k <= n; k++) got[d[k]] = 1} FILENAME == ARGV[3] && FNR > 1 && NF {got[$1] = 1} END {for (s in want) {t++; if (!(s in got)) m++} printf "drafts=%d without_destination=%d\n", t, m}' <drafts> <output dir>/SPECS.tsv <output dir>/DROPPED.tsv`
  last line matches: `drafts=[0-9]+ without_destination=0`
<checks: the group validator and the citation check, each a list item with command and the exact command in backticks, then an indented expected last line>

## Hand-back

End the reply with this block, one field per line. Repeat `check`, `log` and `last line` for every command of the
done evidence, in that order; repeat `version` and `written` as needed. A block that does not parse is sent back
unread.

Above the block, reply <reply: the language and length of the reply>: the counts (resources done, specifications by
kind, with and without intent evidence, dropped drafts, items over three subsystems), the last line of each check,
and the three resources you are least sure of.

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
