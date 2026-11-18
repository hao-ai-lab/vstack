#!/usr/bin/env python3
"""Check a coordinator's unit table for status, evidence, one-unit-first order and gaps against the plan. Read-only."""

import argparse
import sys
from pathlib import Path

HEADER = ["unit_id", "resource", "subsystems", "k", "plane", "entry_kind", "tier", "properties", "method",
          "budget_result", "evidence_level", "status", "brief", "owner", "output_dir", "batch", "first_of_batch",
          "key", "evidence"]
OLD_HEADER = [name for name in HEADER if name != "brief"]  # release 0.123.0
COMPARE_HEADER = ["row_a", "row_b", "relation", "contradiction", "who_is_right", "note"]
STATUSES = ["queued", "running", "pass", "issues", "blocked", "accepted"]
PAST_RUNNING = {"pass", "issues", "blocked", "accepted"}
FINAL = {"accepted", "blocked"}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"ERROR arguments: {message}\n")


def data_lines(path):
    """Yield (line number, line) for rows that are neither blank nor comments."""
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip() and not line.lstrip().startswith("#"):
            yield no, line


def read_plan(path):
    """One unit id per line, or a TSV whose header has a unit_id column."""
    rows = list(data_lines(path))
    if rows and "\t" in rows[0][1] and "unit_id" in rows[0][1].split("\t"):
        column = rows[0][1].split("\t").index("unit_id")
        return [line.split("\t")[column].strip() for _, line in rows[1:] if len(line.split("\t")) > column]
    return [line.strip() for _, line in rows]


def is_compare_table(path):
    try:
        first = next(data_lines(path), (0, ""))[1]
    except (OSError, UnicodeError):
        return False
    return first.split("\t") == COMPARE_HEADER


def main():
    parser = Parser(description=__doc__, epilog=(
        "Header: the exact templates/unit-table.tsv header; blank and # rows are skipped. Status is one of "
        + ", ".join(STATUSES) + ". Every row needs a unique unit_id, a batch, yes/no in first_of_batch and key, "
        "and its own output_dir (unique, not nested in another). Past running (pass, issues, blocked, accepted) "
        "a row needs an owner and evidence: ;-separated paths that exist inside its output_dir; a key unit past "
        "running names two owners (a;b) and, unless blocked, a writing-compare table among its evidence. Each "
        "batch has exactly one first unit, and no other unit of the batch leaves queued before the first is "
        "accepted. --plan lists the planned unit ids; a planned unit missing from the table or a unit absent "
        "from the plan fails. --final also fails on any unit not accepted or blocked; blocked rows are reported "
        "as gaps. Dispatch: brief is the brief the unit's worker was sent and owner the id of that worker (the "
        "id the harness gave the sub-agent, not a role or slot name). A unit past queued needs a brief that "
        "exists; a row that names a brief needs its worker, so a brief written but never dispatched fails; one "
        "worker id may appear in one unit only, and one brief in one unit only, so a message for a worker reaches "
        "one unit. --briefs DIR also fails on a brief file (*.md, recursively) in DIR that no row names. "
        "Relative paths resolve against --root (default: the table's folder). Content of the evidence "
        "is not judged. Exit 0: valid; 1: invalid or unreadable; 2: usage."))
    parser.add_argument("table", type=Path, metavar="UNITS.tsv")
    plan = parser.add_mutually_exclusive_group(required=True)
    plan.add_argument("--plan", type=Path, metavar="FILE", help="planned unit ids, one per line or a unit_id column")
    plan.add_argument("--no-plan", action="store_true", help="skip the gap check against a plan (say so in reports)")
    parser.add_argument("--final", action="store_true", help="end of batch: every unit accepted or blocked")
    parser.add_argument("--root", type=Path, metavar="DIR")
    parser.add_argument("--briefs", type=Path, metavar="DIR", help="folder of written briefs; each must be in a row")
    args = parser.parse_args()
    root = (args.root or args.table.resolve().parent).resolve()
    errors = []

    def error(where, reason):
        errors.append(f"ERROR {args.table}{':' + str(where) if where else ''}: {reason}")

    try:
        lines = list(data_lines(args.table))
        planned = read_plan(args.plan) if args.plan else None
    except (OSError, UnicodeError) as exc:
        print(f"ERROR {getattr(exc, 'filename', None) or args.table}: {exc}\nFAIL unit table: 1 errors")
        return 1
    if not lines or lines[0][1].split("\t") != HEADER:
        hint = ("; this is the 0.123.0 header: add the column brief before owner"
                if lines and lines[0][1].split("\t") == OLD_HEADER else "")
        print(f"ERROR {args.table}: header must be {' '.join(HEADER)} (tab-separated){hint}\n"
              "FAIL unit table: 1 errors")
        return 1
    rows = []
    for no, line in lines[1:]:
        values = line.split("\t")
        if len(values) != len(HEADER):
            error(no, f"expected {len(HEADER)} columns, found {len(values)}")
            continue
        rows.append((no, dict(zip(HEADER, (value.strip() for value in values)))))
    if not rows:
        error(None, "no unit rows")

    ids, dirs, batches, workers, briefs = {}, {}, {}, {}, {}
    for no, row in rows:
        unit, status = row["unit_id"], row["status"]
        if not unit:
            error(no, "unit_id is required")
        elif unit in ids:
            error(no, f"duplicate unit_id {unit} (first at line {ids[unit]})")
        else:
            ids[unit] = no
        if status not in STATUSES:
            error(no, f"status must be one of {', '.join(STATUSES)}, not {status!r}")
        for field in ("first_of_batch", "key"):
            if row[field] not in {"yes", "no"}:
                error(no, f"{field} must be yes or no, not {row[field]!r}")
        if not row["batch"]:
            error(no, "batch is required")
        else:
            batches.setdefault(row["batch"], []).append((no, row))
        owners = [name.strip() for name in row["owner"].split(";") if name.strip()]
        if status != "queued" and not owners:
            error(no, f"a {status} unit needs an owner")
        for name in dict.fromkeys(owners):
            if name in workers:
                error(no, f"worker {name} is recorded for units {workers[name]} and {unit}; one fresh worker per "
                          "unit, so that a message for a worker reaches one unit")
            else:
                workers[name] = unit
        brief = row["brief"]
        if brief:
            path = (root / brief).resolve()
            if not path.is_file():
                error(no, f"brief does not exist: {brief}")
            if path in briefs:
                error(no, f"brief {brief} is also the brief of unit {briefs[path]}; every unit has its own brief")
            briefs.setdefault(path, unit)
            if not owners:
                error(no, f"brief {brief} has no recorded worker: it was written but never dispatched, or its "
                          "worker's id was not recorded")
        elif status != "queued":
            error(no, f"a {status} unit needs the brief its worker was sent (column brief)")
        if row["key"] == "yes" and status in PAST_RUNNING and len(set(owners)) != 2:
            error(no, "a key unit is written twice: owner must name two different workers (a;b)")
        if not row["output_dir"]:
            error(no, "output_dir is required")
            continue
        out = (root / row["output_dir"]).resolve()
        for other, other_no in dirs.items():
            if out == other or out.is_relative_to(other) or other.is_relative_to(out):
                error(no, f"output_dir {row['output_dir']} overlaps the output_dir at line {other_no}")
        dirs[out] = no
        evidence = [item.strip() for item in row["evidence"].split(";") if item.strip()]
        if status in PAST_RUNNING and not evidence:
            error(no, f"a {status} unit needs evidence")
        for item in evidence:
            path = (root / item).resolve()
            if not path.exists():
                error(no, f"evidence does not exist: {item}")
            elif not (path == out or path.is_relative_to(out)):
                error(no, f"evidence lies outside the unit's output_dir: {item}")
        if (row["key"] == "yes" and status in PAST_RUNNING - {"blocked"}
                and not any(is_compare_table(root / item) for item in evidence)):
            error(no, "a key unit needs its writing-compare table (templates/writing-compare.tsv) in evidence")
        if args.final and status not in FINAL:
            error(no, f"not drained: {unit} is {status}; at the end of a batch every unit is accepted or blocked")

    for batch, members in batches.items():
        first = [(no, row) for no, row in members if row["first_of_batch"] == "yes"]
        if len(first) != 1:
            error(members[0][0], f"batch {batch} needs exactly one first_of_batch=yes, found {len(first)}")
            continue
        first_no, first_row = first[0]
        started = [row["unit_id"] for no, row in members if no != first_no and row["status"] != "queued"]
        if started and first_row["status"] != "accepted":
            error(first_no, f"batch {batch}: first unit {first_row['unit_id']} is {first_row['status']}, "
                            f"but {', '.join(started)} already left queued; accept the first unit before fanning out")

    if args.briefs:
        folder = (args.briefs if args.briefs.is_absolute() else Path.cwd() / args.briefs).resolve()
        if not folder.is_dir():
            error(None, f"--briefs {args.briefs} is not a directory")
        for path in sorted(folder.rglob("*.md")) if folder.is_dir() else []:
            if path.resolve() not in briefs:
                error(None, f"brief {path} is named by no unit row: written but never dispatched, or not recorded")

    if planned is not None:
        if not planned:
            error(None, f"plan {args.plan} lists no unit")
        for unit in planned:
            if unit not in ids:
                error(None, f"planned unit missing from the table: {unit}")
        for unit, no in ids.items():
            if unit not in planned:
                error(no, f"unit is not in the plan: {unit}")

    for message in errors:
        print(message)
    if errors:
        print(f"FAIL unit table: {len(errors)} errors")
        return 1
    counts = ", ".join(f"{s} {n}" for s in STATUSES if (n := sum(row["status"] == s for _, row in rows)))
    plan_note = (f"plan {len(planned)} units, none missing" if planned is not None
                 else "no plan supplied, gaps not checked")
    gaps = sum(row["status"] == "blocked" for _, row in rows)
    print(f"OK unit table: {len(rows)} units in {len(batches)} batches ({counts}); {plan_note}; "
          f"{gaps} blocked {'unit' if gaps == 1 else 'units'} recorded as gaps; {len(briefs)} briefs, "
          f"{len(workers)} workers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
