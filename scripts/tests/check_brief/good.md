# Task brief: U-01, writers of the buffer slot table

<!-- Example brief for the checker's self-test. This comment holds a <placeholder> that the checker ignores. -->

## Goal and why

The property owner wants every writer of the buffer slot table listed with its guard, so that the model of unit
U-01 starts from a complete census. Source revision `abc1234`. See <https://example.com/guide> for the method.

## Inputs

- `/srv/verify/inputs/U-01/resources.tsv`: the shared resource and its subsystems.
- `/srv/verify/source`: the pinned source tree.

## Writable paths

- `/srv/verify/out/U-01/`
- /srv/verify/scratch/U-01: scratch space

## Forbidden paths and actions

- Blind: no
- Every path outside the writable paths is read-only.
- No git commands that change state, no network, no sub-agents; never read `.env` files.

## What to produce

Write each output file as you go, so that a partial result is usable.<br>

- `WRITERS.tsv`: header `writer	site	guard	note`.

### Format notes

One row per write site.

## Done evidence

Run each command before handing back.

- command: `python3 /srv/verify/tools/check_writers.py /srv/verify/out/U-01/WRITERS.tsv`
  last line: `OK writers: 0 errors`
1. command: bash /srv/verify/tools/cites.sh /srv/verify/out/U-01
   last line ends with: `errors=0`

## Hand-back

End the reply with this block.

```text
BEGIN HANDBACK
verdict: PASS, ISSUES or BLOCKED
check: the exact command
log: absolute path of its log
last line: the last line of that log
version: each tool and input with its version
written: each file written
rules broken: none, or each rule broken
END HANDBACK
```
