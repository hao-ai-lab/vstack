#!/usr/bin/env python3
"""CLI installer and gate runner for vstack."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Skill, agent and doc cards refer to docs/, scripts/, templates/, examples/ and NOTICE.md by relative paths.
# Installing these next to skills/ and agents/ in every target keeps those paths valid in a clone, a /plugin install
# and `vstack setup` alike.
LINKED_DIRS = ("docs", "scripts", "templates", "examples")
LINKED_FILES = ("NOTICE.md", "LICENSE")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")

GATES = {
    "check-pins": ROOT / "scripts" / "check_spec_pins.sh",
    "assumptions": ROOT / "scripts" / "assumptions_check.sh",
    "tlc-verdict": ROOT / "scripts" / "tlc_verdict.sh",
    "run-tlc": ROOT / "scripts" / "run_tlc_gate.py",
    "check-agreement": ROOT / "scripts" / "check_agreement.py",
    "check-anchors": ROOT / "scripts" / "check_anchors.py",
    "grade-findings": ROOT / "scripts" / "grade_findings.py",
    "op-mirror": ROOT / "scripts" / "op_mirror.sh",
    "scope": ROOT / "scripts" / "scope_check.py",
    "check-docs": ROOT / "scripts" / "check_docs.py",
    "make-brief": ROOT / "scripts" / "make_brief.py",
    "check-brief": ROOT / "scripts" / "check_brief.py",
    "check-unit-table": ROOT / "scripts" / "check_unit_table.py",
    "parse-handback": ROOT / "scripts" / "parse_handback.py",
    "check-writings": ROOT / "scripts" / "check_writings.py",
    "check-hygiene": ROOT / "scripts" / "check_hygiene.py",
    "check-names": ROOT / "scripts" / "check_names.py",
    "check-census-fixes": ROOT / "scripts" / "check_census_fixes.py",
    "check-refusals": ROOT / "scripts" / "check_refusals.py",
    "freeze-tools": ROOT / "scripts" / "freeze_tools.py",
    "gpu-pack": ROOT / "scripts" / "gpu_pack.py",
    "refuse-inline-python": ROOT / "scripts" / "refuse_inline_python.py",
}


def _check_cmd(label: str, cmd: list[str]) -> bool:
    exe = shutil.which(cmd[0])
    if not exe:
        print(f"  [missing] {label} ({cmd[0]} not on PATH)")
        return False
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        first = (out.stdout or out.stderr).strip().splitlines()
        summary = first[0] if first else exe
        if out.returncode != 0:
            print(f"  [missing] {label}: {summary}")
            return False
        print(f"  [ok]      {label}: {summary}")
        return True
    except Exception as exc:  # pragma: no cover
        print(f"  [warn]    {label}: {exc}")
        return False


def cmd_doctor(_args: argparse.Namespace) -> int:
    print("Checking formal verification toolchain:")
    _check_cmd("Java (for TLC)", ["java", "-version"])
    _check_cmd("Z3 SMT solver", ["z3", "--version"])
    _check_cmd("Apalache", ["apalache-mc", "version"])
    _check_cmd("TLAPS (tlapm)", ["tlapm", "--version"])
    return 0


def _copy_tree_contents(src: Path, dst: Path) -> int:
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for item in sorted(src.iterdir()):
        if item.name.startswith(".") or item.name == "__pycache__":
            continue
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target, ignore=IGNORE)
        else:
            shutil.copy2(item, target)
        count += 1
    return count


def cmd_setup(args: argparse.Namespace) -> int:
    base = Path(args.target).expanduser().resolve() if args.target else Path.home()
    skills_src = ROOT / "skills"
    agents_src = ROOT / "agents"
    if not skills_src.is_dir() or not agents_src.is_dir():
        print(f"Error: skills/ or agents/ not found under {ROOT}", file=sys.stderr)
        return 1

    targets = [
        ("Claude Code", base / ".claude"),
        ("Codex / Agents", base / ".agents"),
        ("Cursor", base / ".cursor"),
    ]
    linked_dirs = [d for d in LINKED_DIRS if (ROOT / d).is_dir()]
    linked_files = [f for f in LINKED_FILES if (ROOT / f).is_file()]
    missing = [d for d in LINKED_DIRS if d not in linked_dirs] + [f for f in LINKED_FILES if f not in linked_files]

    print(f"Installing vstack from {ROOT} into {base}:")
    if missing:
        print(f"  [warn]    not found under {ROOT}; links to them will not resolve: {', '.join(missing)}")
    for name, dotdir in targets:
        n_skills = _copy_tree_contents(skills_src, dotdir / "skills")
        n_agents = _copy_tree_contents(agents_src, dotdir / "agents")
        for d in linked_dirs:
            _copy_tree_contents(ROOT / d, dotdir / d)
        for f in linked_files:
            shutil.copy2(ROOT / f, dotdir / f)
        linked = ", ".join(linked_dirs + linked_files)
        print(f"  [installed] {name}: {n_skills} skills, {n_agents} agents, {linked} -> {dotdir}")

    print()
    cmd_doctor(args)
    print("\nReady. Launch your coding agent and invoke /vstack-mode.")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    script = GATES[args.gate]
    cmd = ([sys.executable, str(script)] if script.suffix == ".py" else ["bash", str(script)]) + args.args
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(prog="vstack", description="vstack formal verification CLI")
    sub = parser.add_subparsers(dest="command")

    p_setup = sub.add_parser(
        "setup", help="Check solvers and install skills, agents and the files they link to for Claude Code, Codex, and Cursor"
    )
    p_setup.add_argument("--target", help="Workspace directory to install into (defaults to user home directory)")
    p_setup.set_defaults(func=cmd_setup)

    p_doc = sub.add_parser("doctor", help="Check local Java/TLC, Z3, Apalache, and TLAPS availability")
    p_doc.set_defaults(func=cmd_doctor)

    p_gate = sub.add_parser("gate", help="Run a mechanical vstack verification gate script")
    p_gate.add_argument("gate", choices=list(GATES))
    p_gate.add_argument("args", nargs=argparse.REMAINDER)
    p_gate.set_defaults(func=cmd_gate)

    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
