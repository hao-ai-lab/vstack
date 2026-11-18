#!/usr/bin/env python3
"""Exercise freeze_tools.py on a generated repository.

The repository repeats a mistake seen in use: while two tasks used the finding template and grader of the live
worktree, a third task changed both to a new column layout, and one task's records were refused by the new grader.
With a frozen copy the running tasks keep the version they started with."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'lib'))
from gitrepo import Repo  # noqa: E402
SCRIPT = HERE.parents[1] / 'freeze_tools.py'
checks = 0
OLD = {
    'scripts/grade.py': 'COLUMNS = 32\n',
    'scripts/run.sh': ('exec', '#!/bin/sh\necho run\n'),
    'templates/record.tsv': 'a\tb\n',
    'docs/notes.md': 'Notes.\n',
}
NEW = {**OLD, 'scripts/grade.py': 'COLUMNS = 35\n', 'templates/record.tsv': 'a\tb\tc\n'}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def invoke(*args, code, contains=(), label=''):
    global checks
    result = subprocess.run([sys.executable, '-B', str(SCRIPT), *map(str, args)],
                            capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    require(result.returncode == code, f'{label or args}: expected exit {code}, got {result.returncode}: {output}')
    for fragment in contains:
        require(fragment in output, f'{label or args}: missing {fragment!r} in {output}')
    if code in (0, 1) and '--help' not in args:
        last = output.splitlines()[-1]
        require(last.startswith('OK freeze: ' if code == 0 else 'FAIL freeze: '), f'{label}: last line {last!r}')
    checks += 1
    return output


def writable(top):
    for here, _, names in os.walk(top):
        os.chmod(here, 0o755)
        for name in names:
            os.chmod(Path(here, name), 0o644)


def main():
    invoke('--help', code=0, contains=('FREEZE.sha256',))
    invoke('dest', code=2, contains=('ERROR arguments:',), label='no-mode')
    scratch = Path(tempfile.mkdtemp(prefix='freeze-tools-'))
    try:
        repo_dir = scratch / 'repo'
        repo = Repo(repo_dir)
        old = repo.commit(OLD, 'tools: 32 columns')
        repo.checkout_files(OLD)
        frozen = scratch / 'frozen-old'
        invoke(frozen, '--root', repo_dir, '--rev', old, code=0, contains=('OK freeze: ', ', 3 files from commit '),
               label='freeze')
        require(sorted(p.relative_to(frozen).as_posix() for p in frozen.rglob('*') if p.is_file()) ==
                ['FREEZE.sha256', 'FREEZE.txt', 'scripts/grade.py', 'scripts/run.sh', 'templates/record.tsv'],
                'frozen files differ from scripts and templates of the commit')
        manifest = (frozen / 'FREEZE.sha256').read_text()
        digest = hashlib.sha256(OLD['scripts/grade.py'].encode()).hexdigest()
        require(f'{digest}  scripts/grade.py\n' in manifest, 'manifest line of grade.py')
        require(f'revision: {old}\n' in (frozen / 'FREEZE.txt').read_text(), 'FREEZE.txt names the commit')
        modes = {p.name: p.stat().st_mode & 0o777 for p in frozen.rglob('*')}
        require(modes['run.sh'] == 0o555 and modes['grade.py'] == 0o444 and modes['scripts'] == 0o555
                and frozen.stat().st_mode & 0o777 == 0o555, f'modes {modes}')
        invoke('--verify', frozen, code=0, contains=('verified, 3 files of commit', 'unchanged'), label='verify')
        invoke('--verify', frozen, '--root', repo_dir, code=0, label='verify-against-commit')
        # The live tree moves on; the frozen copy keeps the version the running tasks started with.
        new = repo.commit(NEW, 'tools: 35 columns')
        require((frozen / 'scripts' / 'grade.py').read_text() == 'COLUMNS = 32\n', 'frozen copy followed the tree')
        invoke('--verify', frozen, '--root', repo_dir, code=0, label='verify-after-the-tree-moved')
        invoke(frozen, '--root', repo_dir, '--rev', old, code=0, contains=('already holds these 3 files',),
               label='refreeze-same')
        invoke(frozen, '--root', repo_dir, '--rev', new, code=1, contains=('exists with other content',),
               label='refreeze-other')
        require((frozen / 'scripts' / 'grade.py').read_text() == 'COLUMNS = 32\n', 'refused freeze changed the copy')
        invoke(scratch / 'frozen-new', '--root', repo_dir, '--rev', 'main', code=0, label='freeze-new-version')
        invoke(scratch / 'frozen-docs', '--root', repo_dir, '--rev', new, '--path', 'docs', code=0,
               contains=(', 1 files',), label='freeze-path')
        invoke(scratch / 'frozen-tree', '--root', repo_dir, '--tree', code=0, contains=('from working-tree',),
               label='freeze-tree')
        invoke('--verify', scratch / 'frozen-tree', '--root', repo_dir, code=1,
               contains=('frozen from a working tree',), label='verify-tree-against-commit')
        # Tampering is found.
        copy = scratch / 'tampered'
        shutil.copytree(frozen, copy, symlinks=True)
        writable(copy)
        (copy / 'templates' / 'record.tsv').write_text('a\tb\tc\n')
        (copy / 'scripts' / 'extra.py').write_text('x = 1\n')
        (copy / 'scripts' / 'run.sh').unlink()
        invoke('--verify', copy, code=1, contains=('templates/record.tsv: changed since the freeze',
                                                   'scripts/extra.py: not in the manifest', 'scripts/run.sh: missing',
                                                   'scripts: writable'), label='verify-tampered')
        invoke('--verify', scratch / 'repo', code=1, contains=('not a frozen copy',), label='verify-not-frozen')
        # Refusals and recovery from a run that died.
        invoke(scratch / 'x', '--root', repo_dir, '--rev', 'nosuch', code=1, contains=('not a commit',),
               label='bad-rev')
        invoke(scratch / 'y', '--root', repo_dir, '--rev', new, '--path', 'absent', code=1,
               contains=('no files under the given paths',), label='absent-path')
        invoke(scratch / 'y', '--root', repo_dir, '--rev', new, '--path', '../repo', code=1,
               contains=('relative to the repository root',), label='escaping-path')
        invoke(scratch / 'no' / 'such' / 'dest', '--root', repo_dir, '--rev', new, code=1,
               contains=('not a directory',), label='absent-parent')
        stale = scratch / '.frozen-z.tmp-99999999'
        (stale / 'scripts').mkdir(parents=True)
        (stale / 'scripts' / 'half.py').write_text('partial\n')
        os.chmod(stale / 'scripts', 0o555)
        invoke(scratch / 'frozen-z', '--root', repo_dir, '--rev', new, code=0,
               contains=('left by a run that stopped',), label='stale-temp')
        require(not stale.exists(), 'stale temporary copy kept')
        linked = Repo(scratch / 'linked')
        linked.commit({'scripts/a.py': 'x\n', 'scripts/b.py': ('link', 'a.py')}, 'a link')
        invoke(scratch / 'frozen-link', '--root', scratch / 'linked', '--rev', 'main', code=1,
               contains=('symbolic link',), label='symlink-refused')
        require(not (scratch / 'frozen-link').exists(), 'a refused freeze left a copy')
    finally:
        writable(scratch)
        shutil.rmtree(scratch)
    print(f'PASS freeze_tools: {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
