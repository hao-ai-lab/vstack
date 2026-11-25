#!/usr/bin/env python3
"""Check a census-correction record: who corrected which row of a census table, from what wrong value to what
right value, of which kind, and on what evidence; with --table, also that the table now holds the right value.

Read-only. One tab-separated row per correction, under this script's header (print it with --template):
  fix_id        unique id of the correction
  date          YYYY-MM-DD
  corrected_by  who made the correction (an id without spaces)
  table         name of the corrected table, mapped to its file by --table NAME=PATH
  row_key       column=value items separated by ; that pick the row as the table is now
  field         the corrected column, or row for a row that was missing or should not exist
  wrong_value   the value the census recorded, or (absent) for a missing row
  right_value   the value it should hold, or (removed) for a row that should not exist
  kind          missed_write, not_shared, wrong_subsystem, wrong_access, wrong_site, wrong_condition, wrong_lifetime
  found_by      what found it (an id: second_census, second_pass, review, run, ...)
  evidence      path:LINE[-LINE][@commit] items separated by ; each with an optional excerpt
  note          free text, may be empty
missed_write needs field row, wrong_value (absent) and a right_value other than (removed); not_shared needs
field row and right_value (removed); the other kinds correct one column. With --table, a corrected row must
exist exactly once with the right value, a missing row must now exist, a removed row must be gone. With --source,
every cited path:LINE[-LINE] must name a file inside SOURCE and lines that exist, the range running upwards.
"""

import argparse
import re
import sys
from pathlib import Path

HEADER = ["fix_id", "date", "corrected_by", "table", "row_key", "field", "wrong_value", "right_value", "kind",
          "found_by", "evidence", "note"]
KINDS = {"missed_write", "not_shared", "wrong_subsystem", "wrong_access", "wrong_site", "wrong_condition",
         "wrong_lifetime"}
ABSENT, REMOVED, ROW = "(absent)", "(removed)", "row"
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]*")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
SITE = re.compile(r"(\S+?):([0-9]+)(?:-([0-9]+))?(?:@([0-9a-f]{7,40}))?(?=\s|$)")
EXAMPLE = ("# F-01\t2026-01-01\treviewer\tresources\tresource=shm-ring;site=engine/shm.py:40\tsubsystem\tengine\t"
           "mm-cache\twrong_subsystem\tsecond_pass\tengine/shm.py:40@0123abc only the media cache opens the ring\t"
           "the engine only passes the handle on")


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"ERROR arguments: {message}\n")


def read_tsv(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"{path}: empty")
    header = lines[0].split("\t")
    rows = [(no, line.split("\t")) for no, line in enumerate(lines[1:], 2)
            if line.strip() and not line.startswith("#")]
    return header, rows


def parse_key(text):
    pairs = []
    for item in text.split(";"):
        column, sep, value = item.strip().partition("=")
        if not sep or not column or not value:
            return None
        pairs.append((column, value))
    return pairs


def check_row(row, where, tables, source, error):
    for field in HEADER[:-1]:
        if not row[field]:
            error(where, f"{field} is required")
    if any(not row[f] for f in HEADER[:-1]):
        return
    for field in ("fix_id", "corrected_by", "table", "found_by"):
        if not TOKEN.fullmatch(row[field]):
            error(where, f"{field} is an id without spaces")
    if not DATE.fullmatch(row["date"]):
        error(where, "date is YYYY-MM-DD")
    kind, field = row["kind"], row["field"]
    if kind not in KINDS:
        error(where, "kind is one of " + ", ".join(sorted(KINDS)))
    if row["wrong_value"] == row["right_value"]:
        error(where, "wrong_value and right_value are the same")
    if kind == "missed_write" and (field != ROW or row["wrong_value"] != ABSENT or row["right_value"] == REMOVED):
        error(where, f"missed_write: field {ROW}, wrong_value {ABSENT} and a right_value other than {REMOVED} "
                     "(the missed row now exists)")
    elif kind == "not_shared" and (field != ROW or row["right_value"] != REMOVED or row["wrong_value"] == ABSENT):
        error(where, f"not_shared: field {ROW} and right_value {REMOVED}")
    elif kind in KINDS - {"missed_write", "not_shared"} and (field == ROW or ABSENT in (row["wrong_value"],)
                                                            or row["right_value"] == REMOVED):
        error(where, f"{kind} corrects one column: name it in field and give both values")
    found = [SITE.match(item.strip()) for item in row["evidence"].split(";")]
    if not all(found):
        error(where, "evidence is path:LINE[-LINE][@commit] items separated by ;, each with an optional excerpt "
              "(without ;)")
    elif source is not None:
        for path, first, last, _ in (match.groups() for match in found):
            target = (source / path).resolve()
            if not target.is_relative_to(source.resolve()) or not target.is_file():
                error(where, f"evidence {path} is not a file under {source}")
                continue
            count = len(target.read_bytes().splitlines())
            if not 1 <= int(first) <= int(last or first) <= count:
                error(where, f"evidence {path}:{first}{'-' + last if last else ''} is beyond its {count} lines")
    key = parse_key(row["row_key"])
    if key is None:
        error(where, "row_key is column=value items separated by ;")
        return
    if not tables:
        return
    if row["table"] not in tables:
        error(where, f"no --table for {row['table']}")
        return
    path, header, rows = tables[row["table"]]
    missing = [column for column, _ in key if column not in header] + (
        [field] if field != ROW and field not in header else [])
    if missing:
        error(where, f"{path} has no column {', '.join(missing)}")
        return
    matches = [(no, cells) for no, cells in rows
               if len(cells) == len(header) and all(cells[header.index(c)] == v for c, v in key)]
    if kind == "not_shared":
        if matches:
            error(where, f"the removed row is still in {path} (line {matches[0][0]})")
    elif len(matches) != 1:
        error(where, f"row_key picks {len(matches)} rows of {path}; it must pick exactly one")
    elif field != ROW:
        now = matches[0][1][header.index(field)]
        if now != row["right_value"]:
            error(where, f"{path}:{matches[0][0]} {field} is {now!r}, not the right value {row['right_value']!r}: "
                  "the correction is recorded but not applied")


def main():
    parser = Parser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1] + (
        "\nExit 0: valid; 1: invalid record or table; 2: usage."), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("record", type=Path, nargs="?", metavar="FIXES.tsv")
    parser.add_argument("--table", action="append", default=[], metavar="NAME=PATH",
                        help="the census table a correction names (repeat)")
    parser.add_argument("--source", type=Path, metavar="DIR", help="source tree the evidence cites")
    parser.add_argument("--template", action="store_true", help="print the header and an example row, then exit")
    args = parser.parse_args()
    if args.template:
        print("\t".join(HEADER) + "\n" + EXAMPLE)
        return 0
    if args.record is None:
        parser.error("FIXES.tsv is required")
    errors = []

    def error(where, reason):
        errors.append(f"ERROR {where}: {reason}")

    tables = {}
    try:
        for item in args.table:
            name, sep, path = item.partition("=")
            if not sep or not TOKEN.fullmatch(name) or name in tables:
                raise ValueError(f"--table {item!r}: expected NAME=PATH with a new NAME")
            header, rows = read_tsv(Path(path))
            tables[name] = (path, header, rows)
        header, rows = read_tsv(args.record)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR {exc}\nFAIL census-fixes: 1 errors")
        return 1
    if header != HEADER:
        print(f"ERROR {args.record}: header must be {' '.join(HEADER)} (tab-separated; see --template)\n"
              "FAIL census-fixes: 1 errors")
        return 1
    if args.source is not None and not args.source.is_dir():
        print(f"ERROR {args.source}: not a directory\nFAIL census-fixes: 1 errors")
        return 1
    seen = {}
    for no, cells in rows:
        where = f"{args.record}:{no}"
        if len(cells) != len(HEADER):
            error(where, f"expected {len(HEADER)} columns, found {len(cells)}")
            continue
        row = dict(zip(HEADER, (cell.strip() for cell in cells)))
        if row["fix_id"] in seen:
            error(where, f"fix_id {row['fix_id']} repeats line {seen[row['fix_id']]}")
        seen.setdefault(row["fix_id"], no)
        check_row(row, where, tables, args.source, error)
    if not rows:
        error(args.record, "no corrections (commented rows are examples)")
    for message in errors:
        print(message)
    if errors:
        print(f"FAIL census-fixes: {len(errors)} errors in {len(rows)} corrections")
        return 1
    against = f"; checked against {len(tables)} tables" if tables else "; tables not checked (no --table)"
    print(f"OK census-fixes: {len(rows)} corrections{against}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
