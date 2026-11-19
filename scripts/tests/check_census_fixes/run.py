#!/usr/bin/env python3
"""Exercise check_census_fixes.py on a generated resource matrix, source tree and correction records.

The first two corrections repeat what a second reading found in use: a shared-memory ring recorded under the
subsystem that only passes its handle on (only the media cache uses it), and a receiver's read recorded under
another subsystem although it runs in the worker process. The correction had been kept only in a side file."""

from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / 'check_census_fixes.py'
checks = 0
MATRIX = ['resource\tsubsystem\tplane\taccess\tsite\tcondition\tcensus_a\tcensus_b\tsettled_by',
          'shm-ring\tmm-cache\tdata\twrite\tengine/shm.py:40\tdefault\tengine\tmm-cache\treviewer',
          'kv-recv\tworker\tdata\tread\tworker/recv.py:12\tpd\tscheduler\tworker\treviewer',
          'pool\tscheduler\tcontrol\twrite\tsched/pool.py:7\tdefault\tscheduler\tscheduler\tnone',
          'pool\tcache\tcontrol\twrite\tcache/evict.py:30\tdefault\tnone\tcache\treviewer',
          'pool\tworker\tcontrol\thold\tworker/run.py:9\tdefault\tworker\tworker\tnone']
SOURCE = {'engine/shm.py': 45, 'worker/recv.py': 20, 'cache/evict.py': 30, 'frontend/parse.py': 8,
          'worker/run.py': 12, 'sched/pool.py': 10}
FIELDS = ['fix_id', 'date', 'corrected_by', 'table', 'row_key', 'field', 'wrong_value', 'right_value', 'kind',
          'found_by', 'evidence', 'note']
GOOD = [
    ['F-01', '2026-01-02', 'reviewer', 'resources', 'resource=shm-ring;site=engine/shm.py:40', 'subsystem',
     'engine', 'mm-cache', 'wrong_subsystem', 'second_pass', 'engine/shm.py:40@0123abc only the media cache opens it',
     'the engine only passes the handle on'],
    ['F-02', '2026-01-02', 'reviewer', 'resources', 'resource=kv-recv;site=worker/recv.py:12', 'subsystem',
     'scheduler', 'worker', 'wrong_subsystem', 'second_pass', 'worker/recv.py:12-14 runs in the worker process', ''],
    ['F-03', '2026-01-02', 'census-b', 'resources', 'resource=pool;subsystem=cache', 'row', '(absent)',
     'write at cache/evict.py:30', 'missed_write', 'second_census', 'cache/evict.py:30', 'eviction frees blocks'],
    ['F-04', '2026-01-03', 'reviewer', 'resources', 'resource=req-parser;subsystem=frontend', 'row',
     'write at frontend/parse.py:5', '(removed)', 'not_shared', 'review', 'frontend/parse.py:5 per-request object', ''],
    ['F-05', '2026-01-03', 'reviewer', 'resources', 'resource=pool;subsystem=worker', 'access', 'write', 'hold',
     'wrong_access', 'review', 'worker/run.py:9; worker/run.py:11 returns what it took', ''],
]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def invoke(*args, code, contains=(), label=''):
    global checks
    result = subprocess.run([sys.executable, '-B', str(SCRIPT), *map(str, args)],
                            capture_output=True, text=True, timeout=20)
    output = result.stdout + result.stderr
    require(result.returncode == code, f'{label or args}: expected exit {code}, got {result.returncode}: {output}')
    for fragment in contains:
        require(fragment in output, f'{label or args}: missing {fragment!r} in {output}')
    if code in (0, 1) and '--help' not in args and '--template' not in args:
        last = output.splitlines()[-1]
        require(last.startswith('OK census-fixes: ' if code == 0 else 'FAIL census-fixes: '), f'{label}: {last!r}')
    checks += 1
    return output


def record(path, rows, header=FIELDS):
    path.write_text('\t'.join(header) + '\n' + ''.join('\t'.join(row) + '\n' for row in rows))
    return path


def change(row, **fields):
    row = list(row)
    for name, value in fields.items():
        row[FIELDS.index(name)] = value
    return row


def main():
    invoke('--help', code=0, contains=('missed_write',))
    template = invoke('--template', code=0)
    require(template.splitlines()[0].split('\t') == FIELDS, 'template header')
    with tempfile.TemporaryDirectory(prefix='census-fixes-') as directory:
        scratch = Path(directory)
        source = scratch / 'src'
        for name, lines in SOURCE.items():
            (source / name).parent.mkdir(parents=True, exist_ok=True)
            (source / name).write_text(''.join(f'line {n}\n' for n in range(1, lines + 1)))
        matrix = scratch / 'matrix.tsv'
        matrix.write_text('\n'.join(MATRIX) + '\n')
        table = ['--table', f'resources={matrix}']
        good = record(scratch / 'good.tsv', GOOD)
        invoke(good, code=0, contains=('OK census-fixes: 5 corrections; tables not checked',), label='form-only')
        invoke(good, *table, '--source', source, code=0,
               contains=('OK census-fixes: 5 corrections; checked against 1 tables',), label='good')
        # The past mistake: the correction is written down, the table still holds the wrong value.
        stale = scratch / 'stale.tsv'
        stale.write_text('\n'.join([MATRIX[0], MATRIX[1].replace('\tmm-cache\tdata', '\tengine\tdata')] + MATRIX[2:])
                         + '\n')
        invoke(good, '--table', f'resources={stale}', code=1,
               contains=("subsystem is 'engine', not the right value 'mm-cache': the correction is recorded but "
                         'not applied',), label='not-applied')
        template_only = scratch / 'template.tsv'
        template_only.write_text(template)
        invoke(template_only, code=1, contains=('no corrections',), label='template-has-no-rows')
        bad = {
            'ambiguous-key': (change(GOOD[4], row_key='resource=pool'), 'picks 3 rows'),
            'removed-still-there': (change(GOOD[3], row_key='resource=pool;subsystem=cache'), 'is still in'),
            'absent-still-missing': (change(GOOD[2], row_key='resource=pool;subsystem=frontend'), 'picks 0 rows'),
            'no-location': (change(GOOD[0], evidence='only the media cache opens it'), 'evidence is path:LINE'),
            'same-values': (change(GOOD[4], wrong_value='hold'), 'are the same'),
            'missed-write-column': (change(GOOD[2], field='subsystem'), 'missed_write: field row'),
            'not-shared-kept': (change(GOOD[3], right_value='write'), 'not_shared: field row'),
            'column-kind-as-row': (change(GOOD[0], field='row'), 'wrong_subsystem corrects one column'),
            'unknown-kind': (change(GOOD[0], kind='typo'), 'kind is one of'),
            'bad-date': (change(GOOD[0], date='Jan 2'), 'date is YYYY-MM-DD'),
            'free-text-who': (change(GOOD[0], corrected_by='the reviewer'), 'corrected_by is an id'),
            'empty-found-by': (change(GOOD[0], found_by=''), 'found_by is required'),
            'unknown-key-column': (change(GOOD[0], row_key='unit=U-1'), 'has no column unit'),
            'unknown-field': (change(GOOD[0], field='owner'), 'has no column owner'),
            'bad-key': (change(GOOD[0], row_key='shm-ring'), 'row_key is column=value'),
            'unmapped-table': (change(GOOD[0], table='units'), 'no --table for units'),
            'beyond-file': (change(GOOD[0], evidence='engine/shm.py:90 the ring'), 'beyond its 45 lines'),
            'absent-file': (change(GOOD[0], evidence='engine/ring.py:4 the ring'), 'is not a file under'),
            # Inputs of an outside review of 0.125.0 that passed before 0.126.0.
            'missed-write-removed': (change(GOOD[2], right_value='(removed)'), 'missed_write: field row'),
            'reversed-range': (change(GOOD[0], evidence='engine/shm.py:44-1 the ring'), 'beyond its 45 lines'),
            'start-beyond-file': (change(GOOD[0], evidence='engine/shm.py:99-1 the ring'), 'beyond its 45 lines'),
            'outside-source': (change(GOOD[0], evidence='../outside.py:1 the ring'), 'is not a file under'),
            'absolute-outside-source': (change(GOOD[0], evidence=f'{scratch}/outside.py:1 the ring'),
                                        'is not a file under'),
        }
        (scratch / 'outside.py').write_text('line 1\n')
        for name, (row, fragment) in bad.items():
            invoke(record(scratch / 'one.tsv', [row]), *table, '--source', source, code=1, contains=(fragment,),
                   label=name)
        invoke(record(scratch / 'dup.tsv', [GOOD[0], GOOD[0]]), *table, code=1, contains=('fix_id F-01 repeats',),
               label='duplicate-id')
        invoke(record(scratch / 'short.tsv', [GOOD[0][:5]]), code=1, contains=('expected 12 columns',),
               label='short-row')
        invoke(record(scratch / 'header.tsv', GOOD, header=FIELDS[:-1]), code=1, contains=('header must be',),
               label='bad-header')
        invoke(good, '--table', 'resources', code=1, contains=('expected NAME=PATH',), label='bad-table-option')
        invoke(good, '--table', f'resources={scratch / "absent.tsv"}', code=1, contains=('ERROR ',),
               label='absent-table')
        invoke(code=2, contains=('FIXES.tsv is required',), label='no-record')
    print(f'PASS check_census_fixes: {len(GOOD)} good corrections, {len(bad)} bad rows, {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
