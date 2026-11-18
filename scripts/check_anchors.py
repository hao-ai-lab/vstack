#!/usr/bin/env python3
"""Check source citations and optionally list uncovered Python attribute writes."""

import argparse
import ast
import re
import tokenize
from pathlib import Path

HEADER = ["state_field", "site", "kind", "status", "model_operator", "reason", "quoted_code"]
SITE = re.compile(r"(.+):([1-9][0-9]*)@([^\s@]+)$")


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"ERROR arguments: {message}\n")


def normalized(text):
    return " ".join(text.split())


def under_root(root, name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("path must be relative and stay under source root")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("path resolves outside source root")
    return resolved


def attribute_writes(tree, fields):
    """Return (attribute, line) sites; unpacking targets may contain attributes."""
    sites = set()

    def target(node):
        if isinstance(node, ast.Attribute) and node.attr in fields:
            sites.add((node.attr, node.lineno))
        elif isinstance(node, (ast.Tuple, ast.List)):
            for item in node.elts:
                target(item)
        elif isinstance(node, ast.Starred):
            target(node.value)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.Delete)):
            for item in node.targets:
                target(item)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            target(node.target)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id == "setattr" and len(node.args) >= 2
              and isinstance(node.args[1], ast.Constant)
              and isinstance(node.args[1].value, str) and node.args[1].value in fields):
            sites.add((node.args[1].value, node.lineno))
    return sites


def main():
    parser = Parser(description=__doc__, epilog=(
        "Input: exact anchors template header and single-line TSV fields; blank and # rows are skipped. "
        "Checks enums, companions and whitespace-normalized source quotes. The commit suffix is recorded, "
        "not checked against Git: independently pin DIR. With both --fields and --paths, prints WRITE "
        "sites and rejects missing write rows. Paths are relative files, directories or quoted globs "
        "under DIR; directories are scanned recursively. Python sources only: plain, augmented and "
        "annotated attribute assignments, literal-name setattr and deletion. Aliases, dynamic attribute "
        "names, container mutation through a method call and native code are not seen; a clean result "
        "is a lower bound on coverage, not proof of completeness. Read-only, no network. "
        "Exit 0: valid; 1: invalid or unreadable input; 2: usage."
    ))
    parser.add_argument("--source-root", required=True, type=Path, metavar="DIR")
    parser.add_argument("--anchors", required=True, type=Path, metavar="TSV")
    parser.add_argument("--fields", type=Path, metavar="FILE", help="one attribute name per line (# comments allowed)")
    parser.add_argument("--paths", nargs="+", metavar="GLOB", help="Python files/directories/globs relative to DIR")
    args = parser.parse_args()
    if bool(args.fields) != bool(args.paths):
        parser.error("--fields and --paths must be supplied together")
    root = args.source_root.resolve()
    errors = []

    def error(where, reason):
        errors.append(f"ERROR {where}: {reason}")

    if not root.is_dir():
        print(f"ERROR {root}: source root is not a directory")
        return 1
    try:
        lines = args.anchors.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        print(f"ERROR {args.anchors}: {exc}")
        return 1
    if not lines or lines[0].split("\t") != HEADER:
        print(f"ERROR {args.anchors}: header must be {' '.join(HEADER)} (tab-separated)")
        return 1
    covered, source_cache = set(), {}
    count = 0
    for no, line in enumerate(lines[1:], 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        where = f"{args.anchors}:{no}"
        values = line.split("\t")
        if len(values) != len(HEADER):
            error(where, f"expected {len(HEADER)} columns, found {len(values)}")
            continue
        row = dict(zip(HEADER, (value.strip() for value in values)))
        count += 1
        if not row["state_field"]:
            error(where, "state_field is required")
        if row["kind"] not in {"write", "hold", "read"}:
            error(where, f"invalid kind: {row['kind']!r}")
        if row["status"] not in {"modeled", "assumed_env", "out_of_scope"}:
            error(where, f"invalid status: {row['status']!r}")
        if row["status"] == "modeled" and not row["model_operator"]:
            error(where, "modeled row requires model_operator")
        if row["status"] != "modeled" and not row["reason"]:
            error(where, "non-modeled row requires reason")
        match = SITE.fullmatch(row["site"])
        if not match:
            error(where, "site must be path:line@commit")
            continue
        name, lineno, _commit = match.groups()
        lineno = int(lineno)
        try:
            path = under_root(root, name)
            if path not in source_cache:
                if path.suffix == ".py":
                    with tokenize.open(path) as stream:
                        source_cache[path] = stream.read().splitlines()
                else:
                    source_cache[path] = path.read_text(encoding="utf-8").splitlines()
            source = source_cache[path]
            if lineno > len(source):
                error(where, f"source line does not exist: {row['site']}")
            elif not row["quoted_code"] or normalized(row["quoted_code"]) not in normalized(source[lineno - 1]):
                error(where, f"quoted_code does not match {row['site']}")
            elif row["kind"] == "write":
                covered.add((path, lineno, row["state_field"]))
        except (OSError, UnicodeError, ValueError, SyntaxError) as exc:
            error(where, str(exc))
    if not count:
        error(args.anchors, "no anchor rows")
    writes = 0
    if args.fields:
        fields = set()
        try:
            for no, line in enumerate(args.fields.read_text(encoding="utf-8").splitlines(), 1):
                field = line.strip()
                if not field or field.startswith("#"):
                    continue
                if not field.isidentifier():
                    error(f"{args.fields}:{no}", "expected one attribute name")
                else:
                    fields.add(field)
            if not fields:
                error(args.fields, "no attribute names")
        except (OSError, UnicodeError) as exc:
            error(args.fields, str(exc))
        paths = set()
        for pattern in args.paths:
            try:
                under_root(root, pattern)
                matches = [root] if pattern in {".", "./"} else sorted(root.glob(pattern))
                if not matches:
                    error(pattern, "path or glob matches nothing")
                for match in matches:
                    under_root(root, match.relative_to(root))
                    selected = sorted(match.rglob("*.py")) if match.is_dir() else [match]
                    for path in selected:
                        resolved = under_root(root, path.relative_to(root))
                        if resolved.suffix != ".py" or not resolved.is_file():
                            error(path.relative_to(root), "expected a Python source file")
                        else:
                            paths.add(resolved)
            except (OSError, ValueError, NotImplementedError) as exc:
                error(pattern, str(exc))
        if not paths:
            error("--paths", "no Python source files selected")
        for path in sorted(paths):
            try:
                with tokenize.open(path) as stream:
                    tree = ast.parse(stream.read(), filename=str(path))
                for field, lineno in sorted(attribute_writes(tree, fields), key=lambda item: (item[1], item[0])):
                    writes += 1
                    site = f"{path.relative_to(root)}:{lineno}"
                    print(f"WRITE {site}: {field}")
                    if (path, lineno, field) not in covered:
                        error(site, f"attribute {field} has no write row")
            except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
                error(path.relative_to(root), str(exc))
    for message in errors:
        print(message)
    if not errors:
        print(f"OK anchors: {count} rows, {writes} Python write sites checked")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
