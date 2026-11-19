#!/usr/bin/env python3
"""Exercise check_unit_table.py on a good table with real evidence files, bad rows one at a time and table edits."""

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / 'check_unit_table.py'
ROOT = HERE.parents[2]
COMPARE_HEADER = 'row_a\trow_b\trelation\tcontradiction\twho_is_right\tnote\n'
checks = 0

BAD = {
    'bad-status': 'status must be one of', 'bad-first': 'first_of_batch must be yes or no',
    'bad-key': 'key must be yes or no', 'no-batch': 'batch is required', 'no-owner': 'a running unit needs an owner',
    'no-outdir': 'output_dir is required', 'no-evidence': 'a pass unit needs evidence',
    'missing-evidence': 'evidence does not exist', 'outside-evidence': "evidence lies outside the unit's output_dir",
    'key-one-owner': 'owner must name two different workers', 'key-no-compare': 'needs its writing-compare table',
    # S21: a brief written but not dispatched, a dispatched unit without its brief, a brief that does not exist.
    'brief-no-worker': 'brief bad/briefs/brief-no-worker.md has no recorded worker',
    'no-brief': 'a running unit needs the brief its worker was sent', 'missing-brief': 'brief does not exist',
}
BRIEF = 12  # index of the brief column


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def invoke(*args, code, contains=(), label=''):
    global checks
    result = subprocess.run([sys.executable, '-B', str(SCRIPT), *map(str, args)],
                            capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    require(result.returncode == code, f'{label or args}: expected exit {code}, got {result.returncode}: {output}')
    for fragment in contains:
        require(fragment in output, f'{label or args}: missing {fragment!r} in {output}')
    if code == 1:
        require(output.splitlines()[-1].startswith('FAIL unit table: '), f'{label}: last line is not FAIL: {output}')
    checks += 1
    return output


def read(path):
    lines = path.read_text().splitlines()
    header = lines[0]
    rows = [line.split('\t') for line in lines[1:] if line.strip() and not line.startswith('#')]
    return header, rows


def make_evidence(root, rows):
    """Create every evidence path and brief named in the rows, except paths naming 'absent'."""
    for row in rows:
        if row[BRIEF] and 'absent' not in row[BRIEF]:
            (root / row[BRIEF]).parent.mkdir(parents=True, exist_ok=True)
            (root / row[BRIEF]).write_text(f'# Task brief: {row[0]}\n')
        for item in filter(None, row[-1].split(';')):
            path = root / item
            if 'absent' in item:
                continue
            if item.endswith('/'):
                path.mkdir(parents=True, exist_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(COMPARE_HEADER if item.endswith('writing-compare.tsv') else 'evidence\n')


def write(path, header, rows):
    path.write_text(header + '\n' + ''.join('\t'.join(row) + '\n' for row in rows))


def edit(rows, unit, **fields):
    """Return a copy of rows with named fields of one unit replaced."""
    names = ['unit_id', 'resource', 'subsystems', 'k', 'plane', 'entry_kind', 'tier', 'properties', 'method',
             'budget_result', 'evidence_level', 'status', 'brief', 'owner', 'output_dir', 'batch', 'first_of_batch',
             'key', 'evidence']
    out = []
    for row in rows:
        row = list(row)
        if row[0] == unit:
            for name, value in fields.items():
                row[names.index(name)] = value
        out.append(row)
    return out


def main():
    fixtures = [HERE / name for name in ('good.tsv', 'bad.tsv', 'plan.txt')]
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in fixtures]
    header, good = read(HERE / 'good.tsv')
    _, bad = read(HERE / 'bad.tsv')
    require(sorted(row[0] for row in bad) == sorted(BAD), 'bad.tsv rows and expectations differ')
    # One definition: the headers this test feeds the checker are the templates' own header lines.
    templates = ROOT / 'templates'
    require((templates / 'writing-compare.tsv').read_text().splitlines()[0] + '\n' == COMPARE_HEADER,
            'templates/writing-compare.tsv and the compare header recognized by check_unit_table disagree')
    require((templates / 'unit-table.tsv').read_text().splitlines()[0] == header,
            'templates/unit-table.tsv and the unit-table fixtures disagree')
    invoke('--help', code=0, contains=('one-unit-first', 'queued'))
    invoke(HERE / 'good.tsv', code=2, contains=('ERROR arguments:',), label='plan-option-required')
    invoke(HERE / 'good.tsv', '--plan', HERE / 'plan.txt', '--no-plan', code=2, contains=('ERROR arguments:',))
    with tempfile.TemporaryDirectory(prefix='check-unit-table-') as directory:
        scratch = Path(directory)
        make_evidence(scratch, good + bad)
        table, plan = scratch / 'UNITS.tsv', scratch / 'PLAN.txt'
        plan.write_text((HERE / 'plan.txt').read_text())
        write(table, header, good)
        invoke(table, '--plan', plan, code=0, contains=(
            'OK unit table: 6 units in 2 batches (queued 1, running 1, blocked 1, accepted 3); plan 6 units, none '
            'missing; 1 blocked unit recorded as gaps',))
        invoke(table, '--no-plan', code=0, contains=('no plan supplied, gaps not checked', '5 briefs, 6 workers'))
        # S21: every brief in the coordinator's brief folder is a unit's brief with its worker recorded.
        briefs = scratch / 'briefs'
        invoke(table, '--plan', plan, '--briefs', briefs, code=0, label='briefs-all-recorded')
        (briefs / 'U-06.md').write_text('# Task brief: U-06\n')
        invoke(table, '--plan', plan, '--briefs', briefs, code=1,
               contains=(f'brief {briefs / "U-06.md"} is named by no unit row: written but never dispatched',),
               label='brief-written-not-dispatched')
        invoke(table, '--plan', plan, '--briefs', scratch / 'absent-dir', code=1, contains=('is not a directory',),
               label='briefs-not-a-directory')
        plan_tsv = scratch / 'PLAN.tsv'
        plan_tsv.write_text('unit_id\tresource\n' + ''.join(f'{row[0]}\tbuffer_slots\n' for row in good))
        invoke(table, '--plan', plan_tsv, code=0, label='plan-as-tsv')
        # Input of an outside review of 0.125.0: a TSV plan of one column is a TSV plan, and a short row is an error.
        plan_tsv.write_text('unit_id\n' + ''.join(f'{row[0]}\n' for row in good))
        invoke(table, '--plan', plan_tsv, code=0, label='plan-one-column-tsv')
        plan_tsv.write_text('resource\tunit_id\n' + ''.join(f'buffer_slots\t{row[0]}\n' for row in good) + 'x\n')
        invoke(table, '--plan', plan_tsv, code=1, contains=('no unit_id in this plan row',), label='plan-short-row')
        for row in bad:
            write(table, header, [row])
            invoke(table, '--no-plan', code=1, contains=(BAD[row[0]],), label=row[0])
        cases = {
            'duplicate-id': (edit(good, 'U-02', unit_id='U-01'), 'duplicate unit_id U-01'),
            'nested-output': (edit(good, 'U-02', output_dir='units/U-01/sub/', evidence='units/U-01/HANDBACK.txt'),
                              'overlaps the output_dir'),
            'two-firsts': (edit(good, 'U-02', first_of_batch='yes'), 'batch b1 needs exactly one first_of_batch=yes, found 2'),
            'no-first': (edit(good, 'U-05', first_of_batch='no'), 'batch b2 needs exactly one first_of_batch=yes, found 0'),
            # S21: one worker id per unit, one brief per unit, no brief without its worker or worker without its brief.
            'worker-two-units': (edit(good, 'U-02', owner='worker-01'),
                                 'worker worker-01 is recorded for units U-01 and U-02'),
            'key-worker-reused': (edit(good, 'U-03', owner='worker-03;worker-02'),
                                  'worker worker-02 is recorded for units U-02 and U-03'),
            'brief-two-units': (edit(good, 'U-02', brief='briefs/U-01.md'), 'is also the brief of unit U-01'),
            'brief-without-worker': (edit(good, 'U-06', brief='briefs/U-06.md'),
                                     'brief briefs/U-06.md has no recorded worker'),
            'running-without-brief': (edit(good, 'U-05', brief=''), 'a running unit needs the brief its worker was sent'),
            'fan-out-early': (edit(good, 'U-06', status='running', brief='briefs/U-06.md', owner='worker-07'),
                              'first unit U-05 is running, but U-06 already left queued'),
            'first-not-accepted': (edit(good, 'U-01', status='pass'), 'first unit U-01 is pass, but U-02, U-03, U-04'),
            'compare-by-name-only': (edit(good, 'U-03', evidence='units/U-03/HANDBACK.txt;units/U-03/notes.tsv'),
                                     'needs its writing-compare table'),
            # Input of an outside review of 0.125.0: only a key unit names two workers.
            'not-key-two-owners': (edit(good, 'U-05', owner='worker-06;worker-08'),
                                   'a unit that is not key has one worker'),
        }
        (scratch / 'units' / 'U-03' / 'notes.tsv').write_text('row_a\trow_b\n')
        for name, (rows, fragment) in cases.items():
            write(table, header, rows)
            invoke(table, '--plan', plan, code=1, contains=(fragment,), label=name)
        (scratch / 'units' / 'U-03' / 'review.tsv').write_text(COMPARE_HEADER)
        write(table, header, edit(good, 'U-03', evidence='units/U-03/review.tsv'))
        invoke(table, '--plan', plan, code=0, label='compare-recognized-by-header')
        write(table, header, good)
        plan.write_text('U-01\nU-02\nU-03\nU-04\nU-05\nU-06\nU-07\n')
        invoke(table, '--plan', plan, code=1, contains=('planned unit missing from the table: U-07',))
        plan.write_text('U-01\nU-02\nU-03\nU-04\nU-05\n')
        invoke(table, '--plan', plan, code=1, contains=('unit is not in the plan: U-06',))
        plan.write_text('# nothing planned\n')
        invoke(table, '--plan', plan, code=1, contains=('lists no unit',))
        invoke(table, '--no-plan', '--final', code=1, contains=('not drained: U-05 is running', 'not drained: U-06 is queued'))
        (scratch / 'units' / 'U-05').mkdir(parents=True, exist_ok=True)
        (scratch / 'units' / 'U-05' / 'HANDBACK.txt').write_text('evidence\n')
        (scratch / 'units' / 'U-06').mkdir(parents=True, exist_ok=True)
        (scratch / 'units' / 'U-06' / 'HANDBACK.txt').write_text('evidence\n')
        drained = edit(edit(good, 'U-05', status='accepted', evidence='units/U-05/HANDBACK.txt'),
                       'U-06', status='accepted', brief='briefs/U-06.md', owner='worker-07',
                       evidence='units/U-06/HANDBACK.txt')
        write(table, header, drained)
        invoke(table, '--no-plan', '--final', code=0, contains=('(blocked 1, accepted 5)', '1 blocked unit recorded as gaps'))
        invoke(table, '--no-plan', '--final', '--briefs', briefs, code=0, contains=('6 briefs, 7 workers',),
               label='drained-briefs-recorded')
        write(table, '\t'.join(name for name in header.split('\t') if name != 'brief'),
              [row[:BRIEF] + row[BRIEF + 1:] for row in drained])
        invoke(table, '--no-plan', code=1, contains=('this is the 0.123.0 header: add the column brief before owner',),
               label='release-0.123-header')
        write(table, header, edit(good, 'U-06', evidence='units/U-06/HANDBACK.txt;units/U-06/absent.log'))
        invoke(table, '--no-plan', code=1, contains=('evidence does not exist: units/U-06/absent.log',),
               label='queued-evidence-checked-when-given')
        old = '\t'.join(header.split('\t')[:14])
        write(table, old, [row[:14] for row in good])
        invoke(table, '--no-plan', code=1, contains=('header must be',), label='old-header')
        write(table, header, [good[0][:-1]])
        invoke(table, '--no-plan', code=1, contains=('expected 19 columns, found 18',))
        invoke(ROOT / 'templates' / 'unit-table.tsv', '--no-plan', code=1, contains=('no unit rows',))
        invoke(scratch / 'absent.tsv', '--no-plan', code=1, contains=('ERROR',), label='absent-table')
    after = [hashlib.sha256(path.read_bytes()).hexdigest() for path in fixtures]
    require(before == after, 'a fixture changed')
    print(f'PASS check_unit_table: {len(good)} good rows, {len(bad)} bad rows, {len(cases)} table edits, {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
