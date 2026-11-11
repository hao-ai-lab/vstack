#!/usr/bin/env bash
# Compare coordinator-owned pins; never regenerates them.
# Usage: check_spec_pins.sh ROOT PINS (PINS relative to ROOT, or absolute).
set -uo pipefail
if (( $# != 2 )); then echo 'Usage: check_spec_pins.sh ROOT PINS' >&2; exit 2; fi
cd "$1" || exit 1
pins=$2
if sha256sum --check --strict --quiet "$pins"; then
  echo "spec pins OK ($(wc -l < "$pins") files)"
else
  echo 'SPEC PIN MISMATCH: run invalid; coordinator review and authorized re-pinning required' >&2
  exit 1
fi
