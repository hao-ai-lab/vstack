#!/usr/bin/env bash
# Read-only lexical audit. TSV: model_dir<TAB>module<TAB>cfg.
# Exactly one ASSUMES header in the first 10 lines; definitions at column zero;
# EXTENDS is followed in the same directory. See docs/gates.md for syntax limits.
set -uo pipefail
G=/usr/bin/grep
usage() { echo 'Usage: assumptions_check.sh MANIFEST | --expect DIR EXPECT_TSV KIND MODULE [CFGDIR]' >&2; exit 2; }
pairs=()
if [[ ${1:-} == --expect ]]; then
  (( $# >= 5 )) || usage
  d=$2 ex=$3 kind=$4 mod=$5 cd=${6:-.}
  [[ -f $ex ]] || { echo "assumptions: no such expect file $ex"; exit 2; }
  while IFS=$'\t' read -r n k _; do
    [[ -z $n || $n == \#* ]] && continue
    [[ $k == "$kind" ]] && pairs+=("$d"$'\t'"$mod"$'\t'"$cd/$n.cfg")
  done < "$ex"
elif [[ -n ${1:-} && -f ${1:-} ]]; then
  while IFS= read -r l; do [[ -z $l || $l == \#* ]] && continue; pairs+=("$l"); done < "$1"
else usage; fi
(( ${#pairs[@]} > 0 )) || { echo "assumptions: FAIL (nothing to check: empty manifest)"; exit 1; }

# defined DIR MODULE NAME [seen]: NAME defined at column 0 in MODULE.tla or in a module it EXTENDS (same dir)
defined() {
  local d=$1 m=$2 n=$3 seen=${4:-} e
  [[ " $seen " == *" $m "* ]] && return 1
  [[ -f $d/$m.tla ]] || return 1
  $G -qE "^$n(\(.*\))? ==" "$d/$m.tla" && return 0
  for e in $(sed -n 's/^EXTENDS //p' "$d/$m.tla" | tr ',' ' '); do
    defined "$d" "$e" "$n" "$seen $m" && return 0
  done
  return 1
}
# assumes DIR MODULE -> prints the names (space separated), "(none)" -> nothing; returns 1 with a reason on stderr if bad
assumes() {
  local f=$1/$2.tla h n bad=0
  [[ -f $f ]] || { echo "module file missing: $f" >&2; return 1; }
  h=$(head -10 "$f" | $G -c '^\\\* ASSUMES:')
  [[ $h == 1 ]] || { echo "$h ASSUMES header lines in the first 10 lines of $2.tla (want exactly 1)" >&2; return 1; }
  h=$(head -10 "$f" | sed -n 's/^\\\* ASSUMES: *//p')
  [[ $h == "(none)" ]] && return 0
  [[ $h =~ ^[A-Za-z_][A-Za-z0-9_]*(,\ *[A-Za-z_][A-Za-z0-9_]*)*$ ]] || { echo "malformed ASSUMES header in $2.tla: '$h'" >&2; return 1; }
  for n in $(tr ',' ' ' <<< "$h"); do
    defined "$1" "$2" "$n" || { echo "ASSUMES name $n is not defined in $2 or the modules it EXTENDS" >&2; bad=1; }
  done
  (( bad == 0 )) || return 1
  tr ',' ' ' <<< "$h"
}
# checked CFG -> the names listed under INVARIANT(S) / PROPERTY / PROPERTIES (comments stripped, continuation lines kept)
checked() {
  awk 'BEGIN { kw["SPECIFICATION"]; kw["INIT"]; kw["NEXT"]; kw["CONSTANT"]; kw["CONSTANTS"]; kw["INVARIANT"]; kw["INVARIANTS"];
               kw["PROPERTY"]; kw["PROPERTIES"]; kw["SYMMETRY"]; kw["VIEW"]; kw["CHECK_DEADLOCK"]; kw["CONSTRAINT"];
               kw["CONSTRAINTS"]; kw["ACTION_CONSTRAINT"]; kw["ACTION_CONSTRAINTS"]; kw["POSTCONDITION"]; kw["ALIAS"]; sec = "" }
       { line = $0
         # Existing multiline-comment handling: inside a block comment that spans lines, skip text up to its closing "*)"
         if (incom) { if (match(line, /\*\)/)) { line = substr(line, RSTART + 2); incom = 0 } else next }
         sub(/\\\*.*/, "", line)
         while (match(line, /\(\*/)) { pre = substr(line, 1, RSTART - 1); rest = substr(line, RSTART + 2)
           if (match(rest, /\*\)/)) line = pre " " substr(rest, RSTART + 2); else { line = pre; incom = 1 } }
         n = split(line, t, /[ \t]+/)
         for (i = 1; i <= n; i++) { if (t[i] == "") continue
           if (t[i] in kw) { sec = t[i]; continue }
           if (sec ~ /^(INVARIANTS?|PROPERTY|PROPERTIES)$/) print t[i] } }' "$1"
}
n=0 fails=0
for p in "${pairs[@]}"; do
  IFS=$'\t' read -r d m c <<< "$p"
  [[ $c == /* ]] || c=$d/$c
  n=$((n + 1))
  err=$(assumes "$d" "$m" 2>&1 >/dev/null); names=$(assumes "$d" "$m" 2>/dev/null)
  if [[ -n $err ]]; then echo "FAIL  $m  $(basename "$c")  : $err"; fails=$((fails + 1)); continue; fi
  [[ -f $c ]] || { echo "FAIL  $m  $(basename "$c")  : cfg missing"; fails=$((fails + 1)); continue; }
  have=" $(checked "$c" | tr '\n' ' ') " miss=""
  for x in $names; do [[ $have == *" $x "* ]] || miss="$miss $x"; done
  if [[ -n $miss ]]; then echo "FAIL  $m  $(basename "$c")  : not checked:$miss"; fails=$((fails + 1))
  else echo "ok    $m  $(basename "$c")  : assumes {${names:-none}}"; fi
done
if (( fails == 0 )); then echo "assumptions: OK $n pairs"; exit 0; else echo "assumptions: FAIL $fails of $n"; exit 1; fi
