#!/usr/bin/env python3
"""Freeze a read-only copy of the toolkit's scripts and templates at one commit, so that running tasks keep using
the version they started with while the live worktree changes.

  freeze_tools.py DEST --rev REV [--root ROOT] [--path P ...]   copy the files of commit REV
  freeze_tools.py DEST --tree [--root ROOT] [--path P ...]      copy the working files (marked as such)
  freeze_tools.py --verify DEST [--root ROOT]                   check a frozen copy

The copy holds the files under each --path (default: scripts and templates), FREEZE.sha256 (sha256sum format,
one line per file) and FREEZE.txt (source, revision, paths). Files become read-only (0444, or 0555 when
executable) and so do the directories; the copy is written next to DEST and renamed into place, so DEST is either
absent or complete. Freezing the same content into an existing DEST again is a no-op; different content is
refused, so a running task's copy is never replaced: freeze the new version into a new DEST and name it in new
briefs. A temporary copy left by a run that died is removed by the next run. --verify checks every hash, that no
file was added or removed, that nothing is writable, and with --root that the files still equal the recorded
commit. A brief names DEST/scripts/... and DEST/templates/... instead of the live worktree. Read-only marks
the copy; the manifest proves it.
"""

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time

MANIFEST = "FREEZE.sha256"
INFO = "FREEZE.txt"
DEFAULT_PATHS = ("scripts", "templates")
SKIP = {"__pycache__"}
LINE = re.compile(r"([0-9a-f]{64})  (.+)")


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"ERROR arguments: {message}\n")


class Failure(Exception):
    pass


def git(root, *args, data=None):
    try:
        return subprocess.run(["git", "-c", "core.quotepath=off", "-C", str(root), *args], input=data,
                              capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as exc:
        raise Failure(f"git {args[0]} failed: {exc.stderr.decode(errors='replace').strip()}") from None


def files_at_rev(root, rev, paths):
    """{path: (bytes, executable)} of the blobs under paths at commit rev, and the commit id."""
    if rev.startswith("-"):
        raise Failure(f"--rev {rev!r}: expected a commit")
    try:
        commit = git(root, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").decode().strip()
    except Failure:
        raise Failure(f"--rev {rev}: not a commit of {root}") from None
    listing = git(root, "ls-tree", "-r", "-z", "--full-tree", commit, "--", *paths).decode("utf-8", "surrogateescape")
    entries = []
    for item in filter(None, listing.split("\0")):
        meta, path = item.split("\t", 1)
        mode, kind, sha = meta.split()
        if kind != "blob" or mode == "120000":
            raise Failure(f"{path} at {commit[:12]} is a {'symbolic link' if mode == '120000' else kind}; "
                          "only regular files are frozen")
        entries.append((path, sha, mode == "100755"))
    data = git(root, "cat-file", "--batch", data="".join(f"{sha}\n" for _, sha, _ in entries).encode())
    files, pos = {}, 0
    for path, sha, executable in entries:
        end = data.index(b"\n", pos)
        size = int(data[pos:end].split()[2])
        files[path] = (data[end + 1:end + 1 + size], executable)
        pos = end + 1 + size + 1
    return files, commit


def files_in_tree(root, paths):
    files = {}
    for top in paths:
        base = root / top
        if base.is_file():
            candidates = [base]
        else:
            candidates = []
            for here, dirs, names in os.walk(base):
                dirs[:] = sorted(d for d in dirs if d not in SKIP)
                candidates += [Path(here, name) for name in sorted(names) if not name.endswith(".pyc")]
        for path in candidates:
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or not path.is_file():
                raise Failure(f"{rel} is not a regular file; only regular files are frozen")
            files[rel] = (path.read_bytes(), os.access(path, os.X_OK))
    return files


def manifest_text(files):
    return "".join(f"{hashlib.sha256(data).hexdigest()}  {path}\n" for path, (data, _) in sorted(files.items()))


def make_writable(top):
    for here, dirs, names in os.walk(top):
        os.chmod(here, 0o755)
        for name in names:
            path = Path(here, name)
            if not path.is_symlink():
                os.chmod(path, 0o644)


def remove_stale(dest):
    for old in dest.parent.glob(f".{dest.name}.tmp-*"):
        try:
            os.kill(int(old.name.rsplit("-", 1)[1]), 0)
            continue  # its writer is still running
        except ProcessLookupError:
            pass
        except (ValueError, PermissionError):
            continue
        make_writable(old)
        shutil.rmtree(old)
        print(f"removed {old}: left by a run that stopped")


def freeze(dest, files, info):
    if not files:
        raise Failure("no files under the given paths")
    manifest = manifest_text(files)
    if dest.exists() or dest.is_symlink():
        existing = dest / MANIFEST
        if existing.is_file() and existing.read_text(encoding="utf-8") == manifest and not verify(dest):
            return f"OK freeze: {dest} already holds these {len(files)} files; nothing written"
        raise Failure(f"{dest} exists with other content; freeze into a new directory and name it in new briefs")
    remove_stale(dest)
    temp = dest.parent / f".{dest.name}.tmp-{os.getpid()}"
    try:
        for path, (data, executable) in files.items():
            target = temp / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            os.chmod(target, 0o555 if executable else 0o444)
        (temp / MANIFEST).write_text(manifest, encoding="utf-8")
        (temp / INFO).write_text(info, encoding="utf-8")
        for name in (MANIFEST, INFO):
            os.chmod(temp / name, 0o444)
        for here, _, _ in sorted(os.walk(temp), key=lambda item: -len(item[0])):
            os.chmod(here, 0o555)
        os.rename(temp, dest)
    except BaseException:
        if temp.exists():
            make_writable(temp)
            shutil.rmtree(temp)
        raise
    return f"OK freeze: {dest}, {len(files)} files"


def verify(dest, root=None):
    """Problems found in a frozen copy; with root, also compare with the recorded commit."""
    problems = []
    manifest, info = dest / MANIFEST, dest / INFO
    if not manifest.is_file() or not info.is_file():
        return [f"{dest}: not a frozen copy (no {MANIFEST} or {INFO})"]
    listed = {}
    for no, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        match = LINE.fullmatch(line)
        if not match:
            problems.append(f"{manifest}:{no}: not a sha256sum line")
        else:
            listed[match.group(2)] = match.group(1)
    for path, digest in sorted(listed.items()):
        target = dest / path
        if target.is_symlink() or not target.is_file():
            problems.append(f"{path}: missing")
        elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            problems.append(f"{path}: changed since the freeze")
    for here, dirs, names in os.walk(dest):
        for name in dirs + names:
            path = Path(here, name)
            rel = path.relative_to(dest).as_posix()
            if path.lstat().st_mode & 0o222:
                problems.append(f"{rel}: writable")
            if not path.is_dir() and rel not in listed and rel not in {MANIFEST, INFO}:
                problems.append(f"{rel}: not in the manifest")
        if Path(here).lstat().st_mode & 0o222 and Path(here) == dest:
            problems.append(".: writable")
    if root is not None and not problems:
        fields = dict(line.split(": ", 1) for line in info.read_text(encoding="utf-8").splitlines() if ": " in line)
        if fields.get("source") != "commit":
            problems.append(f"{dest}: frozen from a working tree, so there is no commit to compare with")
        else:
            files, _ = files_at_rev(root, fields["revision"], fields["paths"].split())
            if manifest_text(files) != manifest.read_text(encoding="utf-8"):
                problems.append(f"{dest}: differs from commit {fields['revision'][:12]}")
    return problems


def main():
    parser = Parser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1] + (
        "\nExit 0: frozen or verified; 1: refused, a problem found or invalid input; 2: usage."),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dest", type=Path, metavar="DEST", help="the frozen copy (a new directory when freezing)")
    parser.add_argument("--root", type=Path,
                        help="the repository to freeze from (default: this one); with --verify, compare with it")
    how = parser.add_mutually_exclusive_group(required=True)
    how.add_argument("--rev", metavar="REV", help="freeze the files of this commit")
    how.add_argument("--tree", action="store_true", help="freeze the working files (not tied to a commit)")
    how.add_argument("--verify", action="store_true", help="check DEST instead of freezing")
    parser.add_argument("--path", action="append", metavar="P", help="a directory or file to include (repeat)")
    args = parser.parse_args()
    dest = args.dest.absolute()
    root = (args.root or Path(__file__).resolve().parent.parent).resolve()
    try:
        if args.verify:
            problems = verify(dest, root if args.root else None)
            for problem in problems:
                print(f"ERROR {problem}")
            if problems:
                print(f"FAIL freeze: {dest}: {len(problems)} problems")
                return 1
            fields = dict(line.split(": ", 1) for line in (dest / INFO).read_text(encoding="utf-8").splitlines()
                          if ": " in line)
            count = len((dest / MANIFEST).read_text(encoding="utf-8").splitlines())
            print(f"OK freeze: {dest} verified, {count} files of {fields.get('source', '?')} "
                  f"{fields.get('revision', '?')[:12]} unchanged")
            return 0
        paths = args.path or list(DEFAULT_PATHS)
        if any(p.startswith("/") or ".." in Path(p).parts for p in paths):
            raise Failure("--path takes paths relative to the repository root")
        if not dest.parent.is_dir():
            raise Failure(f"{dest.parent}: not a directory")
        if args.rev is not None:
            files, revision = files_at_rev(root, args.rev, paths)
            source = "commit"
        else:
            files, source = files_in_tree(root, paths), "working-tree"
            head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
            revision = (head.stdout.strip() or "none") if head.returncode == 0 else "none"
        info = (f"source: {source}\nrevision: {revision}\nroot: {root.name}\npaths: {' '.join(paths)}\n"
                f"files: {len(files)}\nfrozen: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
        print(freeze(dest, files, info) + f" from {source} {revision[:12]}")
        return 0
    except (Failure, OSError, UnicodeError, ValueError, KeyError) as exc:
        print(f"ERROR {exc}\nFAIL freeze: refused")
        return 1


if __name__ == "__main__":
    sys.exit(main())
