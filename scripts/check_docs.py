#!/usr/bin/env python3
"""Check vstack documents, the bug ledger and the version manifests. Read-only.

Usage:
    python3 scripts/check_docs.py [--root DIR] [--links-only] [--expect-version X.Y.Z]

Checks, each reported as ERROR <path>[:<line>]: <reason>:
  1. Every local link and image in every .md file under ROOT resolves inside ROOT; every #anchor names a heading
     (GitHub slug rules) or an explicit HTML anchor in the target .md file.
  2. bugs/verified-bugs.csv: exact header; unique VS-NNN ids; violated_spec in the seven pillars; method in the
     closed enumeration; no listed shell model marked model_check; human_verifier is `In Progress` or `@handle`,
     and an @handle row's evidence states a real-engine run.
  3. The pillar table in bugs/README.md, SPEC_STYLE in scripts/sync_bugs_sheet.py and the method table in
     docs/exposure-gate.md list exactly the names used here.
  4. The five version manifests carry one version.
--links-only runs check 1 alone (for an installed tree such as <base>/.claude). Exit 0 only with zero errors.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None

LEDGER = "bugs/verified-bugs.csv"
HEADER = [
    "id", "system", "module", "summary", "violated_spec", "impact", "prior_status", "found_on",
    "checker", "method", "human_verifier", "upstream_label", "upstream_url", "status", "evidence",
]
PILLARS = ["Isolation", "Integrity", "Conservation", "Agreement", "Progress", "Finality", "Invariance"]
METHODS = ["model_check", "smt", "exhaustive_sweep", "experiment"]
# Models judged shell models under docs/exposure-gate.md (Gate 1b); a row citing one cannot be model_check.
SHELL_MODELS = ["GraphPad.tla"]
REAL_ENGINE = re.compile(
    r"\breal (engine|server)\b|\breal (vllm|sglang)\b|\b(GB200|B200|H200|H100|A100|MI300X?)\b|\bGPU\b", re.I
)
HANDLE = re.compile(r"^@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$")
VERSION_FILES = [
    "plugin.json",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".cursor-plugin/plugin.json",
    "pyproject.toml",
]

FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
INLINE_LINK = re.compile(r"!?\[(?:[^\[\]]|\[[^\[\]]*\])*\]\(\s*(<[^>]*>|[^\s)]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
REF_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)")
HTML_ATTR = re.compile(r"\b(?:href|src)\s*=\s*\"([^\"]*)\"", re.I)
HTML_ANCHOR = re.compile(r"<a\s+[^>]*\b(?:name|id)\s*=\s*\"([^\"]+)\"", re.I)
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"ERROR {where}: {msg}")


def slugify(text: str) -> str:
    """GitHub heading slug: strip inline markup, lowercase, drop punctuation, spaces to hyphens."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text).lower()
    kept = [c for c in text if c in " -" or unicodedata.category(c)[0] in "LMN" or unicodedata.category(c) == "Pc"]
    return "".join(kept).replace(" ", "-")


def scan_markdown(path: Path) -> tuple[set[str], list[tuple[int, str]]]:
    """Return the anchors a file defines and its (line, target) links, ignoring fenced and inline code."""
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    links: list[tuple[int, str]] = []
    in_fence = False
    for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for name in HTML_ANCHOR.findall(line):
            anchors.add(name)
        m = HEADING.match(line)
        if m:
            base = slugify(m.group(2))
            n = seen.get(base, 0)
            seen[base] = n + 1
            anchors.add(base if n == 0 else f"{base}-{n}")
        bare = CODE_SPAN.sub("", line)
        for target in INLINE_LINK.findall(bare) + REF_DEF.findall(bare) + HTML_ATTR.findall(bare):
            links.append((no, target.strip("<>")))
    return anchors, links


def check_links(root: Path, rep: Report) -> tuple[int, int, int]:
    md_files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in ("node_modules", "__pycache__"))
        md_files.extend(Path(dirpath) / f for f in sorted(filenames) if f.endswith(".md"))
    if not md_files:
        rep.err(str(root), "no .md files found")
        return 0, 0, 0
    cache: dict[Path, tuple[set[str], list[tuple[int, str]]]] = {}

    def info(p: Path) -> tuple[set[str], list[tuple[int, str]]]:
        if p not in cache:
            cache[p] = scan_markdown(p)
        return cache[p]

    n_links = n_anchors = 0
    root_res = root.resolve()
    for md in md_files:
        rel = md.relative_to(root)
        for no, target in info(md)[1]:
            if not target or SCHEME.match(target) or target.startswith("//"):
                continue
            n_links += 1
            path_part, _, anchor = target.partition("#")
            path_part = unquote(path_part)
            dest = md if not path_part else (md.parent / path_part)
            where = f"{rel}:{no}"
            try:
                dest_res = dest.resolve()
                dest_res.relative_to(root_res)
            except ValueError:
                rep.err(where, f"link '{target}' leaves the checked tree")
                continue
            if not dest_res.exists():
                rep.err(where, f"link '{target}' points to a missing path")
                continue
            if anchor:
                if dest_res.is_file() and dest_res.suffix == ".md":
                    n_anchors += 1
                    if unquote(anchor) not in info(dest_res)[0]:
                        rep.err(where, f"anchor '#{anchor}' not found in {dest_res.relative_to(root_res)}")
    return len(md_files), n_links, n_anchors


def check_ledger(root: Path, rep: Report) -> int:
    path = root / LEDGER
    if not path.is_file():
        rep.err(LEDGER, "missing")
        return 0
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            rep.err(LEDGER, "empty file")
            return 0
        if header != HEADER:
            rep.err(f"{LEDGER}:1", f"header {header} != expected {HEADER}")
            return 0
        ids: set[str] = set()
        n = 0
        for row in reader:
            line = reader.line_num
            if not any(cell.strip() for cell in row):
                continue
            n += 1
            where = f"{LEDGER}:{line}"
            if len(row) != len(HEADER):
                rep.err(where, f"{len(row)} fields, expected {len(HEADER)}")
                continue
            r = dict(zip(HEADER, row))
            rid = r["id"]
            where = f"{LEDGER}:{line} ({rid})"
            if not re.fullmatch(r"VS-\d{3}", rid):
                rep.err(where, f"id '{rid}' is not VS-NNN")
            if rid in ids:
                rep.err(where, f"duplicate id '{rid}'")
            ids.add(rid)
            if r["violated_spec"] not in PILLARS:
                rep.err(where, f"violated_spec '{r['violated_spec']}' is not one of {PILLARS}")
            if r["method"] not in METHODS:
                rep.err(where, f"method '{r['method']}' is not one of {METHODS}")
            for shell in SHELL_MODELS:
                if r["method"] == "model_check" and any(shell in r[k] for k in ("checker", "evidence")):
                    rep.err(where, f"cites shell model {shell} but method is model_check")
            hv = r["human_verifier"]
            if hv.startswith("@"):
                if not HANDLE.fullmatch(hv):
                    rep.err(where, f"human_verifier '{hv}' is not a single @github_handle")
                elif not REAL_ENGINE.search(r["evidence"]):
                    rep.err(where, f"human_verifier {hv} but the evidence states no real-engine run")
            elif hv != "In Progress":
                rep.err(where, f"human_verifier '{hv}' is neither 'In Progress' nor an @github_handle")
    if n == 0:
        rep.err(LEDGER, "no data rows")
    return n


def table_names(text: str, start: str, cell: re.Pattern[str]) -> list[str]:
    """Names in the first cell of each row of the first table after the line starting with `start`."""
    names: list[str] = []
    lines = text.splitlines()
    idx = next((i for i, l in enumerate(lines) if l.startswith(start)), None)
    if idx is None:
        return names
    in_table = False
    for l in lines[idx + 1:]:
        if l.startswith("|"):
            in_table = True
            m = cell.match(l)
            if m:
                names.append(m.group(1))
        elif in_table:
            break
    return names


def check_vocabularies(root: Path, rep: Report) -> None:
    readme = root / "bugs/README.md"
    if readme.is_file():
        got = table_names(readme.read_text(encoding="utf-8"), "## Formal Specification Pillars",
                          re.compile(r"^\|\s*\*\*`([A-Za-z]+)`\*\*\s*\|"))
        if got != PILLARS:
            rep.err("bugs/README.md", f"pillar table lists {got}, expected {PILLARS}")
    else:
        rep.err("bugs/README.md", "missing")
    gate = root / "docs/exposure-gate.md"
    if gate.is_file():
        got = table_names(gate.read_text(encoding="utf-8"), "## Method classes",
                          re.compile(r"^\|\s*`([a-z_]+)`\s*\|"))
        if got != METHODS:
            rep.err("docs/exposure-gate.md", f"method table lists {got}, expected {METHODS}")
    else:
        rep.err("docs/exposure-gate.md", "missing")
    sync = root / "scripts/sync_bugs_sheet.py"
    if sync.is_file():
        m = re.search(r"^SPEC_STYLE = \{(.*?)^\}", sync.read_text(encoding="utf-8"), re.S | re.M)
        got = re.findall(r'^\s*"([A-Za-z]+)":', m.group(1), re.M) if m else []
        if sorted(got) != sorted(PILLARS):
            rep.err("scripts/sync_bugs_sheet.py", f"SPEC_STYLE keys {got} differ from {PILLARS}")
    else:
        rep.err("scripts/sync_bugs_sheet.py", "missing")


def check_versions(root: Path, rep: Report, expect: str | None) -> str | None:
    found: dict[str, str] = {}
    for name in VERSION_FILES:
        path = root / name
        if not path.is_file():
            rep.err(name, "missing version manifest")
            continue
        text = path.read_text(encoding="utf-8")
        if name.endswith(".toml"):
            if tomllib is not None:
                try:
                    version = tomllib.loads(text).get("project", {}).get("version")
                except tomllib.TOMLDecodeError as exc:
                    rep.err(name, f"invalid TOML: {exc}")
                    continue
            else:  # Python 3.10: the [project] table's own version line
                m = re.search(r'^\[project\]\n(?:(?!^\[).*\n)*?^version\s*=\s*"([^"]+)"', text, re.M)
                version = m.group(1) if m else None
            if version:
                found[name] = str(version)
            else:
                rep.err(name, "no [project] version")
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            rep.err(name, f"invalid JSON: {exc}")
            continue
        if "plugins" in data:
            for i, p in enumerate(data.get("plugins", [])):
                found[f"{name}#plugins[{i}]"] = str(p.get("version"))
        else:
            found[name] = str(data.get("version"))
    versions = sorted(set(found.values()))
    if len(versions) > 1:
        rep.err("version manifests", "disagree: " + ", ".join(f"{k}={v}" for k, v in found.items()))
    for k, v in found.items():
        if not re.fullmatch(r"\d+\.\d+\.\d+", v):
            rep.err(k, f"version '{v}' is not MAJOR.MINOR.PATCH")
        if expect is not None and v != expect:
            rep.err(k, f"version {v} != expected {expect}")
    return versions[0] if len(versions) == 1 else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--links-only", action="store_true", help="check links and anchors only")
    parser.add_argument("--expect-version", help="also require this version in every manifest")
    args = parser.parse_args()
    root = args.root
    if not root.is_dir():
        print(f"check-docs: no such directory {root}", file=sys.stderr)
        return 2
    rep = Report()
    n_md, n_links, n_anchors = check_links(root, rep)
    summary = f"{n_md} .md files, {n_links} local links, {n_anchors} anchors"
    if not args.links_only:
        n_rows = check_ledger(root, rep)
        check_vocabularies(root, rep)
        version = check_versions(root, rep, args.expect_version)
        shown = f"version {version}" if version else "no single version"
        summary += f"; ledger {n_rows} rows; {shown} in {len(VERSION_FILES)} manifests"
    for e in rep.errors:
        print(e)
    if rep.errors:
        noun = "error" if len(rep.errors) == 1 else "errors"
        print(f"check-docs: FAIL ({len(rep.errors)} {noun}; {summary})")
        return 1
    print(f"check-docs: OK ({summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
