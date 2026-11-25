#!/usr/bin/env python3
"""Extract and check the hand-back block of a worker reply against its logs and, optionally, its brief. Read-only."""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_brief as cb  # noqa: E402

BEGIN, END = "BEGIN HANDBACK", "END HANDBACK"
VERDICTS = {"PASS", "ISSUES", "BLOCKED"}
PORCELAIN = re.compile(r"^([ MTADRCU?!]{2}) (.+)$")
EMPTY_REFS = {"", "none", "n/a", "-"}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"ERROR arguments: {message}\n")


def normalized(text):
    return " ".join(text.split())


def last_line(path):
    lines = [line.rstrip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    lines = [line for line in lines if line.strip()]
    return lines, (lines[-1] if lines else None)


def field_pattern(keys):
    return re.compile(r"^(" + "|".join(re.escape(key) for key in sorted(keys, key=len, reverse=True))
                      + r"):\s*(.*?)\s*$", re.I)


def parse_block(text, keys):
    """Return (fields, problems): (line, key, value) inside the single block and (line or None, reason)."""
    problems, lines, pattern = [], text.splitlines(), field_pattern(keys)
    begins = [no for no, line in enumerate(lines, 1) if line.strip() == BEGIN]
    ends = [no for no, line in enumerate(lines, 1) if line.strip() == END]
    if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
        return [], [(None, f"expected exactly one '{BEGIN}' line followed by one '{END}' line "
                           f"(found {len(begins)} and {len(ends)})")]
    fields = []
    for no in range(begins[0] + 1, ends[0]):
        line = lines[no - 1].strip()
        if not line:
            continue
        match = pattern.match(line)
        if not match:
            problems.append((no, f"not a hand-back field: {line[:80]}"))
            continue
        key, value = match.group(1).lower(), match.group(2)
        if not value:
            problems.append((no, f"empty {key}"))
        fields.append((no, key, value))
    if not fields and not problems:
        problems.append((None, "empty hand-back block"))
    return fields, problems


def unquote_path(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return text


def read_changed(path, tree):
    """(line, name, path, deleted) from `git status --porcelain` output or one path per line.

    Relative paths resolve against tree. A deleted file and the source of a rename are changes too, but cannot be
    reported as written because they no longer exist."""
    entries = []
    for no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        match = PORCELAIN.match(line)
        names = [(line.strip(), False)]
        plain = tree / unquote_path(line.strip())
        if match and (plain.exists() or plain.is_symlink()):
            raise ValueError(f"{path}:{no}: {line.strip()!r} reads both as a git status line and as the path of "
                             "an existing file; pass git status --porcelain=v1 output, or one path per line "
                             "without such names")
        if match:
            status, rest = match.groups()
            if "R" in status and " -> " in rest:
                old, new = rest.split(" -> ", 1)
                names = [(old, True), (new, "D" in status)]
            else:
                names = [(rest.split(" -> ")[-1], "D" in status)]
        for name, deleted in names:
            name = unquote_path(name)
            entries.append((no, name, (Path(name) if Path(name).is_absolute() else tree / name).resolve(), deleted))
    return entries


def table_rows(path):
    lines = cb.tsv_lines(path)
    numbered = [(no, line) for no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1)
                if line.strip() and not line.lstrip().startswith("#")]
    return lines[0].split("\t"), numbered[1:]


def main():
    parser = Parser(description=__doc__, epilog=(
        "The block lies between a 'BEGIN HANDBACK' and an 'END HANDBACK' line anywhere in the reply; each line is "
        "'field: value', the fields being those of the block in templates/task-brief.md. Required: one verdict "
        "(PASS, ISSUES or BLOCKED); one or more checks, each 'check:' followed by its 'log:' and 'last line:'; "
        "one or more 'version:', 'written:' and 'rules broken:' lines ('none' only alone). Each log must exist "
        "and its last non-blank line must equal the claimed last line; each written file must exist. Relative "
        "paths resolve against --root (default: the reply's folder). With --brief, every done-evidence command "
        "must be reported (except under BLOCKED), a PASS verdict needs every expected last line (exact, suffix "
        "or a regular expression for the whole line), and every written file must lie under a writable path of "
        "the brief (globs and 'except' items honoured). Every 'ref:' of the brief and every --ref is checked: "
        "each id in that column of the output (cells split on ; , and spaces; empty, none, n/a and - skipped) "
        "must be an id of the named table column (a relative --ref table resolves against --root); a missing "
        "output is an error unless the verdict is BLOCKED; an invalid pattern in the brief is an error. "
        "--changed lists the files changed in a tree (git status --porcelain=v1 --untracked-files=all output, "
        "or one path per line, relative to --tree; a line that reads both as a status line and as an existing path "
        "is refused as ambiguous): each must be writable by exactly one of the brief and the "
        "--sibling briefs, and each one this brief may write must be reported as written (a deleted file or the "
        "source of a rename only needs to be writable); a directory entry fails. The parser trusts the "
        "log files themselves; it does not re-run commands. Prints the fields as TSV. "
        "Exit 0: valid; 1: invalid or unreadable; 2: usage."))
    parser.add_argument("reply", type=Path, metavar="REPLY")
    parser.add_argument("--brief", type=Path, metavar="BRIEF.md")
    parser.add_argument("--root", type=Path, metavar="DIR")
    parser.add_argument("--ref", nargs=4, action="append", default=[], metavar=("OUTPUT", "COLUMN", "TABLE", "ID"),
                        help="check that every id in COLUMN of OUTPUT is in column ID of TABLE")
    parser.add_argument("--changed", type=Path, metavar="FILE", help="files changed in the tree (needs --brief)")
    parser.add_argument("--tree", type=Path, metavar="DIR", help="root of relative --changed paths (default --root)")
    parser.add_argument("--sibling", type=Path, action="append", default=[], metavar="BRIEF.md",
                        help="brief of another worker in the same tree")
    args = parser.parse_args()
    if (args.changed or args.sibling) and not args.brief:
        parser.error("--changed and --sibling need --brief")
    root = (args.root or args.reply.resolve().parent).resolve()
    errors = []

    def error(where, reason):
        errors.append(f"ERROR {args.reply}{':' + str(where) if where else ''}: {reason}")

    try:
        rules = cb.load_rules()
        text = args.reply.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR {args.reply}: {exc}\nFAIL handback: 1 errors")
        return 1
    fields, problems = parse_block(text, rules.fields)
    for where, reason in problems:
        error(where, reason)
    if not fields:
        print("\n".join(errors) + f"\nFAIL handback: {len(errors)} errors")
        return 1

    verdicts = [(no, value) for no, key, value in fields if key == "verdict"]
    if len(verdicts) != 1:
        error(None, f"expected one verdict, found {len(verdicts)}")
    elif verdicts[0][1] not in VERDICTS:
        error(verdicts[0][0], f"verdict must be PASS, ISSUES or BLOCKED, not {verdicts[0][1]!r}")
    verdict = verdicts[0][1] if len(verdicts) == 1 else None

    checks, current = [], None
    for no, key, value in fields:
        if key == "check":
            current = {"line": no, "command": value}
            checks.append(current)
        elif key in {"log", "last line"}:
            if current is None:
                error(no, f"'{key}:' outside a check")
            elif key in current or (key == "last line" and "log" not in current):
                error(no, f"'{key}:' out of order in the check at line {current['line']}")
            else:
                current[key] = (no, value)
        else:
            current = None
    if not checks:
        error(None, "no check reported")
    for check in checks:
        for key in ("log", "last line"):
            if key not in check:
                error(check["line"], f"check has no '{key}:': {check['command']}")
        if "log" not in check or "last line" not in check or not check["log"][1]:
            continue
        log = Path(check["log"][1])
        log = log if log.is_absolute() else root / log
        try:
            lines, actual = last_line(log)
        except OSError as exc:
            error(check["log"][0], f"cannot read log {log}: {exc.strerror or exc}")
            continue
        claimed = check["last line"][1].strip()
        check["actual"] = actual
        if actual is None:
            error(check["log"][0], f"log is empty: {log}")
        elif actual.strip() != claimed:
            seen = [n for n, line in enumerate(lines, 1) if line.strip() == claimed]
            where = f"appears at non-blank line {seen[0]} of {len(lines)}" if seen else "does not appear"
            error(check["last line"][0], f"claimed last line {where} in {log}; the log ends with: {actual[:160]}")

    for key in ("version", "written", "rules broken"):
        if not any(k == key for _, k, _ in fields):
            error(None, f"no '{key}:' line")
    rules_broken = [(no, value) for no, key, value in fields if key == "rules broken"]
    if len(rules_broken) > 1 and any(value.lower() == "none" for _, value in rules_broken):
        error(rules_broken[0][0], "'rules broken: none' must be the only rules line")
    written = []
    for no, key, value in fields:
        if key != "written" or not value:
            continue
        path = Path(value)
        path = (path if path.is_absolute() else root / path).resolve()
        written.append((no, path))
        if not path.exists():
            error(no, f"written file does not exist: {value}")

    refs = [(None, *ref) for ref in args.ref]
    base = root
    brief = None
    if args.brief:
        brief = cb.parse_brief(args.brief, rules)
        if brief.errors:
            error(None, f"brief {args.brief} does not pass check_brief ({len(brief.errors)} errors)")
        reported = {}
        for check in checks:
            reported.setdefault(normalized(check["command"]), check)
        for _, command, mode, expected in brief.done:
            check = reported.get(normalized(command))
            if check is None:
                if verdict != "BLOCKED":
                    error(None, f"done-evidence command not reported: {command}")
                continue
            actual = check.get("actual")
            try:
                ok = actual is not None and (actual.strip() == expected if mode == "exact"
                                             else actual.rstrip().endswith(expected) if mode == "suffix"
                                             else re.fullmatch(expected, actual.strip()) is not None)
            except re.error as exc:
                error(check["line"], f"the brief's pattern for '{command}' is not a regular expression: {exc}")
                continue
            if verdict == "PASS" and not ok:
                rule = {"exact": "be", "suffix": "end with", "regex": "match"}[mode]
                error(check["line"], f"verdict PASS, but the last line of '{command}' should {rule}: {expected}")
        resolved = cb.Writable([str(Path(item).resolve()) for item in brief.writable.includes],
                               [str(Path(item).resolve()) for item in brief.writable.excludes])
        brief.resolved = resolved
        for no, path in written:
            if resolved.includes and not resolved.allows(path):
                error(no, f"written file lies outside the brief's writable paths: {path}")
        refs = [(no, out, column, table, id_column) for no, out, column, table, id_column in brief.refs] + refs
        roots = resolved.roots()
        base = Path(roots[0]) if roots else root

    ids_checked = 0
    for no, out, column, table, id_column in refs:
        where = f"ref at brief line {no}" if no else "--ref"
        out_path = Path(out) if Path(out).is_absolute() else base / out
        if not out_path.exists():
            if verdict != "BLOCKED":
                error(None, f"{where}: output {out_path} does not exist")
            continue
        try:
            ids = cb.column_values(table if Path(table).is_absolute() else root / table, id_column)
            header, rows = table_rows(out_path)
        except (OSError, UnicodeError, ValueError) as exc:
            error(None, f"{where}: {getattr(exc, 'strerror', None) or exc}")
            continue
        if column not in header:
            error(None, f"{where}: {out_path} has no column {column!r}")
            continue
        index = header.index(column)
        for line_no, line in rows:
            cells = line.split("\t")
            cell = cells[index].strip() if index < len(cells) else ""
            for value in re.split(r"[;,\s]+", cell):
                if value.lower() in EMPTY_REFS:
                    continue
                ids_checked += 1
                if value not in ids:
                    error(None, f"{out_path}:{line_no}: {column} {value} is not an id in {table} column {id_column}")

    changed_total, sibling_owned = 0, 0
    if args.changed:
        tree = (args.tree or root).resolve()
        siblings = []
        for path in args.sibling:
            sibling = cb.parse_brief(path, rules)
            if sibling.errors:
                error(None, f"sibling brief {path} does not pass check_brief ({len(sibling.errors)} errors)")
            siblings.append((path, cb.Writable([str(Path(i).resolve()) for i in sibling.writable.includes],
                                               [str(Path(i).resolve()) for i in sibling.writable.excludes])))
        try:
            entries = read_changed(args.changed, tree)
        except (OSError, UnicodeError, ValueError) as exc:
            error(None, f"cannot read {args.changed}: {exc}")
            entries = []
        mine_writable = getattr(brief, "resolved", cb.Writable())
        for no, name, path, deleted in entries:
            changed_total += 1
            if name.endswith("/"):
                error(None, f"{args.changed}:{no}: directory entry {name}; list files with "
                            "git status --porcelain=v1 --untracked-files=all")
                continue
            mine = mine_writable.allows(path)
            owners = [str(sibling) for sibling, writable in siblings if writable.allows(path)]
            if mine and owners:
                error(None, f"changed file {path} is writable by this brief and by {', '.join(owners)}; two workers "
                            "may not share a writable file")
            elif mine:
                if not deleted and not any(path == w or path.is_relative_to(w) for _, w in written):
                    error(None, f"changed file {path} is not reported as written")
            elif len(owners) > 1:
                error(None, f"changed file {path} is writable by {', '.join(owners)}; two workers may not share a "
                            "writable file")
            elif owners:
                sibling_owned += 1
            else:
                scope = "this brief and its siblings" if siblings else "this brief"
                error(None, f"changed file {path} lies outside the writable paths of {scope}")

    for message in errors:
        print(message)
    if errors:
        print(f"FAIL handback: {len(errors)} errors")
        return 1
    print("field\tindex\tvalue")
    print(f"verdict\t1\t{verdict}")
    for index, check in enumerate(checks, 1):
        print(f"check\t{index}\t{check['command']}\nlog\t{index}\t{check['log'][1]}\n"
              f"last_line\t{index}\t{check['last line'][1]}")
    for key in ("version", "written", "rules broken"):
        values = [value for _, k, value in fields if k == key]
        for index, value in enumerate(values, 1):
            print(f"{key.replace(' ', '_')}\t{index}\t{value}")
    broken = 0 if rules_broken and rules_broken[0][1].lower() == "none" else len(rules_broken)
    extra = f" refs={len(refs)} ids_checked={ids_checked}" if refs else ""
    if args.changed:
        extra += f" changed={changed_total} sibling_owned={sibling_owned}"
    print(f"OK handback: verdict={verdict} checks={len(checks)} written={len(written)} rules_broken={broken}{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
