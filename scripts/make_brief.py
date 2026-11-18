#!/usr/bin/env python3
"""Generate a task brief from a template and a fields file, compute its counts, check it and stamp it."""

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_brief as cb  # noqa: E402

KEY = re.compile(r"^([a-z][a-z0-9 -]*[a-z0-9]):(?:[ \t]+(.*?))?\s*$")
EXPR = re.compile(r"\{\{\s*(rows|header|cell)\s+of\s+([^{}\n]*?)\s*\}\}")
CELL = re.compile(r"^(\S+)\s+column\s+(\S+)\s+where\s+([^=\s]+)=(.*)$")
RESERVED = {"template"}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"ERROR arguments: {message}\n")


def read_fields(path, problems):
    """Return {name: (line, value)}; a value is one line, or the indented block under 'name:'."""
    fields, lines, index = {}, Path(path).read_text(encoding="utf-8").splitlines(), 0
    while index < len(lines):
        line, no = lines[index], index + 1
        index += 1
        if not line.strip() or line.startswith("#"):
            continue
        match = KEY.match(line)
        if not match:
            problems.append((no, f"not a field line ('name: value', or 'name:' and an indented block): {line[:80]}"))
            continue
        name, value = match.group(1), match.group(2)
        if not value:
            block = []
            while index < len(lines) and (not lines[index].strip() or lines[index].startswith("  ")):
                block.append(lines[index][2:])
                index += 1
            while block and not block[-1].strip():
                block.pop()
            value = "\n".join(block)
        if name in fields:
            problems.append((no, f"field '{name}' given twice (first at line {fields[name][0]})"))
        fields[name] = (no, value)
    return fields


def join_paths(paths):
    quoted = [f"`{path}`" for path in paths]
    return quoted[0] if len(quoted) == 1 else ", ".join(quoted[:-1]) + " and " + quoted[-1]


def compute(kind, argument):
    """Render one computed value: a row count, a template header or one table cell."""
    if kind == "rows":
        files, _, condition = argument.partition(" where ")
        paths = files.split()
        if not paths or any(not path.startswith("/") for path in paths):
            raise ValueError("rows of: name one or more absolute paths")
        conditions = cb.parse_conditions(condition)
        total = cb.count_rows(paths, conditions)
        where = " and ".join(f"{column}{op}{value}" for column, op, value in conditions)
        return f"{total} rows of {join_paths(paths)}" + (f" where `{where}`" if where else "")
    if kind == "header":
        return f"header `{cb.template_header(argument)}` (from `{argument}`)"
    match = CELL.match(argument)
    if not match:
        raise ValueError("cell of: write 'cell of /abs/TABLE.tsv column NAME where KEY=VALUE'")
    path, column, key, value = match.groups()
    lines = cb.tsv_lines(path)
    header = lines[0].split("\t")
    for name in (column, key):
        if name not in header:
            raise ValueError(f"{path} has no column {name!r}")
    rows = [line.split("\t") for line in lines[1:]]
    found = [cells for cells in rows if len(cells) > header.index(key) and cells[header.index(key)].strip() == value]
    if len(found) != 1:
        raise ValueError(f"{path}: {len(found)} rows where {key}={value}, expected exactly one")
    cells = found[0]
    return cells[header.index(column)].strip() if header.index(column) < len(cells) else ""


def comment_spans(text):
    return [(m.start(), m.end()) for m in cb.COMMENT.finditer(text)]


def inside(position, spans):
    return any(start <= position < end for start, end in spans)


def expand(text, problems):
    """Replace every {{rows|header|cell of ...}} outside HTML comments with its computed value."""
    spans, out, last, computed = comment_spans(text), [], 0, 0
    for match in EXPR.finditer(text):
        if inside(match.start(), spans):
            continue
        try:
            value = compute(match.group(1), match.group(2))
            computed += 1
        except (OSError, UnicodeError, ValueError) as exc:
            line = text.count("\n", 0, match.start()) + 1
            problems.append((line, f"cannot compute {match.group(0)}: {getattr(exc, 'strerror', None) or exc}"))
            value = match.group(0)
        out += [text[last:match.start()], value]
        last = match.end()
    return "".join(out + [text[last:]]), computed


def render(template, fields, problems):
    """Fill every slot of the template outside comments; return the text and the names used."""
    spans, pieces, last, used = comment_spans(template), [], 0, set()
    for match in cb.SLOT.finditer(template):
        start, end = match.span()
        if inside(start, spans) or start < last:
            continue
        name, line = match.group(1), template.count("\n", 0, start) + 1
        if name not in fields:
            problems.append((line, f"no field for slot <{name}> (template line {line})"))
            continue
        used.add(name)
        value = fields[name][1]
        line_start = template.rfind("\n", 0, start) + 1
        line_end = template.find("\n", end)
        line_end = len(template) if line_end == -1 else line_end
        if template[line_start:line_end].strip() == match.group(0):
            pieces.append(template[last:line_start])
            last = min(line_end + 1, len(template))
            if value:
                pieces.append(value + ("\n" if line_end < len(template) else ""))
            elif template[:line_start].endswith("\n\n"):
                # An empty block drops its line; drop one of the two blank lines around it as well.
                following = template.find("\n", last)
                if following != -1 and not template[last:following].strip():
                    last = following + 1
        else:
            if "\n" in value or not value.strip():
                problems.append((fields[name][0], f"field '{name}' fills a slot inside a line (template line "
                                                  f"{line}); give it one non-empty line"))
            pieces += [template[last:start], value]
            last = end
    pieces.append(template[last:])
    return "".join(pieces), used


def stamped(body, template, fields_path):
    """Insert the generator stamp as the second line; the stamp hashes the body without itself."""
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    stamp = (f"<!-- generated by make_brief.py: template {template} sha256 {cb.sha256(template)}; fields "
             f"{fields_path} sha256 {cb.sha256(fields_path)}; body sha256 {digest}. Edit the fields and run "
             "make_brief.py again; never edit this file. -->")
    lines = body.split("\n")
    return "\n".join(lines[:1] + [stamp] + lines[1:])


def main():
    parser = Parser(description=__doc__, epilog=(
        "FIELDS holds one field per slot of the template: 'name: value' on one line, or 'name:' followed by "
        "lines indented by two spaces (a block). A slot is <name> or <name: guidance> outside HTML comments; a "
        "slot alone on its line takes a block (an empty block drops the line), a slot inside a line takes one "
        "line. 'template: PATH' in FIELDS (relative to the vstack root) or --template picks the template; the "
        "default is templates/task-brief.md. Outside comments, {{rows of /a.tsv /b.tsv [where COL=VALUE [and "
        "COL!=VALUE]]}} becomes 'N rows of `/a.tsv` and `/b.tsv` ...' counted with each file's own header "
        "skipped, {{header of TEMPLATE.tsv}} becomes that template's header with its source, and {{cell of "
        "/t.tsv column NAME where KEY=VALUE}} the one matching cell. Fails, writing nothing, on a field that "
        "fills no slot, a slot without a field, a value that cannot be computed, or a result that "
        "scripts/check_brief.py refuses. Writes OUT atomically with a stamp that check_brief.py verifies; "
        "refuses to overwrite a file that was not generated or was edited since, unless --force. Running it "
        "twice gives the same file. Exit 0: written; 1: refused; 2: usage."))
    parser.add_argument("fields", type=Path, metavar="FIELDS")
    parser.add_argument("--out", type=Path, required=True, metavar="BRIEF.md")
    parser.add_argument("--template", type=Path, metavar="FILE")
    parser.add_argument("--force", action="store_true", help="overwrite a hand-written or edited OUT")
    args = parser.parse_args()
    problems = []

    def fail():
        for line, reason in problems:
            print(f"ERROR {args.fields}{':' + str(line) if line else ''}: {reason}")
        print(f"FAIL make_brief: {len(problems)} errors")
        return 1

    try:
        fields = read_fields(args.fields, problems)
    except (OSError, UnicodeError) as exc:
        problems.append((None, str(exc)))
        return fail()
    named = fields.get("template", (None, ""))[1]
    from_field = (Path(named) if Path(named).is_absolute() else cb.ROOT / named).resolve() if named else None
    template = args.template.resolve() if args.template else from_field or cb.TEMPLATE.resolve()
    if args.template and from_field and from_field != template:
        problems.append((fields["template"][0], f"--template {args.template} differs from the field 'template: "
                                                f"{named}'"))
    try:
        text = template.read_text(encoding="utf-8")
        rules = cb.load_rules()
    except (OSError, UnicodeError, ValueError) as exc:
        problems.append((None, f"template: {exc}"))
        return fail()
    if problems:
        return fail()
    body, used = render(text, fields, problems)
    for name, (line, _) in sorted(fields.items(), key=lambda item: item[1][0]):
        if name not in used and name not in RESERVED:
            problems.append((line, f"field '{name}' fills no slot of {template} (left over from another fields "
                                   "file?)"))
    body, computed = expand(body, problems)
    if problems:
        return fail()
    fields_path = args.fields.resolve()
    final = stamped(body, template, fields_path)
    brief = cb.check_text(final, str(args.out), rules, provenance=True)
    if brief.errors:
        for message in brief.errors:
            print(message)
        print(f"FAIL make_brief: the generated brief does not pass check_brief ({len(brief.errors)} errors); "
              "nothing written")
        return 1
    out = args.out
    if out.exists() and not args.force:
        try:
            old = cb.check_text(out.read_text(encoding="utf-8"), str(out), rules)
        except (OSError, UnicodeError) as exc:
            problems.append((None, f"cannot read the existing {out}: {exc}"))
            return fail()
        edited = [message for message in old.errors if "edited after it was generated" in message]
        if old.stamp is None or edited:
            problems.append((None, f"{out} exists and was {'edited after generation' if edited else 'not generated'}"
                                   "; move its changes into the fields file, or pass --force"))
            return fail()
    temporary = out.with_name(f".{out.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(final, encoding="utf-8")
        os.replace(temporary, out)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        problems.append((None, f"cannot write {out}: {exc}"))
        return fail()
    print(f"OK make_brief: wrote {out} from {template.name} ({len(used)} slots filled, {computed} computed values); "
          f"check_brief passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
