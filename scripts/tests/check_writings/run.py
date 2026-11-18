#!/usr/bin/env python3
"""Exercise check_writings.py on two writings, a good compare table, bad compare rows one at a time and edits."""

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / 'check_writings.py'
ROOT = HERE.parents[2]
checks = 0

BAD = {
    'bad-relation': 'relation must be one of', 'only-both': 'only_here needs exactly one of row_a and row_b',
    'same-one-side': 'same needs both row_a and row_b', 'unknown-row': 'row_a A-99 is not a row of writing A',
    'bad-contra': 'contradiction must be yes or no', 'contra-no-right': 'a contradiction needs who_is_right',
    'right-without-contra': 'who_is_right is only filled for a contradiction',
    'only-contra': 'a row found on one side only cannot contradict the other', 'duplicate-pair': 'pair listed twice',
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def invoke(*args, code, contains=(), label='', exact=None):
    global checks
    result = subprocess.run([sys.executable, '-B', str(SCRIPT), *map(str, args)],
                            capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    require(result.returncode == code, f'{label or args}: expected exit {code}, got {result.returncode}: {output}')
    for fragment in contains:
        require(fragment in output, f'{label or args}: missing {fragment!r} in {output}')
    if exact is not None:
        require(result.stdout == exact, f'{label}: stdout {result.stdout!r}, expected {exact!r}')
    if code == 1:
        require(output.splitlines()[-1].startswith('FAIL writings: '), f'{label}: last line is not FAIL: {output}')
    checks += 1
    return output


def main():
    names = ('a.tsv', 'b.tsv', 'good.tsv', 'bad.tsv')
    before = [hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in names]
    a, b, good = HERE / 'a.tsv', HERE / 'b.tsv', HERE / 'good.tsv'
    header, *rows = good.read_text().splitlines(keepends=True)
    bad = [line for line in (HERE / 'bad.tsv').read_text().splitlines(keepends=True)[1:] if line.strip()]
    require(sorted(line.rstrip('\n').split('\t')[5].removeprefix('case:') for line in bad) == sorted(BAD),
            'bad.tsv rows and expectations differ')
    invoke('--help', code=0, contains=('only_here',))
    invoke(good, code=2, contains=('ERROR arguments:',), label='writings-required')
    summary = 'OK writings: A 4 rows, B 5 rows, 6 compare rows (narrower 1, only_here 2, overlap 1, same 2); 1 contradictions'
    invoke(good, '--a', a, '--b', b, code=0, exact=summary + '\n', label='good')
    invoke(good, '--a', a, '--b', b, '--base', 'a', code=0, label='base-a', exact=(
        'GRAFT b:B-02 broader than a:A-02\n'
        'GRAFT b:B-05 overlaps a:A-02; merge the extra part by hand\n'
        'GRAFT b:B-03 replaces a:A-03\n'
        'GRAFT b:B-04 only in this writing\n' + summary + '; base a, 4 grafts\n'))
    invoke(good, '--a', a, '--b', b, '--base', 'b', code=0, label='base-b', exact=(
        'GRAFT a:A-02 overlaps b:B-05; merge the extra part by hand\n'
        'GRAFT a:A-04 only in this writing\n' + summary + '; base b, 2 grafts\n'))
    invoke(good, '--a', a, '--b', b, '--id-column', 'id', code=0, label='id-column')
    invoke(good, '--a', a, '--b', b, '--id-column', 'writer', code=1, contains=('duplicate id worker',),
           label='id-column-writer')
    invoke(good, '--a', a, '--b', b, '--id-column', 'absent', code=1, contains=("no column 'absent'",))
    invoke(ROOT / 'templates' / 'writing-compare.tsv', '--a', a, '--b', b, code=1,
           contains=('row A-01 of writing A is not in the compare table',), label='template-header')
    with tempfile.TemporaryDirectory(prefix='check-writings-') as directory:
        scratch = Path(directory)
        table = scratch / 'compare.tsv'
        for line in bad:
            table.write_text(header + ''.join(rows) + line)
            name = line.rstrip('\n').split('\t')[5].removeprefix('case:')
            invoke(table, '--a', a, '--b', b, code=1, contains=(BAD[name],), label=name)
        table.write_text(header + ''.join(rows).replace('\tb\tsrc/transfer.py:77 rejects a stale generation', '\tb\t'))
        invoke(table, '--a', a, '--b', b, code=1, contains=('needs a note naming the code',), label='contra-no-note')
        table.write_text(header + ''.join(row for row in rows if not row.startswith('A-04')))
        invoke(table, '--a', a, '--b', b, code=1, contains=('row A-04 of writing A is not in the compare table',))
        table.write_text(header + ''.join(row for row in rows if not row.startswith('\tB-04')))
        invoke(table, '--a', a, '--b', b, code=1, contains=('row B-04 of writing B is not in the compare table',))
        table.write_text(header.replace('who_is_right', 'winner') + ''.join(rows))
        invoke(table, '--a', a, '--b', b, code=1, contains=('header must be',), label='bad-header')
        table.write_text(header + ''.join(rows) + 'A-01\tB-05\tsame\n')
        invoke(table, '--a', a, '--b', b, code=1, contains=('expected 6 columns, found 3',))
        duplicate = scratch / 'a.tsv'
        duplicate.write_text(a.read_text() + 'A-01\tallocator\tsrc/pool.py:50\tnone\n')
        invoke(good, '--a', duplicate, '--b', b, code=1, contains=('duplicate id A-01',))
        duplicate.write_text('id\twriter\n')
        invoke(good, '--a', duplicate, '--b', b, code=1, contains=('writing has no rows',))
        invoke(good, '--a', scratch / 'absent.tsv', '--b', b, code=1, contains=('ERROR',), label='absent-writing')
    after = [hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in names]
    require(before == after, 'a fixture changed')
    print(f'PASS check_writings: {len(rows)} good compare rows, {len(bad)} bad rows, {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
