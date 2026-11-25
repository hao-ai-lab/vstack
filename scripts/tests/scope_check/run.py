#!/usr/bin/env python3
"""Exercise scope_check.py on role cards and a stand-in git that prints a fixed status, so no repository is needed.

The first case is the input of an outside review of 0.125.0: a rename out of a path no role may write passed,
because only the destination of the rename was checked."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / 'scope_check.py'
CARD = '---\nname: writer\nwritable:\n  - assigned/output/*\n  - handoff/assigned-role.md\n---\nRole card.\n'
checks = 0


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def invoke(hub, status, *args, code, contains=(), label=''):
    global checks
    (hub.parent / 'status.txt').write_text(status)
    env = dict(os.environ, PATH=f'{hub.parent / "bin"}:{os.environ["PATH"]}', VSTACK_PROJECT_ROOT=str(hub),
               FAKE_STATUS=str(hub.parent / 'status.txt'))
    env.pop('VSTACK_MAIN_GLOBS', None)
    result = subprocess.run([sys.executable, '-B', str(SCRIPT), *args], capture_output=True, text=True, timeout=20,
                            env=env, cwd=hub)
    output = result.stdout + result.stderr
    require(result.returncode == code, f'{label}: expected exit {code}, got {result.returncode}: {output}')
    for fragment in contains:
        require(fragment in output, f'{label}: missing {fragment!r} in {output}')
    checks += 1
    return output


def main():
    with tempfile.TemporaryDirectory(prefix='scope-check-') as directory:
        scratch = Path(directory)
        hub = scratch / 'hub'
        (hub / 'agents').mkdir(parents=True)
        (hub / 'agents' / 'writer.md').write_text(CARD)
        (scratch / 'bin').mkdir()
        git = scratch / 'bin' / 'git'
        git.write_text('#!/usr/bin/bash\n# stand-in for git status --porcelain=v1: print the prepared status\n'
                       'cat "$FAKE_STATUS"\n')
        git.chmod(0o755)
        invoke(hub, 'R  docs/gates.md -> assigned/output/gates.md\n', '--all', code=1,
               contains=('OUT    docs/gates.md', 'agent  assigned/output/gates.md  <- writer', 'outside every scope: 1'),
               label='rename-from-outside')
        invoke(hub, 'R  assigned/output/a.md -> assigned/output/b.md\n', '--all', code=0,
               contains=('outside every scope: 0',), label='rename-inside')
        invoke(hub, ' M handoff/assigned-role.md\n?? assigned/output/new.tsv\n', '--all', code=0,
               contains=('outside every scope: 0',), label='changes-in-scope')
        invoke(hub, ' M README.md\n', '--all', code=1, contains=('OUT    README.md',), label='change-outside')
        invoke(hub, '', 'writer', 'assigned/output/x.tsv', code=0, contains=('ok     assigned/output/x.tsv',),
               label='role-path-allowed')
        invoke(hub, '', 'writer', 'docs/x.md', code=1, contains=('OUT    docs/x.md',), label='role-path-outside')
        invoke(hub, '', code=2, label='usage')
    print(f'PASS scope_check: {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
