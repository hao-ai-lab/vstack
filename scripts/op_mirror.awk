#   branches : on a refine module, print "<branch>\t<normalized text>" for every CASE branch under OP_MIRROR_HEADER
#   fields   : on stdin = one normalized "[m EXCEPT !.f = e, ...]" record update, print "<f>\t<e>" per field
#   action   : on a ideal module, NAME = action name; print "<f>\t<e>" for every conjunct "f' = e" of the action (depth 0)
#   def      : on a module, NAME = operator name; print the normalized definition body (one line)
# Normalization: comments dropped, all whitespace removed.
function strip(s) { sub(/\\\*.*/, "", s); return s }
function nows(s) { gsub(/[ \t]+/, "", s); return s }
# split s at top-level occurrences of sep (bracket / paren / brace / angle depth 0)
function tsplit(s, out, sep,   n, i, c, d, cur, L) {
  n = 0; d = 0; cur = ""; L = length(sep)
  for (i = 1; i <= length(s); i++) {
    c = substr(s, i, 1)
    if (d == 0 && substr(s, i, L) == sep) { out[++n] = cur; cur = ""; i += L - 1; continue }
    if (c == "[" || c == "(" || c == "{") d++
    else if (c == "]" || c == ")" || c == "}") d--
    else if (substr(s, i, 2) == "<<") { d++; cur = cur "<<"; i++; continue }
    else if (substr(s, i, 2) == ">>") { d--; cur = cur ">>"; i++; continue }
    cur = cur c }
  out[++n] = cur; return n }
BEGIN { mode = ENVIRON["MODE"]; name = ENVIRON["NAME"] }
mode == "branches" {
  if ($0 == ENVIRON["OP_MIRROR_HEADER"]) { inop = 1; next }
  if (inop && $0 ~ /^$/) { inop = 0 }
  if (inop) body = body nows(strip($0))
  next }
mode == "action" || mode == "def" {
  if (index($0, name "(") == 1 && $0 ~ /==/ || $0 ~ ("^" name " ==")) { ina = 1; sub(/^[^=]*==/, ""); }
  else if (ina && $0 ~ /^$/) ina = 0
  if (ina) body = body nows(strip($0))
  next }
mode == "fields" { body = body nows($0); next }
END {
  if (mode == "branches") {
    sub(/^CASE/, "", body)
    n = tsplit(body, br, "[]")
    for (i = 1; i <= n; i++) {
      if (match(br[i], /^o\.k="[a-z]+"->/)) { b = substr(br[i], 6, RLENGTH - 8); print b "\t" substr(br[i], RLENGTH + 1) }
      else print "UNPARSED\t" br[i] } }
  else if (mode == "fields") {
    s = body
    if (match(s, /^LET.*IN\[/)) s = substr(s, RLENGTH)          # LET P == .. IN [m EXCEPT ...] -> [m EXCEPT ...]
    if (substr(s, 1, 9) != "[mEXCEPT!") { print "UNPARSED\t" body; exit }
    s = substr(s, 9, length(s) - 9)                              # !.f = e, !.g = e
    n = tsplit(s, fl, ",")
    for (i = 1; i <= n; i++) if (match(fl[i], /^!\.[a-zA-Z]+=/)) print substr(fl[i], 3, RLENGTH - 3) "\t" substr(fl[i], RLENGTH + 1)
      else print "UNPARSED\t" fl[i] }
  else if (mode == "action") {
    s = body; gsub(/LET[^I]*IN/, "", s)                           # Limited LET dialect: no 'I' inside the binding
    n = tsplit(s, cj, "/\\")
    for (i = 1; i <= n; i++) if (match(cj[i], /^[a-zA-Z]+'=/)) print substr(cj[i], 1, RLENGTH - 2) "\t" substr(cj[i], RLENGTH + 1) }
  else if (mode == "def") print body
}
