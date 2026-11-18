#!/usr/bin/env python3
"""Validate a model/real-code agreement TSV without modifying its inputs."""

import argparse
import re
from pathlib import Path

HEADER = [
    "unit", "config_or_mutant", "kind", "scale", "mutant_of", "clauses",
    "model_verdict", "model_violated", "model_evidence", "mutation_reached",
    "real_code_method", "real_code_verdict", "code_violated", "seeds_or_traces", "hits",
    "agreement", "resolution", "evidence_level",
]
VERDICTS = {"pass", "violation", "not_run"}
ENUMS = {
    "kind": {"baseline", "mutant", "control"},
    "model_verdict": VERDICTS,
    "mutation_reached": {"yes", "no", "n/a"},
    "real_code_method": {"trace", "stateful_test", "none"},
    "real_code_verdict": VERDICTS,
    "agreement": {"agree", "clause_mismatch", "model_only_detects", "code_only_detects", "not_run"},
    "evidence_level": {"model only", "CPU replay of real code", "real engine"},
}
SIDES = (("model", "model_verdict", "model_violated"), ("code", "real_code_verdict", "code_violated"))
CLAUSE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*")
SETTING = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=\S(?:.*\S)?")


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"ERROR arguments: {message}\n")


def clause_set(text):
    """Distinct clause ids separated by ;, or None when malformed."""
    items = [item.strip() for item in text.split(";")]
    if not all(CLAUSE.fullmatch(item) for item in items) or len(set(items)) != len(items):
        return None
    return frozenset(items)


def main():
    parser = Parser(description=__doc__, epilog=(
        "Input: exact template header, tab-separated single-line fields; blank and # rows are skipped. "
        "Checks enums, a baseline for every unit, unique unit/configuration/scale rows, clause-level "
        "agreement (both sides must violate the same clauses to agree), violated clauses inside the compared "
        "clauses, mismatch resolutions and method/level consistency. If either verdict is not_run, agreement "
        "must be not_run. A mutant names the baseline or control row it modifies at the same scale; a mutant "
        "violation counts only when that unmutated row passes on that side and checked the violated clauses, "
        "and mutation_reached = yes records that every violating run passes through the mutated action or code. "
        "Read-only, no network; does not open evidence files, so mutation_reached, verdict truth, resolution "
        "adequacy and mutant inventory completeness are not verified. Exit 0: valid; 1: invalid or unreadable "
        "input; 2: usage."
    ))
    parser.add_argument("tsv", type=Path, help="agreement TSV using templates/agreement.tsv")
    args = parser.parse_args()
    errors = []

    def error(where, reason):
        errors.append(f"ERROR {where}: {reason}")

    try:
        lines = args.tsv.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        print(f"ERROR {args.tsv}: {exc}")
        return 1
    if not lines or lines[0].split("\t") != HEADER:
        print(f"ERROR {args.tsv}: header must be {' '.join(HEADER)} (tab-separated)")
        return 1
    rows, identities = [], {}
    for no, line in enumerate(lines[1:], 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        where = f"{args.tsv}:{no}"
        values = line.split("\t")
        if len(values) != len(HEADER):
            error(where, f"expected {len(HEADER)} columns, found {len(values)}")
            continue
        row = dict(zip(HEADER, (value.strip() for value in values)))
        for key, choices in ENUMS.items():
            if row[key] not in choices:
                error(where, f"invalid {key}: {row[key]!r}")
        scale = [item.strip() for item in row["scale"].split(";")]
        if not all(SETTING.fullmatch(item) for item in scale):
            error(where, "scale must list the run's constants as name=value items separated by ;")
        clauses = clause_set(row["clauses"])
        if clauses is None:
            error(where, "clauses must list the compared property clauses as distinct ids separated by ;")
        violated = {}
        for side, verdict_key, list_key in SIDES:
            verdict, text = row[verdict_key], row[list_key]
            if verdict == "violation":
                items = None if text in {"none", "n/a"} else clause_set(text)
                if items is None:
                    error(where, f"{list_key} must name the violated clauses when {verdict_key} is violation")
                elif clauses is not None and not items <= clauses:
                    error(where, f"{list_key} names clauses outside clauses: {', '.join(sorted(items - clauses))}")
                else:
                    violated[side] = items
            elif verdict == "pass" and text != "none":
                error(where, f"{list_key} must be none when {verdict_key} is pass")
            elif verdict == "not_run" and text != "n/a":
                error(where, f"{list_key} must be n/a when {verdict_key} is not_run")
        model, code = row["model_verdict"], row["real_code_verdict"]
        both_violate = model == code == "violation"
        if model in VERDICTS and code in VERDICTS and (not both_violate or len(violated) == 2):
            if "not_run" in (model, code):
                expected = "not_run"
            elif both_violate:
                # Agreement is per clause: both failing is not enough, they must fail the same clauses.
                expected = "agree" if violated["model"] == violated["code"] else "clause_mismatch"
            elif model == code:
                expected = "agree"
            else:
                expected = "model_only_detects" if model == "violation" else "code_only_detects"
            if row["agreement"] != expected:
                reason = " (the two sides violate different clauses)" if expected == "clause_mismatch" else ""
                error(where, f"agreement must be {expected} for {model}/{code}{reason}")
        detects = "violation" in (model, code)
        if row["kind"] == "mutant":
            if row["mutant_of"] in {"", "n/a"}:
                error(where, "a mutant names in mutant_of the baseline or control row it modifies")
            if detects and row["mutation_reached"] != "yes":
                error(where, f"mutation_reached is {row['mutation_reached']!r}: a violation counts for a mutant only "
                      "when every violating run passes through the mutated action or code")
            elif not detects and row["mutation_reached"] != "n/a":
                error(where, "mutation_reached must be n/a when neither side detects the mutant")
        else:
            if row["mutant_of"] != "n/a":
                error(where, "mutant_of must be n/a for baseline and control rows")
            if row["mutation_reached"] != "n/a":
                error(where, "mutation_reached must be n/a for baseline and control rows")
        # A mutant that neither side detects calibrates nothing: the check that should catch it is vacuous.
        if row["kind"] == "mutant" and model == "pass" and code == "pass" and not row["resolution"]:
            error(where, "mutant detected by neither model nor real code; record why in resolution or fix the check")
        if row["agreement"] != "agree" and not row["resolution"]:
            error(where, "non-agree row requires resolution")
        if row["real_code_method"] == "none" and row["evidence_level"] != "model only":
            error(where, "method none requires evidence_level model only")
        if row["real_code_method"] in {"trace", "stateful_test"} and row["evidence_level"] == "model only":
            error(where, "real-code method cannot have evidence_level model only")
        identity = (row["unit"], row["config_or_mutant"], frozenset(scale))
        if identity in identities:
            error(where, f"duplicate row for unit {row['unit']!r}, {row['config_or_mutant']!r} at this scale "
                  f"(first at line {identities[identity]})")
        identities.setdefault(identity, no)
        rows.append((where, row, identity, clauses))

    by_identity = {identity: (row, clauses) for _, row, identity, clauses in reversed(rows)}
    for where, row, identity, _ in rows:
        if row["kind"] != "mutant" or row["mutant_of"] in {"", "n/a"}:
            continue
        unit, _, scale = identity
        base, base_clauses = by_identity.get((unit, row["mutant_of"], scale), (None, None))
        if base is None or base["kind"] not in {"baseline", "control"}:
            error(where, f"mutant_of {row['mutant_of']!r} names no baseline or control row of unit {unit!r} "
                  "at the same scale")
            continue
        for side, verdict_key, list_key in SIDES:
            if row[verdict_key] != "violation":
                continue
            if base[verdict_key] != "pass":
                error(where, f"{side} violation is masked: the unmutated row {row['mutant_of']!r} has "
                      f"{verdict_key} {base[verdict_key]!r} at this scale, so the violation need not come from the "
                      "mutation; apply the mutant to a passing control, for example with the known repair on")
                continue
            items = clause_set(row[list_key]) or frozenset()
            if base_clauses is not None and not items <= base_clauses:
                error(where, f"the unmutated row {row['mutant_of']!r} did not check "
                      f"{', '.join(sorted(items - base_clauses))}, so its pass does not cover the {side} violation")
    units = {row["unit"] for _, row, _, _ in rows}
    baselines = {row["unit"] for _, row, _, _ in rows if row["kind"] == "baseline"}
    if not baselines:
        error(args.tsv, "no baseline row")
    for unit in sorted(units - baselines):
        error(args.tsv, f"unit {unit!r} has no baseline row")
    for message in errors:
        print(message)
    if not errors:
        print(f"OK agreement: {len(rows)} rows, {len(units)} units")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
