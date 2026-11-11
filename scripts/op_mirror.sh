#!/usr/bin/env bash
# Lexical comparison for the record-update dialect in docs/gates.md; not arbitrary TLA+.
# Supply OP_MIRROR_HEADER; optionally OP_MIRROR_NORMALIZE (sed file), OP_MIRROR_ACTIONS.
set -uo pipefail
here=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
A=$here/op_mirror.awk
pr=0; [[ ${1:-} == --print ]] && { pr=1; shift; }
ideal=${1:-} rf=${2:-} wl=${3:-}
[[ -f $ideal && -f $rf ]] && { (( pr )) || [[ -f $wl ]]; } || { echo 'Usage: op_mirror.sh IDEAL.tla REFINE.tla WHITELIST.tsv | --print IDEAL.tla REFINE.tla' >&2; exit 2; }
norm() { if [[ -n ${OP_MIRROR_NORMALIZE:-} ]]; then sed -f "$OP_MIRROR_NORMALIZE"; else cat; fi; }
sha() { sha256sum | cut -c1-16; }
ideal_definition() { local a out=""; for a in $(tr ',' ' ' <<< "$1"); do out="$out$a:$(MODE=def NAME=$a awk -f "$A" "$ideal")|"; done; printf '%s' "$out"; }
: "${OP_MIRROR_HEADER:?Set the exact Op definition header; see docs/gates.md}"
export OP_MIRROR_HEADER
[[ -z ${OP_MIRROR_NORMALIZE:-} || -f $OP_MIRROR_NORMALIZE ]] || { echo "normalization file missing" >&2; exit 2; }
mapfile -t BR < <(MODE=branches awk -f "$A" "$rf")
(( ${#BR[@]} > 0 )) || { echo "op mirror: FAIL (no Op branches found in $rf)"; exit 1; }
fails=0
for l in "${BR[@]}"; do
  b=${l%%$'\t'*} t=${l#*$'\t'}
  [[ $b == UNPARSED ]] && { echo "FAIL  unparsed branch text: ${t:0:80}"; fails=$((fails + 1)); continue; }
  if (( pr )); then printf '%s\t%s\n' "$b" "$(printf '%s' "$t" | sha)"; continue; fi
  row=$(awk -F'\t' -v b="$b" '$2 == b && $1 !~ /^#/' "$wl")
  [[ -n $row ]] || { echo "FAIL  $b: neither verbatim nor whitelisted"; fails=$((fails + 1)); continue; }
  IFS=$'\t' read -r kind _ acts bsha vsha why <<< "$row"
  if [[ $kind == VERBATIM ]]; then
    # A branch may call a helper on the state record; compare its body.
    body=$t
    hre='^([A-Za-z]+)\(m,o\.[a-z]+\)$'
    if [[ $t =~ $hre ]]; then body=$(MODE=def NAME=${BASH_REMATCH[1]} awk -f "$A" "$rf"); fi
    lhs=$(printf '%s\n' "$body" | MODE=fields awk -f "$A" | norm | sort)
    rhs=$(MODE=action NAME=$acts awk -f "$A" "$ideal" | sort)
    if [[ -z $lhs || -z $rhs || $lhs == *UNPARSED* ]]; then echo "FAIL  $b: could not extract the fields (${lhs:0:60} | ${rhs:0:60})"; fails=$((fails + 1))
    elif [[ $lhs == "$rhs" ]]; then echo "ok    $b = ideal $acts, word for word ($(cut -f1 <<< "$lhs" | tr '\n' ' '))"
    else echo "FAIL  $b differs from ideal $acts:"; diff <(printf '%s\n' "$rhs") <(printf '%s\n' "$lhs") | sed 's/^/        /'; fails=$((fails + 1)); fi
  else
    nb=$(printf '%s' "$t" | sha) nv=$(ideal_definition "$acts" | sha)
    if [[ $nb == "$bsha" && $nv == "$vsha" ]]; then echo "ok    $b whitelisted ($kind vs ideal $acts): $why"
    else echo "FAIL  $b whitelist entry stale: branch sha $nb (listed $bsha), ideal $acts sha $nv (listed $vsha) -- re-review"; fails=$((fails + 1)); fi
  fi
done
(( pr )) && { for x in ${OP_MIRROR_ACTIONS:-}; do printf 'ideal %s\t%s\n' "$x" "$(ideal_definition "$x" | sha)"; done; exit 0; }
while IFS=$'\t' read -r kind b _; do
  [[ -z $kind || $kind == \#* ]] && continue
  printf '%s\n' "${BR[@]}" | cut -f1 | /usr/bin/grep -qx -- "$b" || { echo "FAIL  whitelisted branch $b no longer exists in $(basename "$rf")"; fails=$((fails + 1)); }
done < "$wl"
if (( fails == 0 )); then echo "op mirror OK (${#BR[@]} branches, $(basename "$rf") vs $(basename "$ideal"))"; exit 0
else echo "op mirror: FAIL $fails"; exit 1; fi
