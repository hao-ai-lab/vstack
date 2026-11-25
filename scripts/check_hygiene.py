#!/usr/bin/env python3
"""Scan a repository's tracked text files, and optionally every commit of a push range, for non-English text,
personal paths, chat links and stray case data.

Read-only. Rules, each reported as HIT <rule> <where>: <match>:
  cjk            any CJK, kana, Hangul (also decomposed jamo) or full-width character (the repository is English
                 only)
  personal-path  /home/<name> or /Users/<name> (with or without a slash after it), or a Windows profile path (a
                 drive letter, then \\Users\\ or /Users/)
  chat-link      a session, share or artifact link of a chat tool (claude.ai, chatgpt.com, gemini, ...)
  case-data      a data file (.tsv .csv .jsonl .ndjson .log .out .trace .tla .cfg .smt2) outside data/
  private-term   a term from --deny FILE (kept outside the repository: internal case names, hosts, task ids)
  encoding       a text file (no NUL byte) that is not valid UTF-8
Paths themselves are checked for cjk, personal-path, private-term and encoding (a name that is not valid UTF-8).
With --walk, a symbolic link to a directory is scanned as a link (its name and target), not followed. The allow-list (default ROOT/scripts/hygiene-allow.tsv,
header rule<TAB>path<TAB>reason) excuses hits of one rule in files matching a glob (fnmatch; * spans /); every
entry needs a reason and must excuse at least one hit of a rule that ran. The allow-list itself is not case data.

--commits BASE..HEAD also scans what a push of that range publishes: every file version that a commit of the range
adds or changes (also when a later commit of the range cleans or deletes it again) and every commit message. Such
hits read HIT <rule> <commit>:<path>:<line> or HIT <rule> <commit> message:<line>; allow entries apply to file
versions by path, never to messages. A range with no commits is an error, so a reversed or mistyped range fails.
"""

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

CJK = re.compile("[\u1100-\u11ff\u2e80-\u2fdf\u3000-\u33ff\u3400-\u4dbf\u4e00-\u9fff\ua960-\ua97f\uac00-\ud7ff"
                 "\uf900-\ufaff\ufe30-\ufe4f\uff00-\uffef\U00020000-\U0003ffff]+")
PERSONAL = re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+/?|\b[A-Za-z]:[\\/]+Users[\\/]+", re.I)
CHAT = re.compile(
    r"\b(?:claude\.ai/(?:chat|share|artifact|project|code/session_|code/artifact)"
    r"|(?:chatgpt\.com|chat\.openai\.com)/(?:c|g|share)/"
    r"|gemini\.google\.com/(?:app|share|gem)|g\.co/gemini/share"
    r"|aistudio\.google\.com/(?:app/)?prompts|copilot\.microsoft\.com/shares?/"
    r"|poe\.com/s/|perplexity\.ai/search/|cursor\.com/(?:agents|background-agent))[^\s)\"'>]*", re.I)
DATA_SUFFIXES = {".tsv", ".csv", ".jsonl", ".ndjson", ".log", ".out", ".trace", ".tla", ".cfg", ".smt2"}
DATA_DIR = "data/"
RULES = ["cjk", "personal-path", "chat-link", "case-data", "private-term", "encoding"]
ALLOW_HEADER = ["rule", "path", "reason"]
NO_OBJECT = "0" * 40
GITLINK = "160000"


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"ERROR arguments: {message}\n")


def git(root, *args, data=None):
    cmd = ["git", "-c", "core.quotepath=off", "-C", str(root), *args]
    return subprocess.run(cmd, input=data, capture_output=True, check=True).stdout


def list_files(root, walk, untracked):
    if walk:
        found = []
        for base, dirs, files in os.walk(root):
            # A symbolic link to a directory is listed among dirs and not followed; scan it as a link, as Git does.
            links = [d for d in dirs if os.path.islink(os.path.join(base, d))]
            dirs[:] = sorted(d for d in dirs if d != ".git" and d not in links)
            found += [Path(base, name).relative_to(root).as_posix() for name in sorted(files + links)]
        return found
    args = ["ls-files", "-z", "--cached"] + (["--others", "--exclude-standard"] if untracked else [])
    out = git(root, *args)
    return sorted({name for name in out.decode("utf-8", "surrogateescape").split("\0") if name})


def read_objects(root, shas):
    """Raw contents of git objects by id, read with one cat-file --batch call."""
    if not shas:
        return {}
    data = git(root, "cat-file", "--batch", data="".join(f"{sha}\n" for sha in shas).encode())
    contents, pos = {}, 0
    for sha in shas:
        end = data.index(b"\n", pos)
        header = data[pos:end].decode().split()
        if len(header) != 3:
            raise ValueError(f"object {sha} is missing from the repository")
        size = int(header[2])
        contents[sha] = data[end + 1:end + 1 + size]
        pos = end + 1 + size + 1
    return contents


def list_commits(root, spec):
    """Commits of the range, oldest first; every (commit, path, blob) the range adds or changes; raw commits."""
    if spec.startswith("-") or not spec.strip():
        raise ValueError(f"--commits {spec!r}: expected a revision range such as origin/main..HEAD")
    commits = git(root, "rev-list", "--reverse", spec, "--").decode().split()
    if not commits:
        raise ValueError(f"--commits {spec}: the range has no commits; check that it reads BASE..HEAD with "
                         "BASE the remote branch the push goes to")
    versions, seen = [], set()
    for commit in commits:
        out = git(root, "diff-tree", "-r", "-z", "--no-renames", "--no-commit-id", "--root", "-m", commit)
        fields = out.decode("utf-8", "surrogateescape").split("\0")
        for meta, path in zip(fields[0::2], fields[1::2]):
            parts = meta.lstrip(":").split()
            if len(parts) != 5:
                continue
            _, mode, _, blob, status = parts
            if status.startswith("D") or blob == NO_OBJECT or mode == GITLINK or (path, blob) in seen:
                continue
            seen.add((path, blob))
            versions.append((commit, path, blob))
    return commits, versions, read_objects(root, commits)


def load_deny(path):
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        terms.append(re.compile(line[3:] if line.startswith("re:") else re.escape(line), re.I))
    if not terms:
        raise ValueError(f"{path}: no deny terms")
    return terms


def load_allow(path):
    entries, errors = [], []
    lines = [(no, line) for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
             if line.strip() and not line.lstrip().startswith("#")]
    if not lines or lines[0][1].split("\t") != ALLOW_HEADER:
        return [], [f"ERROR {path}: header must be {' '.join(ALLOW_HEADER)} (tab-separated)"]
    for no, line in lines[1:]:
        cells = [cell.strip() for cell in line.split("\t")]
        if len(cells) != 3:
            errors.append(f"ERROR {path}:{no}: expected 3 columns, found {len(cells)}")
        elif cells[0] not in RULES:
            errors.append(f"ERROR {path}:{no}: unknown rule {cells[0]!r}")
        elif not cells[1] or not cells[2]:
            errors.append(f"ERROR {path}:{no}: every allow entry needs a path glob and a reason")
        else:
            entries.append({"line": no, "rule": cells[0], "glob": cells[1], "used": 0})
    return entries, errors


def printable(text):
    """Text with the undecodable bytes of a file name shown as escapes, so that printing it cannot fail."""
    return text.encode("utf-8", "backslashreplace").decode("utf-8")


def scan_name(name, deny=()):
    """Yield (rule, None, match) for the path of a file."""
    for rule, pattern in [("cjk", CJK), ("personal-path", PERSONAL)] + [("private-term", term) for term in deny]:
        match = pattern.search(name)
        if match:
            yield rule, None, f"file name: {match.group(0)}"
            if rule == "private-term":
                break
    if any("\udc80" <= char <= "\udcff" for char in name):
        yield "encoding", None, "file name is not valid UTF-8"
    if Path(name).suffix.lower() in DATA_SUFFIXES and not name.startswith(DATA_DIR):
        yield "case-data", None, f"{Path(name).suffix} file outside {DATA_DIR}"


def scan_lines(lines, deny):
    patterns = [("cjk", CJK), ("personal-path", PERSONAL), ("chat-link", CHAT)]
    patterns += [("private-term", term) for term in deny]
    for no, line in enumerate(lines, 1):
        found = set()
        for rule, pattern in patterns:
            match = pattern.search(line)
            if match and rule not in found:
                found.add(rule)
                yield rule, no, match.group(0)[:80]


def scan_bytes(data, deny):
    """Yield (rule, line, match) for the content of one file; binary content (a NUL byte) is skipped."""
    if b"\0" in data:
        return
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        yield "encoding", data[:exc.start].count(b"\n") + 1, "not valid UTF-8"
        return
    yield from scan_lines(lines, deny)


def scan_file(root, name, deny):
    """Yield (rule, line or None, match) for one file of the tree."""
    yield from scan_name(name, deny)
    path = root / name
    if path.is_symlink():
        yield from scan_lines([os.readlink(path)], deny)
    elif path.is_file():
        yield from scan_bytes(path.read_bytes(), deny)


def scan_message(raw, deny):
    """Yield (rule, line, match) for the message of a raw commit object (headers skipped)."""
    _, _, message = raw.partition(b"\n\n")
    yield from scan_bytes(message, deny)


def main():
    parser = Parser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n", 1)[1] + (
        "\nFiles come from 'git ls-files' (add --untracked for files not yet added, --walk for a tree without Git); "
        "files with a NUL byte are binary and skipped. Run it with --commits on the range a push publishes, for "
        "example --commits origin/main..HEAD; a clean tree says nothing about older versions in the history. "
        "Exit 0: no hits; 1: hits or invalid input; 2: usage."),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parent.parent, metavar="ROOT")
    parser.add_argument("--allow", type=Path, metavar="FILE",
                        help="allow-list (default ROOT/scripts/hygiene-allow.tsv)")
    parser.add_argument("--deny", type=Path, metavar="FILE", help="private terms, one per line; 're:' starts a regex")
    parser.add_argument("--walk", action="store_true", help="walk the directory instead of asking Git for the files")
    parser.add_argument("--untracked", action="store_true", help="also scan untracked files that are not ignored")
    parser.add_argument("--commits", metavar="BASE..HEAD",
                        help="also scan every file version and message of the commits in this range")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        print(f"ERROR {root}: not a directory\nFAIL hygiene: 1 errors")
        return 1
    errors = []
    allow_path = args.allow or root / "scripts" / "hygiene-allow.tsv"
    entries, commits, versions, raw = [], [], [], {}
    try:
        if args.allow or allow_path.is_file():
            entries, errors = load_allow(allow_path)
        deny = load_deny(args.deny) if args.deny else []
        files = list_files(root, args.walk, args.untracked)
        if args.commits is not None:
            commits, versions, raw = list_commits(root, args.commits)
            raw.update(read_objects(root, [blob for _, _, blob in versions]))
    except (OSError, UnicodeError, ValueError, re.error) as exc:
        print(f"ERROR {exc}\nFAIL hygiene: 1 errors")
        return 1
    except subprocess.CalledProcessError as exc:
        reason = exc.stderr.decode(errors="replace").strip()
        hint = "" if args.commits is not None else "; use --walk"
        print(f"ERROR {root}: git {exc.cmd[5] if len(exc.cmd) > 5 else ''} failed ({reason}){hint}\n"
              "FAIL hygiene: 1 errors")
        return 1
    if not files:
        print(f"ERROR {root}: no files to scan\nFAIL hygiene: 1 errors")
        return 1
    ran = set(RULES) - (set() if deny else {"private-term"})
    hits, allowed, hit_places = {rule: 0 for rule in RULES}, 0, set()
    try:
        allow_name = allow_path.resolve().relative_to(root).as_posix()
    except ValueError:
        allow_name = None

    def report(name, where, results, excusable=True):
        nonlocal allowed
        for rule, line, text in results:
            if rule == "case-data" and name == allow_name:
                continue  # the allow-list is configuration, not case data
            excuse = excusable and next((e for e in entries if e["rule"] == rule and fnmatch.fnmatch(name, e["glob"])),
                                        None)
            if excuse:
                excuse["used"] += 1
                allowed += 1
                continue
            hits[rule] += 1
            hit_places.add(where)
            print(printable(f"HIT {rule} {where}{':' + str(line) if line else ''}: {text}"))

    for name in files:
        try:
            report(name, name, list(scan_file(root, name, deny)))
        except OSError as exc:
            errors.append(f"ERROR {name}: {exc}")
    for commit, name, blob in versions:
        where = f"{commit[:12]}:{name}"
        report(name, where, list(scan_name(name, deny)) + list(scan_bytes(raw[blob], deny)))
    for commit in commits:
        report("", f"{commit[:12]} message", list(scan_message(raw[commit], deny)), excusable=False)
    for entry in entries:
        if entry["rule"] in ran and not entry["used"]:
            errors.append(f"ERROR {allow_path}:{entry['line']}: allow entry {entry['rule']} {entry['glob']} "
                          "excuses no hit; remove it")
    for message in errors:
        print(printable(message))
    total = sum(hits.values())
    counts = ", ".join(f"{rule} {hits[rule]}" for rule in RULES if rule in ran)
    skipped = "" if deny else " (private-term not run: no --deny)"
    scope = f"{len(files)} files"
    if args.commits is not None:
        scope = f"{len(commits)} commits, {len(versions)} file versions, {scope}"
    # The summary keeps its last word fixed (allowed / files) so a brief can match it with 'last line ends with'.
    if total or errors:
        print(f"FAIL hygiene: {total} hits in {len(hit_places)} places ({counts}){skipped}; {allowed} allowed; "
              f"{len(errors)} errors; {scope}")
        return 1
    print(f"OK hygiene: {scope}, 0 hits{skipped}; {allowed} allowed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
