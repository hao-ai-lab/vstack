#!/usr/bin/env python3
"""Exercise the gate runner of vstack_cli.py where a gate is not a plain script.

The input of an outside review of 0.125.0: 'vstack gate tlc-verdict LOG RC' ran a file that only defines shell
functions, so it printed nothing and exited 0 for a log with a violation."""

from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CLI = HERE.parents[2] / 'vstack_cli.py'
checks = 0


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def invoke(*args, code, contains=(), label=''):
    global checks
    result = subprocess.run([sys.executable, '-B', str(CLI), *map(str, args)], capture_output=True, text=True,
                            timeout=30)
    output = result.stdout + result.stderr
    require(result.returncode == code, f'{label}: expected exit {code}, got {result.returncode}: {output}')
    for fragment in contains:
        require(fragment in output, f'{label}: missing {fragment!r} in {output}')
    checks += 1
    return output


def main():
    with tempfile.TemporaryDirectory(prefix='vstack-cli-') as directory:
        scratch = Path(directory)
        violation = scratch / 'violation.log'
        violation.write_text('Error: Invariant Safety is violated.\n')
        passing = scratch / 'pass.log'
        passing.write_text('Model checking completed. No error has been found.\n')
        invoke('gate', 'tlc-verdict', violation, 1, code=1, contains=('VIOLATION:Safety',), label='violation')
        invoke('gate', 'tlc-verdict', passing, 0, code=0, contains=('PASS',), label='pass')
        invoke('gate', 'tlc-verdict', passing, 124, code=1, contains=('TIMEOUT',), label='timeout')
        invoke('gate', 'tlc-verdict', passing, code=2, contains=('usage: vstack gate tlc-verdict',), label='usage')
    print(f'PASS vstack_cli: {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
