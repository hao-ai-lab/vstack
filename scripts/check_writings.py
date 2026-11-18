#!/usr/bin/env python3
"""Check that a writing-compare table accounts for every row of two independent writings; list the grafts. Read-only."""

import argparse
import sys
from pathlib import Path

HEADER = ["row_a", "row_b", "relation", "contradiction", "who_is_right", "note"]
RELATIONS = {"same", "narrower", "broader", "overlap", "only_here"}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"ERROR arguments: {message}\n")


def rows(path):
    """Return (header, [(line, cells)]) of a TSV, skipping blank and # rows."""
    lines = [(no, line.split("\t")) for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
             if line.strip() and not line.lstrip().startswith("#")]
    return (lines[0][1], lines[1:]) if lines else ([], [])


def writing_ids(path, column, error):
    header, body = rows(path)
    if not header:
        error(path, "empty writing")
        return set()
    if column and column not in header:
        error(path, f"no column {column!r}")
        return set()
    index = header.index(column) if column else 0
    ids = {}
    for no, cells in body:
        value = cells[index].strip() if index < len(cells) else ""
        if not value:
            error(f"{path}:{no}", "row without an id")
        elif value in ids:
            error(f"{path}:{no}", f"duplicate id {value} (first at line {ids[value]})")
        else:
            ids[value] = no
    if not ids:
        error(path, "writing has no rows")
    return set(ids)


def main():
    parser = Parser(description=__doc__, epilog=(
        "COMPARE has the exact templates/writing-compare.tsv header. Each line relates row_a of writing A to "
        "row_b of writing B: same, narrower or broader (row_a claims less or more than row_b), overlap, or "
        "only_here with exactly one side filled. contradiction is yes or no; a contradiction names who_is_right "
        "(a, b or neither) and, in note, the code read to decide; otherwise who_is_right stays empty. Every row "
        "of both writings must appear at least once. Row ids come from --id-column (default: the first column). "
        "With --base a|b, prints the rows of the other writing to graft into the base. The relations themselves "
        "are judged by the reader, not by this script. Exit 0: valid; 1: invalid or unreadable; 2: usage."))
    parser.add_argument("compare", type=Path, metavar="COMPARE.tsv")
    parser.add_argument("--a", required=True, type=Path, metavar="A.tsv", help="first writing")
    parser.add_argument("--b", required=True, type=Path, metavar="B.tsv", help="second writing")
    parser.add_argument("--id-column", metavar="NAME")
    parser.add_argument("--base", choices=["a", "b"], help="writing kept as the base")
    args = parser.parse_args()
    errors = []

    def error(where, reason):
        errors.append(f"ERROR {where}: {reason}")

    try:
        ids = {"a": writing_ids(args.a, args.id_column, error), "b": writing_ids(args.b, args.id_column, error)}
        header, body = rows(args.compare)
    except (OSError, UnicodeError) as exc:
        print(f"ERROR {getattr(exc, 'filename', None) or args.compare}: {exc}\nFAIL writings: 1 errors")
        return 1
    if header != HEADER:
        print("\n".join(errors + [f"ERROR {args.compare}: header must be {' '.join(HEADER)} (tab-separated)"]))
        print(f"FAIL writings: {len(errors) + 1} errors")
        return 1
    seen = {"a": set(), "b": set()}
    pairs, lines, counts = {}, [], {}
    for no, cells in body:
        where = f"{args.compare}:{no}"
        if len(cells) != len(HEADER):
            error(where, f"expected {len(HEADER)} columns, found {len(cells)}")
            continue
        row = dict(zip(HEADER, (cell.strip() for cell in cells)))
        relation, contra, right = row["relation"], row["contradiction"], row["who_is_right"]
        sides = [side for side in "ab" if row[f"row_{side}"]]
        if relation not in RELATIONS:
            error(where, f"relation must be one of {', '.join(sorted(RELATIONS))}, not {relation!r}")
        elif relation == "only_here" and len(sides) != 1:
            error(where, "only_here needs exactly one of row_a and row_b")
        elif relation != "only_here" and len(sides) != 2:
            error(where, f"{relation} needs both row_a and row_b")
        for side in sides:
            if row[f"row_{side}"] not in ids[side]:
                error(where, f"row_{side} {row[f'row_{side}']} is not a row of writing {side.upper()}")
            seen[side].add(row[f"row_{side}"])
        key = (row["row_a"], row["row_b"])
        if key in pairs:
            error(where, f"pair listed twice (first at line {pairs[key]})")
        pairs[key] = no
        if contra not in {"yes", "no"}:
            error(where, f"contradiction must be yes or no, not {contra!r}")
        elif contra == "yes":
            if relation == "only_here":
                error(where, "a row found on one side only cannot contradict the other")
            if right not in {"a", "b", "neither"}:
                error(where, "a contradiction needs who_is_right: a, b or neither")
            if not row["note"]:
                error(where, "a contradiction needs a note naming the code read to decide it")
        elif right:
            error(where, "who_is_right is only filled for a contradiction")
        counts[relation] = counts.get(relation, 0) + 1
        lines.append(row)
    for side in "ab":
        for missing in sorted(ids[side] - seen[side]):
            where = args.a if side == "a" else args.b
            error(where, f"row {missing} of writing {side.upper()} is not in the compare table")
    if not lines and not errors:
        error(args.compare, "no compare rows")

    for message in errors:
        print(message)
    if errors:
        print(f"FAIL writings: {len(errors)} errors")
        return 1
    grafts = 0
    if args.base:
        other = "b" if args.base == "a" else "a"
        # Relations are written from A's side; from the base's side, "other is broader" flips with the base.
        broader = "narrower" if args.base == "a" else "broader"
        for row in lines:
            base_id, other_id = row[f"row_{args.base}"], row[f"row_{other}"]
            action = None
            if row["contradiction"] == "yes" and row["who_is_right"] == "neither":
                print(f"FIX {args.base}:{base_id} contradicts {other}:{other_id} and neither is right; "
                      "fix it from the code")
            elif row["contradiction"] == "yes":
                action = f"replaces {args.base}:{base_id}" if row["who_is_right"] == other else None
            elif row["relation"] == "only_here" and other_id:
                action = "only in this writing"
            elif row["relation"] == broader:
                action = f"broader than {args.base}:{base_id}"
            elif row["relation"] == "overlap":
                action = f"overlaps {args.base}:{base_id}; merge the extra part by hand"
            if action:
                grafts += 1
                print(f"GRAFT {other}:{other_id} {action}")
    contradictions = sum(row["contradiction"] == "yes" for row in lines)
    summary = ", ".join(f"{name} {counts[name]}" for name in sorted(counts))
    tail = f"; base {args.base}, {grafts} grafts" if args.base else ""
    print(f"OK writings: A {len(ids['a'])} rows, B {len(ids['b'])} rows, {len(lines)} compare rows ({summary}); "
          f"{contradictions} contradictions{tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
