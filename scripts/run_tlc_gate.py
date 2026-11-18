#!/usr/bin/env python3
"""Classify a finished TLC log and caller-supplied exit status; does not run TLC."""

import argparse
import re
from pathlib import Path

# Keep these property markers in agreement with tlc_verdict.sh, including -continue.
VIOLATION = re.compile(
    r"^Error: (?:Invariant [A-Za-z_0-9]+ is violated|"
    r"Action property [A-Za-z_0-9]+ is violated|"
    r"Temporal properties were violated|Deadlock reached)", re.MULTILINE
)
SUCCESS = "Model checking completed. No error has been found."
NUMBER = r"[0-9]+(?:,[0-9]{3})*"
SUMMARY = re.compile(
    rf"^({NUMBER}) states generated, ({NUMBER}) distinct states found, "
    rf"({NUMBER}) states left on queue\.?\s*$", re.MULTILINE
)
SIM_SUMMARY = re.compile(rf"^The number of states generated:\s*({NUMBER})\.?\s*$", re.MULTILINE)
SIM_PROGRESS = re.compile(rf"^Progress: ({NUMBER}) states checked\.?\s*$", re.MULTILINE)
ACTION = r"[A-Za-z_][A-Za-z_0-9]*(?:![A-Za-z_][A-Za-z_0-9]*)*"
COVERAGE = re.compile(
    rf"^\s*<({ACTION}) line [0-9]+, col [0-9]+ to line [0-9]+, col [0-9]+ "
    rf"of module [A-Za-z_][A-Za-z_0-9]*>:\s*({NUMBER})(?::\s*({NUMBER}))?\s*$"
)
ERROR = re.compile(
    r"^\s*(?:Error:|Error\b|Fatal\b|Exception\b|Unknown\b|"
    r"[\w.]*?(?:Exception|OutOfMemoryError)\b)", re.MULTILINE | re.IGNORECASE
)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"ERROR arguments: {message}\n")


def number(value):
    return int(value.replace(",", ""))


def coverage_counts(log):
    """Use only the last complete coverage report, never an interim report."""
    current, last = None, None
    for line in log.splitlines():
        if line.startswith("The coverage statistics at "):
            current = {}
            last = None
        elif line.strip() == "End of statistics." or line.startswith("End of statistics ("):
            # TLC ends the report of a larger model with a two-line advisory:
            # "End of statistics (please note that for performance reasons large models"
            if current is not None:
                last, current = current, None
        elif current is not None:
            match = COVERAGE.fullmatch(line)
            if match:
                name, first, second = match.groups()
                # TLC's pair is distinct:total; coverage needs total execution count.
                current.setdefault(name, []).append(number(second if second is not None else first))
    return last


def classify(log, exit_code, required, simulate, time_limit):
    summaries = list(SUMMARY.finditer(log))
    generated, states, queue = (None, None, None)
    if summaries:
        generated, states, queue = map(number, summaries[-1].groups())
    sim_summaries = list(SIM_SUMMARY.finditer(log))
    is_simulation = simulate or bool(re.search(r"^Running Random Simulation\b", log, re.MULTILINE))
    if is_simulation and sim_summaries:
        generated = number(sim_summaries[-1].group(1))
    # A bounded -simulate run of newer TLC prints no summary line: it ends with its last
    # "Progress: N states checked." line followed by "Finished in".
    sim_progress = list(SIM_PROGRESS.finditer(log)) if is_simulation else []
    if is_simulation and not summaries and not sim_summaries and sim_progress:
        generated = number(sim_progress[-1].group(1))
    if VIOLATION.search(log):
        return "VIOLATION", states, queue
    if time_limit:
        return "TIME_LIMIT", states, queue
    if exit_code != 0 or ERROR.search(log):
        return "ERROR", states, queue
    if is_simulation:
        finished = [m.start() for m in re.finditer(r"^Finished in\b", log, re.MULTILINE)]
        complete = bool((summaries or sim_summaries) and finished)
        if not complete and sim_progress and finished:
            # no summary line: the sample is finished only if "Finished in" follows the last progress line
            complete = finished[-1] > sim_progress[-1].start()
    else:
        complete = bool(summaries)
    if not complete:
        return "TIME_LIMIT", states, queue
    if generated == 0 or states == 0:
        return "EMPTY", states, queue
    if not is_simulation and queue != 0:
        return "TIME_LIMIT", states, queue
    if required is not None:
        counts = coverage_counts(log)
        if counts is None or any(name not in counts or min(counts[name]) <= 0 for name in required):
            return "COVERAGE_MISSING", states, queue
    if is_simulation:
        return "SAMPLED_NO_VIOLATION", states, queue
    if SUCCESS not in log:
        return "ERROR", states, queue
    return "COMPLETE_PASS", states, queue


def main():
    parser = Parser(description=__doc__, epilog=(
        "Understands English TLC console output: final 'N states generated, D distinct states found, "
        "Q states left on queue' summaries (comma-grouped counts allowed); the success and Error: "
        "property markers used by tlc_verdict.sh; simulation 'The number of states generated: N' "
        "and 'Finished in' lines. Progress lines are not final summaries, with one exception: a -simulate "
        "run that prints no summary line is a finished sample when its last 'Progress: N states checked.' "
        "line is followed by 'Finished in'. Coverage uses the last "
        "complete 'The coverage statistics at ...' / 'End of statistics.' block (also TLC's advisory "
        "form 'End of statistics (please note ...'): "
        "'<Action line L, col C to line L, col C of module M>: count' or ': distinct:total'. "
        "Nested expression counts do not count as action coverage. Required-actions FILE lists one "
        "action name per line, with blank/# lines ignored; an empty list is invalid. "
        "Supply one complete run, not concatenated logs. Read-only, no network; no source/configuration "
        "identity or witness validation. Trusts the caller's --time-limit-hit flag and --simulate "
        "(also detects the Running Random Simulation banner). Precedence: violation, explicit limit, "
        "error/nonzero exit, missing summary, empty exploration, unfinished queue, missing coverage, "
        "sample, exhaustive success. Exit 0: COMPLETE_PASS; 3: SAMPLED_NO_VIOLATION; 1: other verdict; "
        "2: usage/input error. Diagnostics go to stderr; valid invocations print one VERDICT line."
    ))
    parser.add_argument("--log", required=True, type=Path, help="complete TLC console log")
    parser.add_argument("--exit-code", required=True, type=int, metavar="N", help="TLC process exit status")
    parser.add_argument("--required-actions", type=Path, metavar="FILE")
    parser.add_argument("--simulate", action="store_true", help="classify a -simulate run as sampled")
    parser.add_argument("--time-limit-hit", action="store_true", help="caller observed an exhausted time limit")
    args = parser.parse_args()
    try:
        log = args.log.read_text(encoding="utf-8")
        required = None
        if args.required_actions is not None:
            required = []
            for no, line in enumerate(args.required_actions.read_text(encoding="utf-8").splitlines(), 1):
                name = line.strip()
                if not name or name.startswith("#"):
                    continue
                if not re.fullmatch(ACTION, name):
                    parser.error(f"{args.required_actions}:{no}: expected one action name")
                required.append(name)
            if not required:
                parser.error(f"{args.required_actions}: no required action names")
    except (OSError, UnicodeError) as exc:
        parser.error(str(exc))
    kind, states, queue = classify(log, args.exit_code, required, args.simulate, args.time_limit_hit)
    print(f"VERDICT {kind} states={states if states is not None else 'NA'} "
          f"queue={queue if queue is not None else 'NA'}")
    return 0 if kind == "COMPLETE_PASS" else 3 if kind == "SAMPLED_NO_VIOLATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
