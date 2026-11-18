#!/usr/bin/env python3
"""Refuse table rows whose text names a class, function or field that does not exist in the source tree.

Read-only. The index holds the identifiers of the code under SOURCE: Python names, plus string literals that are
a name or a qualified name (a dictionary key, 'pkg.mod', 'ns::op') and the literal text of an f-string around its
placeholders; for other languages, every identifier outside comments. A name in a comment, a docstring or a
document does not count. Names match whole: an abbreviated class name that is a prefix of a real one is missing.

Code names in a cell are words of these shapes: snake_case or SCREAMING_SNAKE with an inner underscore, CamelCase
of four or more characters with a capital after a lowercase letter, lowerCamel, a leading underscore, each part of
a dotted name, a name followed by '(', and any word of three or more characters inside backticks (string literals
and command-line flags inside backticks are values and skipped). A word with '*' is a pattern that must match at
least one identifier. A name ending in s whose singular exists counts as a plural. A file path (a word with a
directory and a source suffix, or a bare file name ending in .py, .cu, .cpp and the like, optionally followed by
:LINE) must name a file under SOURCE. Product and model names written in CamelCase need an --allow entry.
"""

import argparse
import fnmatch
import io
import os
import re
import sys
import tokenize
from pathlib import Path

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
QUALIFIED = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.)[A-Za-z_][A-Za-z0-9_]*)*")
PLACEHOLDER = re.compile(r"\{[^{}]*\}")
FSTRING_MIDDLE = getattr(tokenize, "FSTRING_MIDDLE", None)
PYTHON = {".py", ".pyi"}
CYTHON = {".pyx", ".pxd"}
C_LIKE = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".cu", ".cuh", ".inc", ".rs", ".go", ".java",
          ".js", ".ts", ".tsx", ".jsx", ".kt", ".scala"}
SUFFIXES = PYTHON | CYTHON | C_LIKE
# Without a directory, only these suffixes mark a file name; others are too often attribute names (self.h).
FILE_SUFFIXES = PYTHON | CYTHON | {".cu", ".cuh", ".cpp", ".cc", ".cxx", ".hpp", ".hh"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "build", "dist"}
C_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
HASH_COMMENT = re.compile(r"#[^\n]*")
BACKTICK = re.compile(r"`([^`\n]+)`")
LITERAL = re.compile(r"\"[^\"]*\"|'[^']*'|<[^<>\s]*>|(?<![\w-])--?[A-Za-z][\w-]*")
PATH = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+(\.[A-Za-z0-9]+))(?::[0-9]+(?:-[0-9]+)?)?(?![\w/])")
WORD = re.compile(r"[A-Za-z0-9_*]+(?:\.[A-Za-z0-9_*]+)*(\()?")
SNAKE = re.compile(r"_*[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+_*")
CAMEL = re.compile(r"[A-Z][A-Za-z0-9]*[a-z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*|[A-Z]+[a-z][a-z0-9]*[A-Z][A-Za-z0-9]*")
CAMEL_MIN = 4  # shorter mixed-case words are abbreviations in prose (CoW)
LOWER_CAMEL = re.compile(r"[a-z][a-z0-9]*[A-Z][A-Za-z0-9]*")
ALLOW_HEADER = ["name", "reason"]


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"ERROR arguments: {message}\n")


def string_names(content):
    """Identifiers of a string literal that is a name, a qualified name or an f-string piece."""
    names = set()
    for piece in PLACEHOLDER.split(content):
        if QUALIFIED.fullmatch(piece):
            names |= set(IDENT.findall(piece))
    return names


def python_names(text):
    names = set()
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.NAME:
                names.add(token.string)
            elif token.type == FSTRING_MIDDLE:
                names |= string_names(token.string)
            elif token.type == tokenize.STRING:
                body = token.string.lstrip("rRbBuUfF")
                for quote in ('"""', "'''", '"', "'"):
                    if len(body) >= 2 * len(quote) and body.startswith(quote) and body.endswith(quote):
                        names |= string_names(body[len(quote):-len(quote)])
                        break
    except (tokenize.TokenError, IndentationError, SyntaxError):
        names |= set(IDENT.findall(HASH_COMMENT.sub("", text)))
    return names


def build_index(source):
    names, paths = set(), set()
    for base, dirs, files in os.walk(source):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in files:
            path = Path(base, name)
            suffix = path.suffix.lower()
            if suffix not in SUFFIXES or not path.is_file():
                continue
            paths.add(path.relative_to(source).as_posix())
            text = path.read_bytes().decode("utf-8", "replace")
            if suffix in PYTHON:
                names |= python_names(text)
            elif suffix in CYTHON:
                names |= set(IDENT.findall(HASH_COMMENT.sub("", text)))
            else:
                names |= set(IDENT.findall(C_COMMENT.sub("", text)))
    return names, paths


def is_code_shape(word):
    return bool(SNAKE.fullmatch(word) and "_" in word.strip("_") or word.startswith("_") and len(word) > 1
                or CAMEL.fullmatch(word) and len(word) >= CAMEL_MIN
                or LOWER_CAMEL.fullmatch(word) and len(word) >= 4)


def candidates(text):
    """(kind, word) pairs named in one cell: kind is 'path', 'pattern' or 'name'."""
    found = []
    # Inside code spans, string literals and command-line flags are values, not names.
    quoted = [LITERAL.sub(" ", span) for span in BACKTICK.findall(text)]
    for chunk, in_code in [(BACKTICK.sub(" ", text), False)] + [(span, True) for span in quoted]:
        rest = chunk
        for match in PATH.finditer(chunk):
            path, suffix = match.group(1), match.group(2).lower()
            bare = "/" not in path
            if suffix in (FILE_SUFFIXES if bare else SUFFIXES) and not (bare and "." in path[:-len(suffix)]):
                found.append(("path", path))
                rest = rest.replace(match.group(0), " ")
        for match in WORD.finditer(rest):
            word, call = match.group(0).rstrip("("), match.group(1)
            parts = word.split(".")
            for part in parts:
                if not part or part.isdigit() or not re.search(r"[A-Za-z]", part):
                    continue
                if "*" in part:
                    if re.search(r"[A-Za-z]{2}", part):
                        found.append(("pattern", part))
                elif (is_code_shape(part) or len(parts) > 1 and len(part) >= 2 and part[0].isalpha()
                      and all(p and p[0].isalpha() for p in parts) or call and len(part) >= 2
                      or in_code and len(part) >= 3 and IDENT.fullmatch(part)):
                    found.append(("name", part))
    return found


def missing_names(text, names, paths, allowed):
    missing = []
    for kind, word in candidates(text):
        if word in allowed:
            allowed[word] += 1
        elif kind == "path":
            if not any(p == word or p.endswith("/" + word) for p in paths):
                missing.append(word)
        elif kind == "pattern":
            if not any(fnmatch.fnmatchcase(name, word) for name in names):
                missing.append(word)
        elif word not in names and not (word.endswith("s") and word[:-1] in names):
            missing.append(word)
    return list(dict.fromkeys(missing))


def load_allow(path):
    lines = [(no, line) for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
             if line.strip() and not line.startswith("#")]
    if not lines or lines[0][1].split("\t") != ALLOW_HEADER:
        raise ValueError(f"{path}: header must be {' '.join(ALLOW_HEADER)} (tab-separated)")
    allowed = {}
    for no, line in lines[1:]:
        cells = [cell.strip() for cell in line.split("\t")]
        if len(cells) != 2 or not cells[0] or not cells[1]:
            raise ValueError(f"{path}:{no}: every entry needs a name and a reason")
        allowed[cells[0]] = 0
    return allowed


def main():
    parser = Parser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n", 1)[1] + (
        "\nExit 0: every named identifier exists; 1: a row names one that does not, or invalid input; 2: usage."),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, metavar="SOURCE", help="the source tree at the pinned revision")
    parser.add_argument("table", type=Path, metavar="TABLE", help="tab-separated table with a header row")
    parser.add_argument("--column", action="append", required=True, metavar="NAME",
                        help="a column whose text is checked (repeat for several)")
    parser.add_argument("--id-column", metavar="NAME", help="column that names a row in messages (default: first)")
    parser.add_argument("--allow", type=Path, metavar="FILE",
                        help="words that are not code names, as name<TAB>reason; every entry must be used")
    args = parser.parse_args()
    if not args.source.is_dir():
        print(f"ERROR {args.source}: not a directory\nFAIL names: 1 errors")
        return 1
    try:
        allowed = load_allow(args.allow) if args.allow else {}
        lines = args.table.read_text(encoding="utf-8").splitlines()
        names, paths = build_index(args.source)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR {exc}\nFAIL names: 1 errors")
        return 1
    header = lines[0].split("\t") if lines else []
    wanted = args.column + [args.id_column] if args.id_column else args.column
    absent = [column for column in wanted if column not in header]
    if absent:
        print(f"ERROR {args.table}: no column {', '.join(absent)} in the header\nFAIL names: 1 errors")
        return 1
    if not names:
        print(f"ERROR {args.source}: no source files with identifiers\nFAIL names: 1 errors")
        return 1
    id_index = header.index(args.id_column) if args.id_column else 0
    rows = bad = checked = 0
    errors = []
    for no, line in enumerate(lines[1:], 2):
        if not line.strip() or line.startswith("#"):
            continue
        cells = line.split("\t")
        if len(cells) != len(header):
            errors.append(f"ERROR {args.table}:{no}: expected {len(header)} columns, found {len(cells)}")
            continue
        rows += 1
        row_bad = False
        for column in args.column:
            text = cells[header.index(column)]
            checked += len(candidates(text))
            missing = missing_names(text, names, paths, allowed)
            if missing:
                row_bad = True
                print(f"ERROR {args.table}:{no} {cells[id_index]} {column}: not in the source: {', '.join(missing)}")
        bad += row_bad
    errors += [f"ERROR {args.allow}: entry {name!r} excuses no word; remove it" for name, used in allowed.items()
               if not used]
    for message in errors:
        print(message)
    if not rows and not errors:
        errors.append("no rows")
        print(f"ERROR {args.table}: no rows")
    if bad or errors:
        print(f"FAIL names: {bad} of {rows} rows name identifiers absent from the source; {len(errors)} errors")
        return 1
    print(f"OK names: {rows} rows, {checked} names checked against {len(names)} identifiers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
