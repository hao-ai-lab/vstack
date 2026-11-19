#!/usr/bin/env python3
"""Validate finding records and derive danger grades without running commands."""

from __future__ import annotations

import argparse
import csv
import itertools
import posixpath
import re
import shlex
import sys
from pathlib import Path

HEADER = (
    "finding_id unit author summary method found_by gate1a gate1b evidence_level "
    "entrypoint entry_kind default_launch_cmd launch_cmd non_default_settings preconditions injected "
    "single_model_only hits runs hit_unit hit_kind arm_stock arm_patched arm_reference reference_kind "
    "serious_consequence impact dup_search upstream_checked_at review_verdict reviewer ambiguous_facts "
    "tier grade route"
).split()
UNKNOWN = "unknown"
ENTRY_KINDS = ("external_request", "internal_control", "startup_config", "test_only")
TIERS = ("tier0", "tier1", "common_combo", "corner")
ENUMS = {
    "method": {"model_check", "smt", "exhaustive_sweep", "experiment"},
    "found_by": {"checker", "reading"},
    "gate1a": {"pass", "fail", "n/a"},
    "gate1b": {"pass", "fail", "n/a"},
    "evidence_level": {"model only", "CPU replay of real code", "real engine"},
    "entry_kind": {*ENTRY_KINDS, UNKNOWN},
    "single_model_only": {"yes", "no"},
    "hit_kind": {"random", "directed", "selected", "none"},
    "reference_kind": {"reference_implementation", "deployment_variable_control", "n/a"},
    "serious_consequence": {"yes", "no", UNKNOWN},
    "review_verdict": {"real", "real_but_narrow", "partial", "undetermined", "spec_defect", "harness_only",
                       "false_positive", "pending"},
    "tier": {*TIERS, UNKNOWN},
    "grade": {"A", "B", "C", "D", UNKNOWN, "n/a"},
    "route": {"private_report", "upstream_report", "keep_internal", "not_a_product_defect", "hold_for_review",
              "await_facts", "property_owner"},
}
COMPUTED = {"non_default_settings", "tier", "grade", "route"}
ARMS = ("arm_stock", "arm_patched", "arm_reference")
# Facts that may hold two readings; the record must carry the one giving the lower grade.
AMBIGUOUS = ("entry_kind", "serious_consequence", "single_model_only")
RANK = {"D": 0, "C": 1, "B": 2, "A": 3}
PRECONDITION_KINDS = ("request", "control", "timing", UNKNOWN)
# A consequence that is not serious says why, as the leading class of `impact`; nothing else may be `no`. In
# particular a wrong, incomplete or missing output of the request itself is serious (property owner, 2026-11-18).
NOT_SERIOUS = ("error", "slow", "report")
# Impact markers that send a reportable finding to the private channel: one request reads or changes another's
# data, or the finding ends the service for every in-flight request. They lead `impact`, in either order.
CROSS_REQUEST_MARK = "cross_request_data:"
AVAILABILITY_MARK = "availability:"
PRIVATE_MARKS = (CROSS_REQUEST_MARK, AVAILABILITY_MARK)
_NOT_TO = r"(?!\s+to\b)"  # "fails to free" names a leak or a slow path, not a failed request
_WORDS = r"(?:(?!(?:not|never|no)\b)[\w-]+ ){0,6}?"  # up to six words between, none a negation
_SPAN = r"(?:(?!\b(?:not|never|no)\b)[^.;:]){{0,{}}}?"  # a short stretch of one clause without a negation
# Phrases that state a service-ending effect; an impact naming one must carry the availability marker. The list
# reads words, not causes, and errs toward the marker, whose route is the safe one.
SERVICE_ENDING = (
    ("a process exit", re.compile(
        r"\b(?:engine[- ]?core|engine|api[- ]?server|server|scheduler|worker)(?:'s)?(?: process)?"
        r" (?:exits|exited|dies|died|crashes|crashed|terminates|terminated|stops serving|goes down|went down)\b"
        r"|\bexits the (?:server|process)\b"
        r"|\b(?:ends|ended|kills|killed|crashes|crashed|takes down|took down|brings down|brought down)"
        r" the (?:whole |entire )?(?:api[- ]?server|server|scheduler|engine[- ]?core|engine|worker)(?: process)?\b"
        r"(?! (?:step|loop|request|call)s?\b)"
        r"|\bENGINE_(?:CORE_)?DEAD\b|\bEngineDeadError\b|\bengine[- ](?:core[- ])?dead\b(?!-)", re.I)),
    ("refused new requests", re.compile(
        r"\brefus(?:es|ed|ing)? (?:every |all |any )?(?:new|later|further|subsequent) requests?\b"
        r"|\b(?:new|later|further|subsequent) requests? (?:are |were |is |get |got |being )?(?:refused|rejected)\b"
        r"|\b(?:new|later|further|subsequent) requests? " + _WORDS + r"(?:are|were|is|get|got) (?:refused|rejected)\b"
        r"|\b(?:new|later|further|subsequent) requests? " + _WORDS + r"fail(?:s|ed|ing)?\b" + _NOT_TO, re.I)),
    ("failure of other in-flight requests", re.compile(
        r"\b(?:every|all)\b[^.;:]{0,40}?\brequests?\b[^.;:]{0,60}?\bfail(?:s|ed|ing)?\b" + _NOT_TO
        + r"|\bother\b" + _SPAN.format(30) + r"\brequests?\b" + _SPAN.format(60) + r"\bfail(?:s|ed|ing)?\b"
        + _NOT_TO + r"|\bdenial of service\b", re.I)),
)
# Words that stand in for a command nobody established; `unknown` alone is the sanctioned value.
PLACEHOLDERS = {"n/a", "na", "none", "tbd", "todo", "default", "same", "-", "?", "...", UNKNOWN}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*", re.S)
OPTION = re.compile(r"--[A-Za-z0-9][A-Za-z0-9_-]*(?:=.*)?", re.S)
UNSIGNED = re.compile(r"[0-9]+")
RATIO = re.compile(r"([0-9]+)/([0-9]+)")
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/+-]*")
QUOTED_CELL = re.compile(r'"((?:[^"]|"")*)"(?=\t|\Z)')
FORMATS = {
    "finding_id": (TOKEN, "an identifier without spaces"),
    "unit": (TOKEN, "an identifier without spaces"),
    "author": (TOKEN, "an identifier without spaces"),
    "reviewer": (TOKEN, "an identifier without spaces"),
    "hit_unit": (re.compile(r"[a-z][a-z0-9_-]*"), "one lowercase word naming what was counted, such as requests"),
    "upstream_checked_at": (re.compile(r"[0-9a-f]{7,64}"), "the checked upstream commit as 7 to 64 lowercase hex digits"),
    "dup_search": (re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}: \S.*"), "YYYY-MM-DD: query; query"),
    "injected": (re.compile(r"none|\S+:[0-9]+ \S.*"), "none, or path:line followed by a description"),
}


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.exit(2, f"ERROR arguments: {message}\n")


def parse_command(command: str) -> tuple[str, set[tuple[str, str | None]]]:
    """Return the executable's base name and the literal leading assignments and long options."""
    words = shlex.split(command, comments=False, posix=True)
    result: set[tuple[str, str | None]] = set()
    index = 0
    while index < len(words) and ASSIGNMENT.fullmatch(words[index]):
        name, value = words[index].split("=", 1)
        result.add((name, value))
        index += 1
    if index == len(words):
        raise ValueError("expected an executable after leading environment assignments")
    executable = posixpath.basename(words[index])
    if words[index].lower() in PLACEHOLDERS or executable.lower() in PLACEHOLDERS:
        raise ValueError(f"{words[index]!r} is a placeholder, not a command; write unknown when the launch "
                         "was not established")
    index += 1  # Remaining positional arguments are ignored.
    while index < len(words):
        word = words[index]
        if word == "--":
            break
        if OPTION.fullmatch(word):
            if "=" in word:
                name, value = word.split("=", 1)
            else:
                name, value = word, None
                if index + 1 < len(words):
                    following = words[index + 1]
                    # Accept negative numeric values, but never eat another option.
                    if not following.startswith("-") or re.fullmatch(r"-\d+(?:\.\d+)?", following):
                        value = following
                        index += 1
            result.add((name, value))
        index += 1
    return executable, result


def format_settings(items: set[tuple[str, str | None]]) -> str:
    # Quote a whole setting so embedded spaces and semicolons remain unambiguous.
    return ";".join(sorted(shlex.quote(name if value is None else f"{name}={value}")
                           for name, value in items))


def precondition_items(value: str) -> list[tuple[str, str]]:
    """Split `kind:condition;kind:condition` into pairs; `none` and `unknown` are handled by callers."""
    items = []
    for item in value.split(";"):
        kind, _, text = item.strip().partition(":")
        items.append((kind.strip(), text.strip()))
    return items


def unknown_precondition(row: dict[str, str]) -> bool:
    value = row["preconditions"]
    return value == UNKNOWN or (value != "none" and any(kind == UNKNOWN for kind, _ in precondition_items(value)))


def has_control_precondition(row: dict[str, str]) -> bool:
    value = row["preconditions"]
    return value not in {"none", UNKNOWN} and any(kind == "control" for kind, _ in precondition_items(value))


def split_marks(impact: str) -> tuple[set[str], str]:
    """The private-routing markers leading `impact`, in any order, and the text after them."""
    marks: set[str] = set()
    text = impact
    while True:
        mark = next((m for m in PRIVATE_MARKS if text.startswith(m)), None)
        if mark is None:
            return marks, text
        marks.add(mark)
        text = text[len(mark):].lstrip()


def service_ending(impact: str) -> tuple[str, str] | None:
    """The first service-ending effect that `impact` states, as (class, matched words), or None."""
    for label, pattern in SERVICE_ENDING:
        match = pattern.search(impact)
        if match:
            return label, match[0]
    return None


def consequence_class(impact: str) -> tuple[str | None, str]:
    """The leading not-serious class of `impact` (after optional private-routing markers) or None, and the text
    after the class."""
    head, colon, rest = split_marks(impact)[1].partition(":")
    return (head, rest.strip()) if colon and head in NOT_SERIOUS else (None, "")


def has_unknown_fact(row: dict[str, str]) -> bool:
    return (unknown_precondition(row) or UNKNOWN in (row["default_launch_cmd"], row["launch_cmd"],
                                                     row["entry_kind"], row["serious_consequence"]))


def grade_from(kind: str, tier: str, serious: str) -> str:
    if kind == "test_only":
        return "D"
    if tier == "corner" or kind == "startup_config":
        return "C"
    if kind == "external_request":
        return "A" if tier in {"tier0", "tier1"} and serious == "yes" else "B"
    if kind == "internal_control" and tier in {"tier0", "tier1"}:
        return "B"
    return "C"


def derive(row: dict[str, str], count: int | None) -> tuple[str, str]:
    """Tier and grade from the facts; count is None when a launch command is unknown."""
    if row["injected"] != "none" or row["single_model_only"] == "yes":
        tier = "corner"
    elif count is None:
        tier = UNKNOWN
    else:
        tier = TIERS[min(count, 3)]
    verdict = row["review_verdict"]
    if verdict == "spec_defect":
        return tier, "n/a"
    if verdict in {"harness_only", "false_positive"}:
        return tier, "D"
    # The review verdict never caps the grade: confidence and priority are separate quantities.
    kinds = ENTRY_KINDS if row["entry_kind"] == UNKNOWN else (row["entry_kind"],)
    tiers = TIERS if tier == UNKNOWN else (tier,)
    serious = ("yes", "no") if row["serious_consequence"] == UNKNOWN else (row["serious_consequence"],)
    options = {grade_from(k, t, s) for k in kinds for t in tiers for s in serious}
    # An unsettled precondition may need a setting or a control call, so it can only lower the grade.
    if unknown_precondition(row) and options != {"D"}:
        return tier, UNKNOWN
    return tier, options.pop() if len(options) == 1 else UNKNOWN


def lowest_rank(row: dict[str, str], count: int | None) -> int | None:
    """The lowest grade rank the facts allow: the grade itself when it is known, else the lowest grade any value of
    the unknown facts gives (an unknown precondition may also make external traffic an internal control); None for
    a finding without a grade."""
    tier, grade = derive(row, count)
    if grade in RANK:
        return RANK[grade]
    if grade != UNKNOWN:
        return None
    kinds = ENTRY_KINDS if row["entry_kind"] == UNKNOWN else (row["entry_kind"],)
    if unknown_precondition(row) and "external_request" in kinds:
        kinds = (*kinds, "internal_control")
    tiers = TIERS if tier == UNKNOWN else (tier,)
    serious = ("yes", "no") if row["serious_consequence"] == UNKNOWN else (row["serious_consequence"],)
    return min(RANK[grade_from(k, t, s)] for k in kinds for t in tiers for s in serious)


def route_of(row: dict[str, str], grade: str) -> str:
    verdict = row["review_verdict"]
    if verdict in {"pending", "partial"}:
        return "hold_for_review"
    if verdict == "spec_defect":
        return "property_owner"
    if verdict == "undetermined" or grade == UNKNOWN:
        return "await_facts"
    if grade == "D":
        return "not_a_product_defect"
    if grade == "C":
        return "keep_internal"
    if split_marks(row["impact"])[0]:
        return "private_report"
    return "upstream_report"


def check_row(row: dict[str, str], where: str, errors: list[str]) -> None:
    def error(field: str, reason: str) -> None:
        errors.append(f"ERROR {where}:{field}: {reason}")

    start = len(errors)
    for field, value in row.items():
        if not value and field not in COMPUTED and not (field == "reviewer" and row["review_verdict"] == "pending"):
            error(field, "required field is empty")
        elif value and field in ENUMS and value not in ENUMS[field]:
            error(field, "expected one of " + ", ".join(sorted(ENUMS[field])))
        elif value and field in FORMATS and not FORMATS[field][0].fullmatch(value):
            error(field, "free text is not accepted here; expected " + FORMATS[field][1])
        if any(char in value for char in "\x00\r\n"):
            error(field, "fields must occupy one physical line and contain no NUL")
    verdict = row["review_verdict"]
    if verdict != "pending" and row["reviewer"] == row["author"]:
        error("reviewer", "must differ from author after review")
    if row["entry_kind"] != "test_only" and row["entrypoint"] == "n/a":
        error("entrypoint", "name the official server or CLI entry point")
    elif row["entry_kind"] == "test_only" and row["entrypoint"] != "n/a":
        error("entrypoint", "test_only means no official entry point reaches it; write n/a, or record the entry "
              "point with the entry kind it reaches")
    marks, described = split_marks(row["impact"])
    ending = service_ending(row["impact"])
    if row["impact"] and not described:
        error("impact", "a marker needs the concrete impact after it")
    elif ending and AVAILABILITY_MARK not in marks:
        error("impact", f"states {ending[0]} ({ending[1]!r}), which ends the service for other requests; start "
              f"impact with the {AVAILABILITY_MARK} marker (before error:, slow: or report:), so that the finding "
              "routes to the private channel after review")
    kind, reason = consequence_class(row["impact"])
    if kind is not None and not reason:
        error("impact", f"{kind}: needs the concrete impact after it")
    elif row["serious_consequence"] == "no" and kind is None:
        error("impact", "serious_consequence no needs impact to start with error:, slow: or report: (after the "
              f"optional markers {CROSS_REQUEST_MARK} and {AVAILABILITY_MARK}) saying why it is not serious; a "
              "wrong, incomplete or missing output of the request itself is serious (yes)")
    elif row["serious_consequence"] == "yes" and kind is not None:
        error("impact", f"{kind}: names a consequence that is not serious, but serious_consequence is yes")

    if row["preconditions"] not in {"", "none", UNKNOWN}:
        for kind, text in precondition_items(row["preconditions"]):
            if kind not in PRECONDITION_KINDS or not text:
                error("preconditions", "expected none, unknown, or kind:condition items separated by ; with kind "
                      "one of " + ", ".join(PRECONDITION_KINDS))
                break
        else:
            if row["entry_kind"] == "external_request" and has_control_precondition(row):
                error("entry_kind", "a control precondition means ordinary client traffic alone cannot trigger "
                      "it; use internal_control")

    counts = []
    for field in ("hits", "runs"):
        if not UNSIGNED.fullmatch(row[field]):
            error(field, "expected a non-negative integer")
        else:
            counts.append(int(row[field]))
    if len(counts) == 2:
        if counts[0] > counts[1]:
            error("hits", "cannot exceed runs")
        if row["hit_kind"] in ENUMS["hit_kind"] and (row["hit_kind"] == "none") != (counts[1] == 0):
            error("hit_kind", "use none exactly when there are no natural observations (runs = 0); "
                  "0/0 is not a measured rate")

    if all(row[field] == "n/a" for field in ARMS):
        if row["reference_kind"] != "n/a":
            error("reference_kind", "must be n/a when no fix is claimed")
    else:
        for field in ARMS:
            match = RATIO.fullmatch(row[field])
            if not match:
                error(field, "a fix needs all three arms as hits/runs")
            elif int(match[2]) == 0 or int(match[1]) > int(match[2]):
                error(field, "require 0 <= hits <= runs and runs > 0")
        if row["reference_kind"] not in {"reference_implementation", "deployment_variable_control"}:
            error("reference_kind", "a fix needs a reference implementation or deployment-variable control")

    commands = {}
    for field in ("default_launch_cmd", "launch_cmd"):
        if row[field] and row[field] != UNKNOWN:
            try:
                commands[field] = parse_command(row[field])
            except ValueError as exc:
                error(field, str(exc))
    if len(commands) == 2 and commands["launch_cmd"][0] != commands["default_launch_cmd"][0]:
        error("launch_cmd", "name the same executable as default_launch_cmd, so the settings comparison "
              "compares like with like")
    if len(errors) > start:
        return  # Grade only records whose facts are well formed.
    extra = commands["launch_cmd"][1] - commands["default_launch_cmd"][1] if len(commands) == 2 else None
    tier, grade = derive(row, None if extra is None else len(extra))

    if verdict == "real_but_narrow" and extra is not None and not extra and row["preconditions"] == "none" \
            and row["entry_kind"] == "external_request" and row["injected"] == "none" \
            and row["single_model_only"] == "no":
        error("review_verdict", "a narrow verdict needs the narrowing in the graded facts: a launch setting, a "
              "precondition, the entry kind, an injection or a model restriction")
    if verdict == "undetermined" and not has_unknown_fact(row):
        error("review_verdict", "an undetermined verdict must name the unsettled fact by recording it as unknown")

    if row["ambiguous_facts"] != "none":
        readings: dict[str, list[str]] = {}
        for item in row["ambiguous_facts"].split(";"):
            field, _, value = item.strip().partition("=")
            if field not in AMBIGUOUS or value not in ENUMS[field] - {UNKNOWN}:
                error("ambiguous_facts", "expected none or field=value items separated by ; with field one of "
                      + ", ".join(AMBIGUOUS) + " and a known value of that field")
                return
            if value == row[field] or row[field] == UNKNOWN or value in readings.get(field, []):
                error("ambiguous_facts", f"{field}={value} must differ from the recorded value, which must be known")
                return
            if (field, value) == ("entry_kind", "external_request") and has_control_precondition(row):
                error("ambiguous_facts", "entry_kind=external_request contradicts a control precondition")
                return
            readings.setdefault(field, []).append(value)
        # An unknown grade is compared by the lowest grade its facts allow, so a listed reading below all of them
        # is still refused.
        floor = lowest_rank(row, None if extra is None else len(extra))
        if floor is not None:
            fields = sorted(readings)
            for values in itertools.product(*([row[f], *readings[f]] for f in fields)):
                other = dict(row, **dict(zip(fields, values)))
                _, other_grade = derive(other, None if extra is None else len(extra))
                if other_grade in RANK and RANK[other_grade] < floor:
                    reading = ";".join(f"{f}={v}" for f, v in zip(fields, values) if v != row[f])
                    error("ambiguous_facts", f"record the lower reading: with {reading} the grade is "
                          f"{other_grade}, the recorded facts give {grade}")
                    return

    row["non_default_settings"] = UNKNOWN if extra is None else format_settings(extra)
    for field, value in (("tier", tier), ("grade", grade), ("route", route_of(row, grade))):
        if row[field] and row[field] != value:
            error(field, f"stored {row[field]!r} differs from computed {value!r}")
        row[field] = value


def tsv_cells(line: str) -> list[str]:
    """Split one TSV line. A cell that is wholly quoted, with inner quotes doubled (as --write writes a cell that
    holds a quote), is unquoted; every other cell is read as written, so prose may start with a quote."""
    line, cells, index = line.rstrip("\r\n"), [], 0
    while True:
        quoted = QUOTED_CELL.match(line, index)
        if quoted:
            cells.append(quoted.group(1).replace('""', '"'))
            index = quoted.end()
        else:
            end = line.find("\t", index)
            end = len(line) if end == -1 else end
            cells.append(line[index:end])
            index = end
        if index >= len(line):
            return cells
        index += 1  # the tab


def read_table(path: Path, errors: list[str]) -> tuple[list[tuple[int, str]], list[tuple[int, dict[str, str]]]]:
    lines = list(enumerate(path.read_text(encoding="utf-8").splitlines(keepends=True), 1))
    if not lines:
        errors.append(f"ERROR {path}: missing header")
        return [], []
    records = []
    seen: set[str] = set()
    for number, line in lines:
        if number > 1 and (not line.strip() or line.startswith("#")):
            continue
        values = tsv_cells(line)
        if number == 1:
            if values != HEADER:
                errors.append(f"ERROR {path}:1: header must be " + "\t".join(HEADER))
                return lines, []
            continue
        if len(values) != len(HEADER):
            errors.append(f"ERROR {path}:{number}: expected {len(HEADER)} columns, got {len(values)}")
            continue
        row = dict(zip(HEADER, (value.strip() for value in values)))
        if row["finding_id"] in seen:
            errors.append(f"ERROR {path}:{number}: duplicate finding_id {row['finding_id']!r}")
        seen.add(row["finding_id"])
        check_row(row, f"{path}:{number}", errors)
        records.append((number, row))
    if not records:
        errors.append(f"ERROR {path}: no finding records (commented examples are not records)")
    return lines, records


def main() -> int:
    parser = Parser(description=(
        "Validate a finding TSV: exact header, required fields, enumerations, field formats (no free text in "
        "structured fields), counts and their kind, three-arm companions, independent reviewer, verdict "
        "consistency, lower readings of ambiguous facts, and stored tier/grade/route. Compute "
        "non_default_settings, tier, grade and route. No network; input is read-only. Exit 0 only when all "
        "checks hold."
    ), epilog=(
        "Limits: compares command text, not whether settings change behaviour. Recognizes leading NAME=value "
        "and long options --name, --name=value, --name value; the next non-option token is treated as a value. "
        "Positional arguments and short options are ignored. Repeated identical name/value pairs count once; "
        "different values count separately. Both commands must name the same executable; placeholder words "
        "are refused, and unknown marks a launch nobody established (the tier is then unknown unless an "
        "injection or model restriction makes it corner). An unknown fact leaves the grade unknown unless every "
        "value it could take gives the same grade; an unknown precondition leaves it unknown unless the grade "
        "is D. Preconditions are recorded and checked for form, not counted in the tier. No shell expansion, "
        "wrapper interpretation or execution. Only the impact markers cross_request_data: and availability: "
        "(leading impact, in either order) select private routing for reportable grades. An impact that states "
        "a process exit, refused new requests or failure of other in-flight requests without availability: is "
        "refused; the phrase list reads words, not causes, and a missing cross_request_data: is not inferred. "
        "serious_consequence no needs impact to start with error:, slow: or report: (after the markers); yes may "
        "not start with one of them; a marker or a class with no text after it is refused. test_only needs "
        "entrypoint n/a. An unknown grade is compared with a listed ambiguous reading by the lowest grade its "
        "facts allow. A cell is read as written; only a wholly quoted cell with doubled inner quotes (as "
        "--write writes it) is unquoted, and no cell holds a tab. Review of evidence, default commands, security impact, preconditions "
        "and reference-contract agreement is manual. A pending row may be structurally valid but is held."
    ))
    parser.add_argument("tsv", type=Path, metavar="TSV", help="one finding per TSV row; # examples and blank lines are skipped")
    parser.add_argument("--write", type=Path, metavar="OUT", help="write computed columns to a new output file; never overwrite an input or existing output")
    args = parser.parse_args()
    errors: list[str] = []
    try:
        lines, records = read_table(args.tsv, errors)
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"ERROR {args.tsv}: {exc}")
        lines, records = [], []
    if args.write and (args.write.resolve() == args.tsv.resolve() or args.write.exists() or args.write.is_symlink()):
        errors.append(f"ERROR {args.write}: output must be a new file distinct from the input")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if args.write:
        by_line = dict(records)
        try:
            with args.write.open("x", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
                for number, line in lines:
                    if number == 1:
                        writer.writerow(HEADER)
                    elif number in by_line:
                        writer.writerow([by_line[number][field] for field in HEADER])
                    else:
                        stream.write(line)
        except OSError as exc:
            print(f"ERROR {args.write}: {exc}", file=sys.stderr)
            return 1
    print(f"PASS {args.tsv}: {len(records)} findings checked" + (f"; wrote {args.write}" if args.write else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
