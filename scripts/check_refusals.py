#!/usr/bin/env python3
"""Check the record of refused or ineffective operations from a check run on real code: each row answers the two
questions of the refusal rule, lists the documentation read, and carries the verdict the answers give.

Read-only. One tab-separated row per tested operation sequence, under this script's header (see --template):
  case_id   unique id of the case
  operation the calls in the order the check made them, separated by ; such as sleep(level=0); release()
  promised  question 1, does the documentation promise that this sequence can be done:
            yes (it says so), no (it forbids it or states a precondition the case did not meet),
            silent (the documentation read says nothing about it), unknown (not settled)
  doc_read  the documentation read, as SOURCE[:LINE[-LINE]] ["quote"] items separated by ; where SOURCE is a path
            under --docs or a URL; yes and no need a quote that names every call of the operation
  outcome   question 2, what the operation did: refused (an error, an exception, a rejected request),
            no_effect (it reported success and nothing changed), done (it took effect)
  verdict   failure, documented_refusal, triage, await_facts or pass, as the answers give it:
            done -> pass; no_effect -> failure; refused -> failure when promised yes, documented_refusal when no,
            triage when silent (neither a failure nor safe until the property owner decides), await_facts when
            unknown
  note      free text, may be empty
With --docs, every SOURCE path must exist under it and each quote must appear in the cited lines (whitespace is
normalized); URLs are not opened. The verdict is checked, not chosen: a refusal of a promised sequence cannot be
recorded as a documented precondition.
"""

import argparse
import re
import sys
from pathlib import Path

HEADER = ["case_id", "operation", "promised", "doc_read", "outcome", "verdict", "note"]
PROMISED = {"yes", "no", "silent", "unknown"}
OUTCOMES = {"refused", "no_effect", "done"}
VERDICTS = {"failure", "documented_refusal", "triage", "await_facts", "pass"}
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]*")
ITEM = re.compile(r'(?P<source>[^\s";]+)(?:\s+"(?P<quote>[^"]+)")?')
LINES = re.compile(r"(.+?):([0-9]+)(?:-([0-9]+))?")
CALL = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)\s*\(")
EXAMPLE = ('# C-01\tsleep(level=0); release_kv_cache_memory()\tyes\tdocs/control.md:12 "After sleep(level=0) '
           'release_kv_cache_memory() frees the KV cache"\trefused\tfailure\tthe second call raises')


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"ERROR arguments: {message}\n")


def verdict_of(promised, outcome):
    if outcome == "done":
        return "pass"
    if outcome == "no_effect" or promised == "yes":
        return "failure"
    return {"no": "documented_refusal", "silent": "triage", "unknown": "await_facts"}[promised]


def parse_doc_read(text):
    """(source, first, last, quote) items of doc_read, or None when it is malformed; quotes may hold ;."""
    items, position = [], 0
    while True:
        match = ITEM.match(text, position)
        if not match:
            return None
        source, quote = match.group("source"), match.group("quote")
        lines = LINES.fullmatch(source)
        first = last = None
        if lines:
            source, first, last = lines.group(1), int(lines.group(2)), int(lines.group(3) or lines.group(2))
        items.append((source, first, last, quote))
        position = match.end()
        if position == len(text):
            return items
        rest = re.match(r"\s*;\s*", text[position:])
        if not rest:
            return None
        position += rest.end()


def normalized(text):
    return " ".join(text.split())


def check_row(row, where, docs, error):
    for field in HEADER[:-1]:
        if not row[field]:
            error(where, f"{field} is required (doc_read lists what was read even when it is silent)")
            return
    if not TOKEN.fullmatch(row["case_id"]):
        error(where, "case_id is an id without spaces")
    steps = [step.strip() for step in row["operation"].split(";")]
    if not all(steps):
        error(where, "operation is the calls separated by ;")
    for field, choices in (("promised", PROMISED), ("outcome", OUTCOMES), ("verdict", VERDICTS)):
        if row[field] not in choices:
            error(where, f"{field} is one of {', '.join(sorted(choices))}")
            return
    expected = verdict_of(row["promised"], row["outcome"])
    if row["verdict"] != expected:
        error(where, f"verdict is {expected} when promised is {row['promised']} and the outcome is {row['outcome']}, "
              f"not {row['verdict']}")
    items = parse_doc_read(row["doc_read"])
    if items is None:
        error(where, 'doc_read is SOURCE[:LINE[-LINE]] ["quote"] items separated by ;')
        return
    quotes = " ".join(quote or "" for _, _, _, quote in items)
    if row["promised"] in {"yes", "no"}:
        if not quotes:
            error(where, f"promised {row['promised']} needs the documentation's words: quote them in doc_read")
        else:
            calls = {name.rsplit(".", 1)[-1] for name in CALL.findall(row["operation"])}
            missing = sorted(name for name in calls if not re.search(rf"(?<!\w){re.escape(name)}\b", quotes))
            if missing:
                error(where, f"the quoted documentation does not name {', '.join(missing)}: a promise or a "
                      "prohibition of this sequence names every call in it; quote the text about the sequence "
                      "that was run")
    if docs is None:
        return
    for source, first, last, quote in items:
        if re.match(r"[a-z]+://", source):
            continue
        path = docs / source
        if not path.is_file():
            error(where, f"doc_read {source} is not a file under {docs}")
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if first is None:
            first, last = 1, len(lines)
        if not 1 <= first <= last <= len(lines):
            error(where, f"doc_read {source}:{first}-{last} is outside its {len(lines)} lines")
        elif quote and normalized(quote) not in normalized(" ".join(lines[first - 1:last])):
            error(where, f"the quote is not in {source}:{first}{'-' + str(last) if last != first else ''}")


def main():
    parser = Parser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1] + (
        "\nExit 0: valid; 1: invalid record; 2: usage."), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("record", type=Path, nargs="?", metavar="REFUSALS.tsv")
    parser.add_argument("--docs", type=Path, metavar="DIR", help="the documentation tree doc_read cites")
    parser.add_argument("--template", action="store_true", help="print the header and an example row, then exit")
    args = parser.parse_args()
    if args.template:
        print("\t".join(HEADER) + "\n" + EXAMPLE)
        return 0
    if args.record is None:
        parser.error("REFUSALS.tsv is required")
    try:
        lines = args.record.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        print(f"ERROR {exc}\nFAIL refusals: 1 errors")
        return 1
    if not lines or lines[0].split("\t") != HEADER:
        print(f"ERROR {args.record}: header must be {' '.join(HEADER)} (tab-separated; see --template)\n"
              "FAIL refusals: 1 errors")
        return 1
    if args.docs is not None and not args.docs.is_dir():
        print(f"ERROR {args.docs}: not a directory\nFAIL refusals: 1 errors")
        return 1
    errors, seen, counts = [], {}, {}

    def error(where, reason):
        errors.append(f"ERROR {where}: {reason}")

    rows = 0
    for no, line in enumerate(lines[1:], 2):
        if not line.strip() or line.startswith("#"):
            continue
        rows += 1
        where = f"{args.record}:{no}"
        cells = line.split("\t")
        if len(cells) != len(HEADER):
            error(where, f"expected {len(HEADER)} columns, found {len(cells)}")
            continue
        row = dict(zip(HEADER, (cell.strip() for cell in cells)))
        if row["case_id"] in seen:
            error(where, f"case_id {row['case_id']} repeats line {seen[row['case_id']]}")
        seen.setdefault(row["case_id"], no)
        check_row(row, where, args.docs, error)
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    if not rows:
        error(args.record, "no cases (commented rows are examples)")
    for message in errors:
        print(message)
    if errors:
        print(f"FAIL refusals: {len(errors)} errors in {rows} cases")
        return 1
    summary = ", ".join(f"{counts.get(v, 0)} {v}" for v in ("failure", "documented_refusal", "triage", "await_facts",
                                                              "pass"))
    print(f"OK refusals: {rows} cases ({summary})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
