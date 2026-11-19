#!/usr/bin/env python3
"""Exercise make_brief.py: the base template and the five domain templates, computed values, the stamp, refusals."""

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1]
ROOT = HERE.parents[2]
MAKE, CHECK = SCRIPTS / 'make_brief.py', SCRIPTS / 'check_brief.py'
DOMAINS = ('spec-check', 'triage', 'reproduction', 'instance-writing', 'comparison')
checks = 0

# Fields of each domain template; {tmp} is the scratch directory and {root} this vstack tree.
DOMAIN_FIELDS = {
    'spec-check': (
        'template: templates/briefs/spec-check.md\nunit id: SC-01\nspec id: SPEC-02\nsource tree: {tmp}/src\n'
        'revision: abc1234\ncontext:\nspec table: {tmp}/specs.tsv\n'
        'sentence: {{cell of {tmp}/specs.tsv column sentence where spec_id=SPEC-02}}\n'
        'id pattern: SPEC-[0-9][0-9]\ninputs:\n  - `{tmp}/harness`: a stand-in executor that lets the real core run.\n'
        'output dir: {tmp}/out/SC-01\nwritable:\n  - `{tmp}/scratch/SC-01`: scratch space.\n'
        'blind paths:\n  - `{tmp}/known/`: the known defects, the answer key of this check.\n'
        '  - `{tmp}/out/SC-02/`: another worker\'s folder.\nchecks:\nreply: in English, short\n'),
    'triage': (
        'template: templates/briefs/triage.md\nunit id: TR-01\n'
        'failures: {{rows of {tmp}/viol-a.tsv {tmp}/viol-b.tsv where known=no}}\n'
        'context: The failures come from two checks of the specification table at revision `abc1234`.\n'
        'violation tables:\n  - `{tmp}/viol-a.tsv`: failures of the first check.\n'
        '  - `{tmp}/viol-b.tsv`: failures of the second check.\n'
        'known table: {tmp}/known/known.tsv\nknown id column: id\nsource tree: {tmp}/src\ninputs:\n'
        'output dir: {tmp}/out/TR-01\nwritable:\nforbidden:\nchecks:\nreply: in English, short\n'),
    'reproduction': (
        'template: templates/briefs/reproduction.md\nunit id: RP-01\nlead id: L-07\nrevision: abc1234\ncontext:\n'
        'leads table: {tmp}/leads.tsv\nlead: {{cell of {tmp}/leads.tsv column claim where lead_id=L-07}}\n'
        'id pattern: L-[0-9][0-9]\nsource tree: {tmp}/src\nvstack root: {root}\ninputs:\n'
        'output dir: {tmp}/out/RP-01\nwritable:\nforbidden:\nchecks:\nreply: in English, short\n'),
    'instance-writing': (
        'template: templates/briefs/instance-writing.md\nunit id: IW-01\ngroup id: G-03\nrevision: abc1234\n'
        'resources: {{rows of {tmp}/group/resources.tsv}}\ncontext:\nresources table: {tmp}/group/resources.tsv\n'
        'drafts: {tmp}/group/drafts.tsv\nsites: {tmp}/group/sites.tsv\nsource tree: {tmp}/src\ninputs:\n'
        'output dir: {tmp}/out/IW-01\nwritable:\nforbidden:\n'
        'specs header: header `local_id\tresource_id\tstandard_sentence\tinstance_sentence\tdraft_sentence_ids`\n'
        'draft id column: sentence_id\nchecks:\n  - command: `python3 {tmp}/tools/validate.py {tmp}/group '
        '{tmp}/out/IW-01`\n    last line: `VALIDATE PASS`\nreply: in English, short\n'),
    'comparison': (
        'template: templates/briefs/comparison.md\nunit id: KU-01\ncontext:\nwriting a: {tmp}/w/a.tsv\n'
        'writing b: {tmp}/w/b.tsv\nsource tree: {tmp}/src\nvstack root: {root}\ninputs:\noutput dir: {tmp}/out/KU-01\n'
        'writable:\nforbidden:\nid column: id\nchecks:\nreply: in English, short\n'),
}
DOMAIN_OK = {
    'spec-check': ('blind=yes', '1 id sets', 'generated=yes'),
    'triage': ('1 counts', '1 refs', 'generated=yes'),
    'reproduction': ('2 done checks', '1 id sets', 'generated=yes'),
    'instance-writing': ('1 counts', '1 refs', '2 done checks', 'generated=yes'),
    'comparison': ('1 done checks', 'generated=yes'),
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run(script, *args, code, contains=(), absent=(), label='', fail_prefix=None):
    global checks
    result = subprocess.run([sys.executable, '-B', str(script), *map(str, args)],
                            capture_output=True, text=True, timeout=60)
    output = result.stdout + result.stderr
    require(result.returncode == code, f'{label}: expected exit {code}, got {result.returncode}: {output}')
    for fragment in contains:
        require(fragment in output, f'{label}: missing {fragment!r} in {output}')
    for fragment in absent:
        require(fragment not in output, f'{label}: unexpected {fragment!r} in {output}')
    if code == 1 and fail_prefix:
        require(output.splitlines()[-1].startswith(fail_prefix), f'{label}: last line is not FAIL: {output}')
    checks += 1
    return output


def make(*args, **kwargs):
    return run(MAKE, *args, fail_prefix='FAIL make_brief', **kwargs)


def check(*args, **kwargs):
    return run(CHECK, *args, fail_prefix='FAIL brief: ', **kwargs)


def write_tables(tmp):
    """The tables the fields name: failure tables, specifications, known rows, leads, a group and two writings."""
    tables = {
        'fail-1.tsv': 'violation\tverdict\nV1\t\nV2\tdefect\nV3\t\n',
        'fail-2.tsv': '# rows of the second check\nviolation\tverdict\n\nV4\tartefact\nV5\t\n',
        'fail-3.tsv': 'violation\tverdict\nV6\t\n',
        'resources.tsv': 'resource_id\tname\nR1\tslot table\n',
        'specs.tsv': 'spec_id\tsentence\nSPEC-01\tA waiter wakes on every change that can satisfy it.\n'
                     'SPEC-02\tA released buffer is never read again by a later step.\n',
        'known/known.tsv': 'id\tsummary\nK-01\tstale read\nK-02\tlost wake-up\n',
        'viol-a.tsv': 'id\tplace\tknown\nSPEC-01-V01\tp1\tno\nSPEC-01-V02\tp2\tyes\n',
        'viol-b.tsv': 'id\tplace\tknown\nSPEC-02-V01\tp3\tno\n',
        'leads.tsv': 'lead_id\tclaim\nL-07\tA retried request reuses a slot freed by its first attempt.\n'
                     'L-08\tA cancelled stream keeps its slot.\n',
        'group/resources.tsv': 'resource_id\tname\nR1\tslots\nR2\tpages\n',
        'group/drafts.tsv': 'sentence_id\tsentence\nD1\tone\nD2\ttwo\n',
        'group/sites.tsv': 'resource_id\tsite\nR1\ta.py:1\n',
        'w/a.tsv': 'id\twriter\nA-01\tw\n',
        'w/b.tsv': 'id\twriter\nB-01\tw\n',
    }
    for name, text in tables.items():
        (tmp / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp / name).write_text(text)
    (tmp / 'src').mkdir()


def main():
    template = ROOT / 'templates' / 'task-brief.md'
    fixtures = [HERE / 'fields.txt', template] + [ROOT / 'templates' / 'briefs' / f'{name}.md' for name in DOMAINS]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in fixtures}
    make('--help', code=0, contains=('FIELDS', 'stamp'), label='help')
    make(code=2, contains=('ERROR arguments:',), label='usage')
    with tempfile.TemporaryDirectory(prefix='make-brief-') as directory:
        tmp = Path(directory)
        write_tables(tmp)
        text = (HERE / 'fields.txt').read_text().replace('{tmp}', str(tmp))
        fields, brief = tmp / 'fields.txt', tmp / 'BRIEF.md'
        fields.write_text(text)
        make(fields, '--out', brief, code=0, contains=('OK make_brief: wrote', '3 computed values'), label='base')
        body = brief.read_text()
        # S20: each file's own header is skipped: 6 rows, 4 of them undecided ('awk NR>1' over the three gives 10).
        require(f'6 rows of `{tmp}/fail-1.tsv`, `{tmp}/fail-2.tsv` and `{tmp}/fail-3.tsv` to' in body,
                'computed count missing')
        require(f'4 rows of `{tmp}/fail-1.tsv`' in body and 'where `verdict=`' in body, 'filtered count')
        unit_header = (ROOT / 'templates' / 'unit-table.tsv').read_text().splitlines()[0]
        require(f'header `{unit_header}` (from `templates/unit-table.tsv`)' in body, 'S4: template header missing')
        check(brief, code=0, contains=('generated=yes', '2 counts'), absent=('ERROR',), label='base-checks')
        first = brief.read_bytes()
        make(fields, '--out', brief, code=0, label='idempotent')
        require(brief.read_bytes() == first, 'a second run changed the brief')
        # S2: a generated brief edited by hand, or derived from another brief by substitution, is refused.
        brief.write_text(body.replace('in two lines', 'in three lines'))
        check(brief, code=1, contains=('edited after it was generated',), label='edited')
        make(fields, '--out', brief, code=1, contains=('exists and was edited after generation',), label='no-clobber')
        make(fields, '--out', brief, '--force', code=0, label='force')
        derived = tmp / 'BRIEF-U-02.md'
        derived.write_text(body.replace('U-01', 'U-02'))
        check(derived, code=1, contains=('edited after it was generated',), label='derived-by-substitution')
        check(derived, '--hand-written', code=1, contains=('edited after it was generated',),
              label='derived-hand-written-flag')
        fields.write_text(text + '# a later note\n')
        check(brief, code=1, contains=('fields file', 'changed since this brief was generated'), label='fields-changed')
        fields.write_text(text)
        hand = tmp / 'HAND.md'
        hand.write_text('# Task brief: written by hand\n')
        make(fields, '--out', hand, code=1, contains=('exists and was not generated',), label='hand-written-out')
        refusals = {
            'stale-field': (text + 'spec id: SPEC-09\n', "field 'spec id' fills no slot"),
            'missing-field': (text.replace('reply: Above the block, reply in English, in two lines.\n', ''),
                              'no field for slot <reply>'),
            'inline-block': (text.replace('unit id: U-01\n', 'unit id:\n  U-01\n  U-02\n'),
                             "field 'unit id' fills a slot inside a line"),
            'duplicate': (text + 'blind: yes\n', "field 'blind' given twice"),
            'not-a-field': (text + 'Unit: U-01\n', 'not a field line'),
            'relative-count': (text.replace(
                f'{{{{rows of {tmp}/fail-1.tsv', '{{rows of fail-1.tsv', 1), 'cannot compute {{rows of fail-1.tsv'),
            'missing-cell-column': (text.replace('title: writers of the buffer slot table',
                                                 f'title: {{{{cell of {tmp}/specs.tsv column absent where '
                                                 'spec_id=SPEC-01}}'), "has no column 'absent'"),
            'blind-conflict': (text.replace('blind: no', 'blind: yes').replace(
                'forbidden:\n', f'forbidden:\n  - `{tmp}/src/`: hidden\n'), 'does not pass check_brief'),
        }
        for name, (variant, fragment) in refusals.items():
            fields.write_text(variant)
            out = tmp / f'{name}.md'
            make(fields, '--out', out, code=1, contains=(fragment,), label=name)
            require(not out.exists(), f'{name}: a refused brief was written')
        # S2: a fields file copied from another unit keeps an id of that unit; the declared ids refuse it.
        fields.write_text(text.replace('the pinned source tree.', 'the tree read for U-07.').replace(
            '  - `{0}/src`'.format(tmp), '  - ids: `U-[0-9][0-9]` only `U-01`\n  - `{0}/src`'.format(tmp)))
        make(fields, '--out', tmp / 'stale-id.md', code=1, contains=('id U-07 is not in the ids listed',),
             label='stale-id-in-copied-fields')
        fields.write_text(text)
        # A slot whose text runs past the end of its line is neither filled nor missed: the check refuses it.
        broken = tmp / 'templates' / 'task-brief.md'
        broken.parent.mkdir()
        broken.write_text(template.read_text().replace('<reply: what the reply says above the block, or nothing>',
                                                       '<reply: what the reply says\nabove the block>'))
        make(fields, '--template', broken, '--out', tmp / 'dangling.md', code=1,
             contains=("field 'reply' fills no slot",), label='dangling-slot-field')
        fields.write_text(text.replace('reply: Above the block, reply in English, in two lines.\n', ''))
        make(fields, '--template', broken, '--out', tmp / 'dangling.md', code=1,
             contains=('placeholder left: <reply: what the reply says',), label='dangling-slot-checked')
        fields.write_text(text + 'template: templates/briefs/triage.md\n')
        make(fields, '--template', template, '--out', tmp / 'x.md', code=1, contains=('differs from the field',),
             label='template-mismatch')
        # Inputs of an outside review of 0.125.0. The stamp line is left out of the body hash, so text after its
        # closing '-->' (between two comments, visible when rendered) makes the line no stamp at all.
        fields.write_text(text)
        make(fields, '--out', brief, '--force', code=0, label='regenerate')
        lines = brief.read_text().split('\n')
        lines[1] = lines[1] + ' TODO 99 rows /srv/blind/secret.tsv <!-- -->'
        injected = tmp / 'INJECTED.md'
        injected.write_text('\n'.join(lines))
        check(injected, code=1, contains=('not generated from a template', 'placeholder left: TODO'),
              label='stamp-injection')
        # --template gives the sections the brief is checked against, and a slot name may be one letter.
        custom = tmp / 'custom' / 'task-brief.md'
        custom.parent.mkdir()
        custom.write_text(template.read_text().replace('## Goal and why', '## Context', 1).replace(
            '<goal:', 'Note: <a>.\n\n<goal:', 1))
        fields.write_text(text + 'a: hello\n')
        out = tmp / 'custom.md'
        make(fields, '--template', custom, '--out', out, code=0, label='custom-template')
        require('Note: hello.' in out.read_text() and '## Context' in out.read_text(), 'custom template not used')
        check(out, '--template', custom, code=0, contains=('generated=yes',), label='custom-template-checked')
        fields.write_text(text)
        # S14: the five domain templates have the seven sections and generate briefs that pass check_brief.
        for name in DOMAINS:
            raw = ROOT / 'templates' / 'briefs' / f'{name}.md'
            check(raw, '--hand-written', code=1, contains=('placeholder left: <unit id>',),
                  absent=('missing section', 'out of order', 'must carry the hand-back block', 'is empty'),
                  label=f'raw-{name}')
            domain_fields = tmp / f'{name}.fields'
            domain_fields.write_text(DOMAIN_FIELDS[name].replace('{tmp}', str(tmp)).replace('{root}', str(ROOT)))
            out = tmp / f'{name}.md'
            make(domain_fields, '--out', out, code=0, contains=('OK make_brief: wrote',), label=f'make-{name}')
            check(out, code=0, contains=DOMAIN_OK[name], absent=('ERROR',), label=f'check-{name}')
        spec = (tmp / 'spec-check.md').read_text()
        require('> A released buffer is never read again by a later step.' in spec, 'sentence not copied')
        triage = (tmp / 'triage.md').read_text()
        require(f'Judge each of the 2 rows of `{tmp}/viol-a.tsv` and `{tmp}/viol-b.tsv` where `known=no`' in triage,
                'triage count not computed')
        compare_header = (ROOT / 'templates' / 'writing-compare.tsv').read_text().splitlines()[0]
        require(f'header `{compare_header}`' in (tmp / 'comparison.md').read_text(), 'compare header missing')
        # S2 with a domain template: a spec-check brief turned into another one by substitution is refused.
        other = tmp / 'spec-check-SPEC-01.md'
        other.write_text(spec.replace('SPEC-02', 'SPEC-01').replace('SC-01', 'SC-02'))
        check(other, code=1, contains=('edited after it was generated',), label='domain-derived')
        stale = tmp / 'spec-check-stale.fields'
        stale.write_text(DOMAIN_FIELDS['spec-check'].replace('{tmp}', str(tmp)).replace(
            'a stand-in executor that lets the real core run.', 'the harness of the SPEC-01 check.'))
        make(stale, '--out', tmp / 'stale.md', code=1, contains=('id SPEC-01 is not in the ids listed',),
             label='domain-stale-id')
        leak = tmp / 'spec-check-leak.fields'
        leak.write_text(DOMAIN_FIELDS['spec-check'].replace('{tmp}', str(tmp)).replace(
            "  - `{0}/out/SC-02/`: another worker's folder.\n".format(tmp), '  - `{0}/`: everything else.\n'.format(tmp)))
        make(leak, '--out', tmp / 'leak.md', code=1, contains=('blind path', 'contains'), label='domain-blind-leak')
    require(before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in fixtures}, 'a fixture changed')
    print(f'PASS make_brief: base template and {len(DOMAINS)} domain templates generated and checked, '
          f'{len(refusals)} refused fields files, 14 refused or edited briefs, {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
