#!/usr/bin/env python3
"""Audit declared write paths.
VSTACK_PROJECT_ROOT defaults to cwd; role cards are PROJECT/agents/<role>.md.
Usage: python3 scope_check.py ROLE PATH... | --all
Optional VSTACK_MAIN_GLOBS: coordinator-owned file, one glob per line.
Paths must be canonical, project-relative POSIX paths. This is an audit, not a sandbox.
Exit 0: allowed paths; 1: outside scope; 2: usage.
"""
import fnmatch
import os
import subprocess
import sys
from pathlib import Path

HUB = Path(os.environ.get("VSTACK_PROJECT_ROOT", ".")).resolve()
# Coordinator-owned patterns are explicit, rather than granting repository-wide defaults.
main_card = os.environ.get("VSTACK_MAIN_GLOBS")
MAIN_ONLY = [line.strip() for line in Path(main_card).read_text().splitlines()
             if line.strip() and not line.lstrip().startswith("#")] if main_card else []


def role_globs():
    roles = {}
    for card in sorted((HUB / "agents").glob("*.md")):
        if card.name.startswith("_"):
            continue
        text = card.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            continue
        globs, in_list = [], False
        for line in text[4:text.find("\n---", 4)].splitlines():
            if line.startswith("writable:"):
                in_list = True
                continue
            if in_list and line.startswith("  - "):
                globs.append(line[4:].strip())
            elif in_list and line.strip():
                in_list = False
        roles[card.stem] = globs
    return roles


def matches(path, globs):
    return any(fnmatch.fnmatch(path, g) for g in globs)


def changed_paths():
    out = subprocess.run(["git", "-c", "gc.auto=0", "-c", "maintenance.auto=false", "-C", str(HUB), "-c", "core.quotepath=off", "status", "--porcelain=v1",
                          "--untracked-files=all"], capture_output=True, text=True, check=True).stdout
    return sorted({line[3:].split(" -> ")[-1] for line in out.splitlines() if line})


def main():
    roles = role_globs()
    if len(sys.argv) >= 3 and sys.argv[1] != "--all":
        role, paths = sys.argv[1], sys.argv[2:]
        if role not in roles:
            print(f"unknown role {role!r}; known: {sorted(roles)}")
            return 1
        bad = [p for p in paths if not matches(p, roles[role])]
        for p in paths:
            print(("ok     " if p not in bad else "OUT    ") + p)
        return 1 if bad else 0
    if sys.argv[1:] != ["--all"]:
        print(__doc__)
        return 2
    bad = 0
    for p in changed_paths():
        owners = [r for r, g in roles.items() if matches(p, g)]
        if owners:
            print(f"agent  {p}  <- {','.join(owners)}")
        elif matches(p, MAIN_ONLY):
            print(f"main   {p}")
        else:
            print(f"OUT    {p}")
            bad += 1
    print(f"outside every scope: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
