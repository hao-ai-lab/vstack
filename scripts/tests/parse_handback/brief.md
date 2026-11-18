# Task brief: U-01, writers of the buffer slot table

## Goal and why

List every writer of the buffer slot table with its guard, so that the model of unit U-01 starts from a complete
census of source revision `abc1234`.

## Inputs

- `/opt/verify/inputs/U-01/resources.tsv`: the shared resource and its subsystems.

## Writable paths

- `{tmp}/out/`

## Forbidden paths and actions

- Blind: no
- Every path outside the writable paths is read-only.

## What to produce

Write each output file as you go, so that a partial result is usable.

- `WRITERS.tsv`: one row per write site.

## Done evidence

- command: `python3 /opt/verify/tools/check_writers.py {tmp}/out/WRITERS.tsv`
  last line: `OK writers: 0 errors`
- command: `bash /opt/verify/tools/cites.sh {tmp}/out`
  last line ends with: `errors=0`

## Hand-back

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
