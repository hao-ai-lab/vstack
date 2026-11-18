#!/usr/bin/env python3
"""Exercise check_refusals.py on generated documentation and refusal records.

The first bad row repeats a mistake seen in use: a check judged a refused documented sequence (pause at level 0,
then release the cache) to be the documented precondition of another sequence (release without a pause), so the
refusal was not counted as a failure. Asking whether the documentation promises the sequence that was run, and
quoting it, makes the record refuse that reading."""

from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / 'check_refusals.py'
checks = 0
DOC = ('# Engine control\n'
       'Call pause() before release_cache().\n'
       'After sleep(level=0) the engine is paused, and release_cache() then frees the cache.\n'
       'wake_up() resumes the engine after sleep().\n'
       'update_weights() replaces the weights in place.\n')
FIELDS = ['case_id', 'operation', 'promised', 'doc_read', 'outcome', 'verdict', 'note']
P2 = 'docs/control.md:2 "Call pause() before release_cache()."'
P3 = 'docs/control.md:3 "After sleep(level=0) the engine is paused, and release_cache() then frees the cache."'
GOOD = [
    ['C-01', 'release_cache()', 'no', P2, 'refused', 'documented_refusal', 'no pause before the release'],
    ['C-02', 'sleep(level=0); release_cache()', 'yes', P3, 'refused', 'failure', 'the documented sequence is refused'],
    ['C-03', 'sleep(level=0); wake_up()', 'yes', f'{P3}; docs/control.md:4 "wake_up() resumes the engine after sleep()"',
     'done', 'pass', ''],
    ['C-04', 'reset_cache()', 'silent', 'docs/control.md', 'refused', 'triage', 'nothing documented'],
    ['C-05', 'engine.update_weights(path)', 'yes', 'docs/control.md:5 "update_weights() replaces the weights in place."',
     'no_effect', 'failure', 'reports success, weights unchanged'],
    ['C-06', 'pause(); flush()', 'unknown', 'https://example.com/api#flush; docs/control.md:1-2', 'refused',
     'await_facts', 'the page and the file disagree'],
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
        require(last.startswith('OK refusals: ' if code == 0 else 'FAIL refusals: '), f'{label}: {last!r}')
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
    invoke('--help', code=0, contains=('documented_refusal',))
    template = invoke('--template', code=0)
    require(template.splitlines()[0].split('\t') == FIELDS, 'template header')
    with tempfile.TemporaryDirectory(prefix='check-refusals-') as directory:
        scratch = Path(directory)
        docs = scratch / 'tree'
        (docs / 'docs').mkdir(parents=True)
        (docs / 'docs' / 'control.md').write_text(DOC)
        good = record(scratch / 'good.tsv', GOOD)
        invoke(good, '--docs', docs, code=0, contains=('OK refusals: 6 cases (2 failure, 1 documented_refusal, '
                                                       '1 triage, 1 await_facts, 1 pass)',), label='good')
        invoke(good, code=0, label='good-without-docs')
        bad = {
            # The past mistake: the refused sequence recorded as a documented precondition of another sequence.
            'precondition-of-another-sequence': (change(GOOD[1], promised='no', doc_read=P2,
                                                        verdict='documented_refusal'),
                                                 'the quoted documentation does not name sleep'),
            'refusal-called-safe': (change(GOOD[1], verdict='documented_refusal'),
                                    'verdict is failure when promised is yes and the outcome is refused'),
            'silent-success-passed': (change(GOOD[4], verdict='pass'), 'verdict is failure'),
            'silent-docs-refusal-safe': (change(GOOD[3], verdict='documented_refusal'), 'verdict is triage'),
            'no-docs-listed': (change(GOOD[0], doc_read=''), 'doc_read is required'),
            'prohibition-without-quote': (change(GOOD[0], doc_read='docs/control.md:2'),
                                          "promised no needs the documentation's words"),
            'invented-quote': (change(GOOD[0], doc_read='docs/control.md:2 "release_cache() needs a pause"'),
                               'the quote is not in docs/control.md:2'),
            'quote-on-other-line': (change(GOOD[0], doc_read='docs/control.md:4 "Call pause() before release_cache()."'),
                                    'the quote is not in docs/control.md:4'),
            'absent-doc': (change(GOOD[0], doc_read='docs/other.md:2 "Call pause() before release_cache()."'),
                           'is not a file under'),
            'line-outside': (change(GOOD[0], doc_read='docs/control.md:40 "Call pause() before release_cache()."'),
                             'outside its 5 lines'),
            'bad-promised': (change(GOOD[0], promised='maybe'), 'promised is one of'),
            'bad-outcome': (change(GOOD[0], outcome='error'), 'outcome is one of'),
            'bad-doc-read': (change(GOOD[0], doc_read='docs/control.md:2 "unclosed'), 'doc_read is SOURCE'),
            'empty-step': (change(GOOD[1], operation='sleep(level=0);; release_cache()'), 'operation is the calls'),
            'free-text-id': (change(GOOD[0], case_id='case one'), 'case_id is an id'),
        }
        for name, (row, fragment) in bad.items():
            invoke(record(scratch / 'one.tsv', [row]), '--docs', docs, code=1, contains=(fragment,), label=name)
        invoke(record(scratch / 'dup.tsv', [GOOD[0], GOOD[0]]), code=1, contains=('case_id C-01 repeats',),
               label='duplicate-id')
        invoke(record(scratch / 'short.tsv', [GOOD[0][:4]]), code=1, contains=('expected 7 columns',),
               label='short-row')
        invoke(record(scratch / 'header.tsv', GOOD, header=FIELDS[:-1]), code=1, contains=('header must be',),
               label='bad-header')
        empty = scratch / 'empty.tsv'
        empty.write_text(template)
        invoke(empty, code=1, contains=('no cases',), label='template-has-no-rows')
        invoke(good, '--docs', scratch / 'absent', code=1, contains=('not a directory',), label='absent-docs')
        invoke(code=2, contains=('REFUSALS.tsv is required',), label='no-record')
    print(f'PASS check_refusals: {len(GOOD)} good cases, {len(bad)} bad rows, {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
