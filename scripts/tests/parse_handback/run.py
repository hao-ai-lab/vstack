#!/usr/bin/env python3
"""Exercise parse_handback.py on a good reply with real logs and on single-defect variants of it."""

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / 'parse_handback.py'
checks = 0
LOGS = {'out/logs/writers.log': 'reading 2 write sites\nOK writers: 0 errors\n\n',
        'out/logs/cites.log': 'cites checked: 4, errors=0\n'}


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
        require(output.splitlines()[-1].startswith('FAIL handback: '), f'{label}: last line is not FAIL: {output}')
    checks += 1
    return output


def setup(scratch):
    """Write the brief, the outputs and the logs; return (reply text, brief path)."""
    for name, text in LOGS.items():
        path = scratch / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    (scratch / 'out' / 'WRITERS.tsv').write_text('writer\tsite\tguard\n')
    (scratch / 'elsewhere.txt').write_text('not in the writable paths\n')
    brief = scratch / 'BRIEF.md'
    brief.write_text((HERE / 'brief.md').read_text().replace('{tmp}', str(scratch)))
    return (HERE / 'reply.txt').read_text().replace('{tmp}', str(scratch)), brief


# (old, new) replacements on the reply, the extra arguments, and the expected fragment.
VARIANTS = {
    'no-begin': (('BEGIN HANDBACK\n', ''), (), "expected exactly one 'BEGIN HANDBACK' line"),
    'end-before-begin': (('BEGIN HANDBACK\n', 'END HANDBACK\nBEGIN HANDBACK\n'), (), 'expected exactly one'),
    'bad-verdict': (('verdict: PASS', 'verdict: DONE'), (), 'verdict must be PASS, ISSUES or BLOCKED'),
    'no-verdict': (('verdict: PASS\n', ''), (), 'expected one verdict, found 0'),
    'two-verdicts': (('verdict: PASS\n', 'verdict: PASS\nverdict: ISSUES\n'), (), 'expected one verdict, found 2'),
    'unknown-field': (('version: python3 3.12\n', 'version: python3 3.12\nnote: extra\n'), (), 'not a hand-back field'),
    'empty-value': (('version: python3 3.12', 'version:'), (), 'empty version'),
    'check-without-log': (('log: {tmp}/out/logs/writers.log\n', ''), (), "'last line:' out of order"),
    'log-outside-check': (('verdict: PASS\n', 'verdict: PASS\nlog: out/logs/cites.log\n'), (), "'log:' outside a check"),
    'missing-log': (('logs/writers.log', 'logs/absent.log'), (), 'cannot read log'),
    'earlier-line': (('last line: OK writers: 0 errors', 'last line: reading 2 write sites'), (),
                     'claimed last line appears at non-blank line 1 of 2'),
    'wrong-count': (('last line: OK writers: 0 errors', 'last line: OK writers: 1 errors'), (),
                    'claimed last line does not appear'),
    'no-version': (('version: python3 3.12\nversion: source abc1234\n', ''), (), "no 'version:' line"),
    'no-written': (('written: {tmp}/out/WRITERS.tsv\nwritten: {tmp}/out/logs\n', ''), (), "no 'written:' line"),
    'no-rules': (('rules broken: none\n', ''), (), "no 'rules broken:' line"),
    'none-and-rule': (('rules broken: none\n', 'rules broken: none\nrules broken: opened a forbidden path\n'), (),
                      "'rules broken: none' must be the only rules line"),
    'written-missing': (('written: {tmp}/out/WRITERS.tsv', 'written: {tmp}/out/MISSING.tsv'), (), 'written file does not exist'),
    'no-check': (('check: python3', 'version: python3'), (), "'log:' outside a check"),
    'brief-unreported': (('check: python3 /opt', 'check: python3 -B /opt'), ('--brief',),
                         'done-evidence command not reported'),
    'brief-outside': (('rules broken: none', 'written: {tmp}/elsewhere.txt\nrules broken: none'), ('--brief',),
                      "written file lies outside the brief's writable paths"),
}


def regex_checks(scratch, text, brief, reply):
    """S16: a done check whose last line carries a count is written as a pattern for the whole line."""
    regex_brief = scratch / 'REGEX.md'
    regex_brief.write_text(brief.read_text().replace('last line ends with: `errors=0`',
                                                     'last line matches: `cites checked: [0-9]+, errors=0`'))
    reply.write_text(text)
    invoke(reply, '--brief', regex_brief, code=0, contains=('verdict=PASS',), label='regex-pass')
    cites = scratch / 'out' / 'logs' / 'cites.log'
    cites.write_text('cites checked: 4, errors=3\n')
    reply.write_text(text.replace('errors=0\nversion', 'errors=3\nversion'))
    invoke(reply, '--brief', regex_brief, code=1, contains=('should match: cites checked: [0-9]+, errors=0',),
           label='regex-mismatch')
    cites.write_text(LOGS['out/logs/cites.log'])


def ref_checks(scratch, text, brief, reply):
    """S9: ids that an output column names must exist in the table the brief names."""
    specs = scratch / 'specs.tsv'
    specs.write_text('spec_id\tsentence\nSTD-P01-01\tone\nSTD-P01-02\ttwo\n')
    leads = scratch / 'out' / 'LEADS.tsv'
    good_rows = 'lead\trelated_spec\nL1\tSTD-P01-01\nL2\tSTD-P01-02; STD-P01-01\nL3\tnone\n'
    leads.write_text(good_rows)
    ref_brief = scratch / 'REF.md'
    ref_brief.write_text(brief.read_text().replace(
        '- `WRITERS.tsv`: one row per write site.\n',
        '- `WRITERS.tsv`: one row per write site.\n- `LEADS.tsv`: one row per lead.\n'
        f'- ref: `LEADS.tsv` column `related_spec` -> `{specs}` column `spec_id`\n'))
    with_leads = text.replace('rules broken: none', f'written: {leads}\nrules broken: none')
    reply.write_text(with_leads)
    invoke(reply, '--brief', ref_brief, code=0, contains=('refs=1 ids_checked=3',), label='refs-good')
    # The real failure: renamed ids written into the column, here 2 of 3 rows.
    leads.write_text('lead\trelated_spec\nL1\tSTD-SA2-01-02\nL2\tSTD-P01-02\nL3\tSTD-SA2-01-03\n')
    invoke(reply, '--brief', ref_brief, code=1, contains=(
        f'{leads}:2: related_spec STD-SA2-01-02 is not an id in {specs} column spec_id',
        f'{leads}:4: related_spec STD-SA2-01-03 is not an id in'), label='refs-renamed-ids')
    invoke(reply, '--ref', leads, 'related_spec', specs, 'spec_id', code=1, contains=('STD-SA2-01-02 is not an id',),
           label='refs-cli')
    invoke(reply, '--ref', leads, 'absent', specs, 'spec_id', code=1, contains=("has no column 'absent'",),
           label='refs-missing-column')
    leads.unlink()
    reply.write_text(text)
    invoke(reply, '--brief', ref_brief, code=1, contains=('LEADS.tsv does not exist',), label='refs-missing-output')
    reply.write_text(text.replace('verdict: PASS', 'verdict: BLOCKED'))
    invoke(reply, '--brief', ref_brief, code=0, contains=('verdict=BLOCKED',), label='refs-blocked-skip')
    leads.write_text(good_rows)


def changed_checks(scratch, text, brief, reply):
    """S8: files changed in a shared tree stay inside the writable list of exactly one brief and are reported."""
    tree = scratch / 'tree'
    for name in ('scripts/a.py', 'scripts/b.py', 'docs/x.md'):
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_text('x\n')
    source = brief.read_text()
    out = f'- `{scratch}/out/`\n'
    mine = scratch / 'MINE.md'
    mine.write_text(source.replace(out, out + f'- `{tree}/scripts/a*.py`\n'))
    sibling = scratch / 'SIBLING.md'
    sibling.write_text(source.replace(out, f'- `{tree}/scripts/b.py`\n'))
    whole = scratch / 'WHOLE.md'
    whole.write_text(source.replace(out, f'- `{tree}`\n'))
    carved = scratch / 'CARVED.md'
    carved.write_text(source.replace(out, out + f'- `{tree}/scripts/`\n- except `{tree}/scripts/b.py`: the sibling\'s\n'))
    changed = scratch / 'CHANGED.txt'
    reported = text.replace('rules broken: none', f'written: {tree}/scripts/a.py\nrules broken: none')
    reply.write_text(reported)
    changed.write_text(' M scripts/a.py\n M scripts/b.py\n')
    base = ('--changed', changed, '--tree', tree)
    invoke(reply, '--brief', mine, *base, '--sibling', sibling, code=0, contains=('changed=2 sibling_owned=1',),
           label='changed-good')
    invoke(reply, '--brief', carved, *base, '--sibling', sibling, code=0, contains=('changed=2 sibling_owned=1',),
           label='changed-except')
    invoke(reply, '--brief', mine, *base, code=1, contains=('b.py lies outside the writable paths of this brief',),
           label='changed-no-sibling')
    # The real situation: both briefs give the whole tree, ownership only in prose.
    invoke(reply, '--brief', whole, *base, '--sibling', whole, code=1, contains=('two workers may not share',),
           label='changed-shared-tree')
    changed.write_text(' M scripts/a.py\n M scripts/b.py\n?? docs/x.md\n')
    invoke(reply, '--brief', mine, *base, '--sibling', sibling, code=1,
           contains=('x.md lies outside the writable paths of this brief and its siblings',), label='changed-outside')
    changed.write_text(' M scripts/a.py\n')
    reply.write_text(text)
    invoke(reply, '--brief', mine, *base, code=1, contains=('a.py is not reported as written',),
           label='changed-unreported')
    changed.write_text('R  scripts/a_old.py -> scripts/a.py\n D scripts/a2.py\n')
    reply.write_text(reported)
    invoke(reply, '--brief', mine, *base, code=0, contains=('changed=3',), label='changed-rename-delete')
    changed.write_text('?? scripts/new/\n')
    invoke(reply, '--brief', mine, *base, code=1, contains=('directory entry scripts/new/',), label='changed-dir')
    changed.write_text(f'{tree}/scripts/a.py\nscripts/a.py\n')
    invoke(reply, '--brief', mine, *base, code=0, contains=('changed=2',), label='changed-plain-paths')
    invoke(reply, '--changed', changed, code=2, contains=('need --brief',), label='changed-needs-brief')


def main():
    names = ('brief.md', 'reply.txt', 'bad.txt')
    before = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in names}
    invoke('--help', code=0, contains=('BEGIN HANDBACK',))
    invoke(code=2, contains=('ERROR arguments:',))
    invoke(HERE / 'bad.txt', code=1, label='bad-reply', contains=(
        "verdict must be PASS, ISSUES or BLOCKED, not 'DONE'", "'last line:' out of order",
        'not a hand-back field: status: finished', "no 'version:' line", 'written file does not exist',
        "'rules broken: none' must be the only rules line"))
    with tempfile.TemporaryDirectory(prefix='parse-handback-') as directory:
        scratch = Path(directory)
        text, brief = setup(scratch)
        reply = scratch / 'reply.txt'
        reply.write_text(text)
        out = invoke(reply, code=0, contains=('OK handback: verdict=PASS checks=2 written=2 rules_broken=0',
                                              'last_line\t2\tcites checked: 4, errors=0', 'version\t2\tsource abc1234'))
        require(out.splitlines()[0] == 'field\tindex\tvalue', 'TSV header missing')
        invoke(reply, '--brief', brief, code=0, contains=('OK handback:',))
        reply.write_text(text.replace('check: bash /opt', 'check:   bash  /opt'))
        invoke(reply, '--brief', brief, code=0, label='whitespace-normalized')
        reply.write_text(text.replace('verdict: PASS', 'verdict: BLOCKED').replace('check: python3 /opt',
                                                                                  'check: python3 -B /opt'))
        invoke(reply, '--brief', brief, code=0, contains=('verdict=BLOCKED',), label='blocked-may-skip-a-done-check')
        for name, ((old, new), extra, fragment) in VARIANTS.items():
            old, new = old.replace('{tmp}', str(scratch)), new.replace('{tmp}', str(scratch))
            require(old in text, f'{name}: fixture text not found')
            reply.write_text(text.replace(old, new, 1))
            args = [reply] + ([extra[0], brief] if extra else [])
            invoke(*args, code=1, contains=(fragment,), label=name)
        reply.write_text(text + '\n' + text[text.index('BEGIN'):])
        invoke(reply, code=1, contains=("expected exactly one 'BEGIN HANDBACK'",), label='two-blocks')
        reply.write_text('BEGIN HANDBACK\nEND HANDBACK\n')
        invoke(reply, code=1, contains=('empty hand-back block',), label='empty-block')
        # A claimed line that matches the log but not the brief: an error for PASS, accepted for ISSUES.
        log = scratch / 'out' / 'logs' / 'writers.log'
        log.write_text('OK writers: 2 errors\n')
        mismatch = text.replace('last line: OK writers: 0 errors', 'last line: OK writers: 2 errors')
        reply.write_text(mismatch)
        invoke(reply, code=0, label='mismatch-without-brief')
        invoke(reply, '--brief', brief, code=1, contains=("verdict PASS, but the last line of 'python3",
                                                          'should be: OK writers: 0 errors'), label='pass-mismatch')
        reply.write_text(mismatch.replace('verdict: PASS', 'verdict: ISSUES'))
        invoke(reply, '--brief', brief, code=0, contains=('verdict=ISSUES',), label='issues-mismatch')
        log.write_text(LOGS['out/logs/writers.log'])
        cites = scratch / 'out' / 'logs' / 'cites.log'
        cites.write_text('cites checked: 4, errors=3\n')
        reply.write_text(text.replace('errors=0\nversion', 'errors=3\nversion'))
        invoke(reply, '--brief', brief, code=1, contains=('should end with: errors=0',), label='suffix-mismatch')
        cites.write_text('')
        reply.write_text(text)
        invoke(reply, code=1, contains=('log is empty',), label='empty-log')
        cites.write_text(LOGS['out/logs/cites.log'])
        invoke(reply, '--root', scratch / 'out', code=1, contains=('cannot read log',), label='root-moves-relative-paths')
        broken = scratch / 'BROKEN.md'
        broken.write_text(brief.read_text().replace('- command:', '- step:'))
        invoke(reply, '--brief', broken, code=1, contains=('does not pass check_brief',), label='broken-brief')
        regex_checks(scratch, text, brief, reply)
        ref_checks(scratch, text, brief, reply)
        changed_checks(scratch, text, brief, reply)
        reply.write_bytes(b'\xff\xfe')
        invoke(reply, code=1, contains=('ERROR',), label='not-utf8')
        invoke(scratch / 'absent.txt', code=1, contains=('ERROR',), label='absent-reply')
    after = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in before}
    require(before == after, 'a fixture changed')
    print(f'PASS parse_handback: 1 good reply, 1 bad reply, {len(VARIANTS)} defect variants, regex, id-reference '
          f'and changed-file cases, {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
