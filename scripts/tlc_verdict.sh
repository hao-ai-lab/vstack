#!/usr/bin/env bash
# LEGACY CLASSIFIER ONLY: source this file and call tlc_verdict LOG RC.
# It prints a label; its shell exit status is NOT the verification verdict.
# No empty-state or coverage check; not a complete fail-closed acceptance gate. See docs/gates.md.
G=/usr/bin/grep
tlc_verdict() {  # tlc_verdict LOG RC -> PASS | VIOLATION:<name> | VIOLATION:temporal | VIOLATION:deadlock | TIMEOUT | ERROR:...
  local log=$1 rc=$2 x
  # Violation takes precedence over a later success line from TLC -continue.
  if x=$($G -m1 -oE '^Error: Invariant [A-Za-z_0-9]+ is violated' "$log"); then echo "VIOLATION:$(echo "$x" | cut -d' ' -f3)"
  elif x=$($G -m1 -oE '^Error: Action property [A-Za-z_0-9]+ is violated' "$log"); then echo "VIOLATION:$(echo "$x" | cut -d' ' -f4)"
  elif $G -q '^Error: Temporal properties were violated' "$log"; then echo VIOLATION:temporal
  elif $G -q '^Error: Deadlock reached' "$log"; then echo VIOLATION:deadlock
  elif (( rc == 124 )); then echo TIMEOUT
  elif $G -q 'Model checking completed. No error has been found.' "$log"; then echo PASS
  else echo "ERROR:$($G -m1 '^Error:' "$log" | cut -c1-60 | tr '\t' ' ')rc=$rc"
  fi
}
tlc_states() { $G -oE '[0-9,]+ distinct states found' "$1" | tail -1 | tr -d ',' | cut -d' ' -f1; }
