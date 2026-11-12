#!/usr/bin/env python3
"""CLI installer and gate runner for vstack."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


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
        if item.name.startswith("."):
            continue
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
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
        ("Claude Code", base / ".claude" / "skills", base / ".claude" / "agents"),
        ("Codex / Agents", base / ".agents" / "skills", None),
        ("Cursor", base / ".cursor" / "skills", base / ".cursor" / "agents"),
    ]

    print(f"Installing vstack from {ROOT} into {base}:")
    for name, s_dst, a_dst in targets:
        n_skills = _copy_tree_contents(skills_src, s_dst)
        msg = f"  [installed] {name}: {n_skills} skills -> {s_dst}"
        if a_dst is not None:
            n_agents = _copy_tree_contents(agents_src, a_dst)
            msg += f", {n_agents} agents -> {a_dst}"
        print(msg)

    print()
    cmd_doctor(args)
    print("\nReady. Launch your coding agent and invoke /vstack-mode.")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    scripts = {
        "check-pins": ROOT / "scripts" / "check_spec_pins.sh",
        "assumptions": ROOT / "scripts" / "assumptions_check.sh",
        "tlc-verdict": ROOT / "scripts" / "tlc_verdict.sh",
        "op-mirror": ROOT / "scripts" / "op_mirror.sh",
        "scope": ROOT / "scripts" / "scope_check.py",
    }
    script = scripts[args.gate]
    cmd = ([sys.executable, str(script)] if script.suffix == ".py" else ["bash", str(script)]) + args.args
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(prog="vstack", description="vstack formal verification CLI")
    sub = parser.add_subparsers(dest="command")

    p_setup = sub.add_parser("setup", help="Check solvers and install skills/agents for Claude Code, Codex, and Cursor")
    p_setup.add_argument("--target", help="Workspace directory to install into (defaults to user home directory)")
    p_setup.set_defaults(func=cmd_setup)

    p_doc = sub.add_parser("doctor", help="Check local Java/TLC, Z3, Apalache, and TLAPS availability")
    p_doc.set_defaults(func=cmd_doctor)

    p_gate = sub.add_parser("gate", help="Run a mechanical vstack verification gate script")
    p_gate.add_argument("gate", choices=["check-pins", "assumptions", "tlc-verdict", "op-mirror", "scope"])
    p_gate.add_argument("args", nargs=argparse.REMAINDER)
    p_gate.set_defaults(func=cmd_gate)

    args = parser.parse_args()
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
