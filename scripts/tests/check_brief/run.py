#!/usr/bin/env python3
"""Exercise check_brief.py on a good brief, a bad brief, the template and single-defect variants of the good one."""

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / 'check_brief.py'
ROOT = HERE.parents[2]
HW = '--hand-written'
checks = 0


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def invoke(*args, code, contains=(), absent=(), label=''):
    global checks
    result = subprocess.run([sys.executable, '-B', str(SCRIPT), *map(str, args)],
                            capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    require(result.returncode == code, f'{label or args}: expected exit {code}, got {result.returncode}: {output}')
    for fragment in contains:
        require(fragment in output, f'{label or args}: missing {fragment!r} in {output}')
    for fragment in absent:
        require(fragment not in output, f'{label or args}: unexpected {fragment!r} in {output}')
    if code == 1:
        require(output.splitlines()[-1].startswith('FAIL brief: '), f'{label}: last line is not FAIL: {output}')
    checks += 1
    return output


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


AS_YOU_GO = 'Write each output file as you go, so that a partial result is usable.<br>'
GOAL_END = 'See <https://example.com/guide> for the method.'
SOURCE = '- `/srv/verify/source`: the pinned source tree.\n'
NO_GIT = '- No git commands that change state, no network, no sub-agents; never read `.env` files.\n'
PRODUCE = '- `WRITERS.tsv`: header `writer\tsite\tguard\tnote`.\n'
SUFFIX = 'last line ends with: `errors=0`'
EXACT = 'last line: `OK writers: 0 errors`'
WRITABLE = '- `/srv/verify/out/U-01/`\n'
BLIND_NO = '- Blind: no\n'
# Each variant applies one (old, new) replacement to good.md and must fail with the given fragment.
VARIANTS = {
    'missing-section': (('## Inputs\n', '## Inputs list\n'), "missing section '## Inputs'"),
    'comment-only-section': (('- `/srv/verify/inputs/U-01/resources.tsv`: the shared resource and its subsystems.\n'
                              '- `/srv/verify/source`: the pinned source tree.\n', '<!-- to do -->\n'),
                             "section 'Inputs' is empty"),
    'angle-placeholder': (('the pinned source tree', '<what the tree is>'), 'placeholder left: <what the tree is>'),
    'ellipsis-placeholder': (('the pinned source tree', '<...>'), 'placeholder left: <...>'),
    'name-placeholder': (('U-01, writers', '__UNIT__, writers'), 'placeholder left: __UNIT__'),
    'brace-placeholder': (('Source revision `abc1234`', 'Source revision {{revision}}'), 'placeholder left: {{revision}}'),
    'todo-placeholder': (('One row per write site.', 'TODO describe rows.'), 'placeholder left: TODO'),
    'placeholder-in-command': (('check_writers.py /srv', 'check_writers.py <table> /srv'), 'placeholder left: <table>'),
    'relative-writable': (('- `/srv/verify/out/U-01/`', '- `out/U-01/`'), 'writable path must be absolute: out/U-01/'),
    'dotdot-writable': (('- `/srv/verify/out/U-01/`', '- `/srv/verify/../U-01/`'), 'writable path must be canonical'),
    'prose-writable': (('- `/srv/verify/out/U-01/`\n- /srv/verify/scratch/U-01: scratch space\n',
                        'Only the output folder.\n'), 'no writable path listed as a list item'),
    'no-blind-line': ((BLIND_NO, ''), "exactly one line 'Blind: yes' or 'Blind: no'"),
    'bad-blind-value': (('- Blind: no', '- Blind: maybe'), "exactly one line 'Blind: yes' or 'Blind: no'"),
    'blind-without-paths': (('- Blind: no', '- Blind: yes'), 'Blind: yes needs a list item naming each absolute path'),
    'not-as-you-go': (('Write each output file as you go, so that a partial result is usable.',
                       'Write the files at the end.'), 'written as you go'),
    'no-command': (('- command: `python3 /srv/verify/tools/check_writers.py /srv/verify/out/U-01/WRITERS.tsv`\n'
                    '  last line: `OK writers: 0 errors`\n1. command: bash /srv/verify/tools/cites.sh /srv/verify/out/U-01\n'
                    '   last line ends with: `errors=0`\n', 'Run the checker until it passes.\n'),
                   'done evidence names no command'),
    'command-without-line': (('  last line: `OK writers: 0 errors`\n', ''), 'command has no expected last line'),
    'line-without-command': (('- command: `python3', '- run: `python3'), "'last line:' without a preceding 'command:'"),
    'empty-expected': (('last line: `OK writers: 0 errors`', 'last line:'), 'empty expected last line'),
    'no-handback-block': (('BEGIN HANDBACK\n', ''), 'missing BEGIN HANDBACK'),
    'handback-field-missing': (('rules broken: none, or each rule broken\n', ''), 'missing rules broken:'),
    'findings-without-grader': ((AS_YOU_GO, AS_YOU_GO + '\n\nAlso write the finding records in `FINDINGS.tsv`.'),
                                'the outputs include finding records: the done evidence must run'),
    'duplicate-section': (('## Inputs\n', '## Hand-back\n\nsee below\n\n## Inputs\n'), "section 'Hand-back' appears twice"),
    'empty-goal': (('The property owner wants every writer of the buffer slot table listed with its guard, so that the '
                    'model of unit\nU-01 starts from a complete census. Source revision `abc1234`. See '
                    '<https://example.com/guide> for the method.\n', ''), "section 'Goal and why' is empty"),
    # S13: placeholders. Usage syntax in code passes (see GOOD_VARIANTS); a spaced <...> in code, an undeclared
    # marker and a literal that would hide a placeholder word fail.
    'spaced-angle-in-code': ((SOURCE, '- `/srv/verify/source`: the tree, `<what the tree is>`.\n'),
                             'placeholder left: <what the tree is>'),
    'template-slot-in-code': ((GOAL_END, GOAL_END + ' Unit `<title: one line>`.'), 'placeholder left: <title: one line>'),
    'marker-undeclared': ((AS_YOU_GO, AS_YOU_GO + '\nKeep the marker `[TBD-cmp2]` where the count goes.'),
                          'placeholder left: TBD'),
    'dangling-slot': ((GOAL_END, GOAL_END + ' <context: one sentence on why'),
                      'placeholder left: <context: one sentence on why'),
    'literal-keyword': ((AS_YOU_GO, AS_YOU_GO + '\n- Literal: `TODO`: a word'), "literal 'TODO' would hide a placeholder"),
    'literal-slot': ((AS_YOU_GO, AS_YOU_GO + '\n- Literal: `<unit id>`: a slot'), 'would hide a placeholder'),
    # S16: an exact or suffix line that ends with '=' or ':' can never match a line carrying a value.
    'suffix-ends-with-equals': ((SUFFIX, 'last line ends with: `judged=`'), "ends with '=', so a real line carries"),
    'exact-ends-with-colon': ((EXACT, 'last line: `OK writers:`'), "ends with ':', so a real line carries"),
    'regex-invalid': ((SUFFIX, 'last line matches: `judged=[0-9`'), "'last line matches:' needs a regular expression"),
    'regex-accepts-anything': ((SUFFIX, 'last line matches: `.*`'), "accepts the line ''"),
    'regex-accepts-fail': ((SUFFIX, 'last line matches: `[A-Z]+`'), "accepts the line 'FAIL'"),
    # S17: a blind path that contains a path another section gives the worker (see also blind-contains-input).
    'blind-contains-writable': ((BLIND_NO, '- Blind: yes\n- `/srv/verify/out/`: every unit\'s output\n'),
                                'blind path /srv/verify/out/ contains /srv/verify/out/U-01/'),
    # S2: ids that the brief declares must exist; a stale id from another brief fails.
    'stale-id-inline': ((GOAL_END, GOAL_END + ' Compare SH13 and SH02; the notes of SH01 apply.\n\n'
                         '- ids: `SH[0-9][0-9]` only `SH13`, `SH02`'), 'id SH01 is not in the ids listed at line'),
    'ids-bad-regex': ((SOURCE, SOURCE + '- ids: `SH[` only `SH13`\n'), 'is not a regular expression'),
    'ids-empty-regex': ((SOURCE, SOURCE + '- ids: `x?` only `x`\n'), 'matches the empty string'),
    'declaration-garbled': ((SOURCE, SOURCE + '- ids: SH13 and SH02\n'), 'declaration not understood'),
    # S4: a header stated for a template must be that template's header.
    'header-drift': ((PRODUCE, '- `UNITS.tsv`: header `unit_id\tresource` (from `templates/unit-table.tsv`).\n'),
                     "differs from that template's header"),
    'header-missing-template': ((PRODUCE, '- `X.tsv`: header `a\tb` (from `templates/absent.tsv`).\n'),
                                'cannot read the header of templates/absent.tsv'),
    # S8: writable globs and except items.
    'except-outside': ((WRITABLE, WRITABLE + '- except `/srv/elsewhere/x.py`: not ours\n'),
                       "'except /srv/elsewhere/x.py' lies under no writable path"),
}
# Replacements that must still pass, with a fragment of the OK line.
GOOD_VARIANTS = {
    'usage-in-code': ((NO_GIT, NO_GIT + '- Python files only through `bash guard.sh 4 PYTHON <file> <args>`.\n'),
                      'OK brief:'),
    'id-in-code-path': ((PRODUCE, PRODUCE + '- `slides/<id>.html`: one page per unit.\n'), 'OK brief:'),
    'literal-marker': ((AS_YOU_GO, AS_YOU_GO + '\nKeep the marker `[TBD-cmp2]` where the count goes.\n\n'
                        '- Literal: `[TBD-cmp2]`: the marker the slide keeps until the count arrives.'), 'OK brief:'),
    'count-declared-literal': ((SOURCE, '- `/srv/verify/source/NOTES.md`: the 20 rows of its Markdown table.\n'
                                '- Literal: `20 rows`: rows of a Markdown table, not of a TSV file\n'), 'OK brief:'),
    'regex-last-line': ((SUFFIX, 'last line matches: `cites checked: [0-9]+, errors=0`'), '2 done checks'),
    'regex-named-group': ((SUFFIX, 'last line matches: `judged=(?P<n>[0-9]+); done`'), '2 done checks'),
    'blind-carve-out': ((BLIND_NO, '- Blind: yes\n- `/srv/verify/source/tests/answers/`: the answer key\n'),
                        'blind=yes'),
    'blind-sibling': ((BLIND_NO, '- Blind: yes\n- `/srv/verify/inputs/U-02/`: the next unit\n'), 'blind=yes'),
    'ids-inline': ((GOAL_END, GOAL_END + ' Compare SH13 and SH02.\n\n- ids: `SH[0-9][0-9]` only `SH13`, `SH02`'),
                   '1 id sets'),
    'writable-glob-except': ((WRITABLE, WRITABLE + '- `/srv/repo/scripts/check_*.py`\n'
                              '- except `/srv/repo/scripts/check_docs.py`: owned by the other worker\n'),
                             '3 writable paths'),
}


def main():
    good, bad, template = HERE / 'good.md', HERE / 'bad.md', ROOT / 'templates' / 'task-brief.md'
    before = {path: digest(path) for path in (good, bad, template)}
    invoke('--help', code=0, contains=('placeholder', 'last line matches'))
    invoke(code=2, contains=('ERROR arguments:',))
    invoke(good, HW, code=0, contains=('OK brief: 7 sections, 2 writable paths, 2 done checks, blind=no',
                                       'generated=no'), absent=('ERROR',))
    invoke(good, code=1, contains=('not generated from a template',), label='hand-written-refused')
    invoke(bad, HW, code=1, contains=(
        'placeholder left: __UNIT__', 'placeholder left: <resource name>', 'placeholder left: TODO',
        'sections out of order', 'writable path must be absolute: out/U-01/', 'Blind: yes needs a list item',
        'written as you go', 'done evidence names no command', 'hand-back section must carry the hand-back block'))
    invoke(template, HW, code=1, contains=('placeholder left: <unit id>', 'placeholder left: <blind: yes or no>',
                                           'placeholder left: <reply: what the reply says above the block, or nothing>'),
           absent=('missing section', 'out of order', 'must carry the hand-back block', 'is empty'), label='template')
    text = good.read_text()
    unit_header = (ROOT / 'templates' / 'unit-table.tsv').read_text().splitlines()[0]
    with tempfile.TemporaryDirectory(prefix='check-brief-') as directory:
        scratch = Path(directory)
        brief = scratch / 'BRIEF.md'
        # S20 fixtures: six failure tables holding 27 data rows in all. Skipping only the first file's header, as
        # `awk 'NR>1'` over all of them does, also counts the five other headers (32). File 2's comment and blank
        # line never count.
        files = []
        for index, rows in enumerate((5, 4, 6, 3, 5, 4), 1):
            path = scratch / f'fail-{index}.tsv'
            body = ''.join(f'V{index}-{n}\t{"" if n % 2 else "defect"}\n' for n in range(rows))
            path.write_text('violation\tverdict\n' + ('# comment\n\n' if index == 2 else '') + body)
            files.append(path)
        undecided = sum(1 for index, rows in enumerate((5, 4, 6, 3, 5, 4), 1) for n in range(rows) if n % 2)
        listed = ', '.join(f'`{path}`' for path in files[:-1]) + f' and `{files[-1]}`'
        (scratch / 'specs.tsv').write_text('spec_id\tsentence\nSTD-P02-14\tone\nSTD-P03-21\ttwo\n')
        specs = scratch / 'specs.tsv'
        local = {
            'blind-contains-input': ((BLIND_NO + '- Every', '- Blind: yes\n- `/srv/verify/table/`: later tables\n- Every'),
                                     'blind path /srv/verify/table/ contains /srv/verify/table/v0.1/out/Specs.tsv'),
            'count-naive': ((GOAL_END, GOAL_END + f' Judge the 32 rows of {listed}.'),
                            'the brief says 32 rows of'),
            'count-bare': ((GOAL_END, GOAL_END + ' There are 32 more failing rows.'),
                           "row count '32 more failing rows' is not tied to its files"),
            'count-relative': ((GOAL_END, GOAL_END + ' Judge the 5 rows of `fail-1.tsv`.'),
                               'a counted file must be an absolute path: fail-1.tsv'),
            'count-bad-column': ((GOAL_END, GOAL_END + f' Judge the 5 rows of `{files[0]}` where `status=open`.'),
                                 "has no column 'status'"),
            'stale-id-table': ((GOAL_END, GOAL_END + ' Check STD-P02-14 and STD-P99-01.\n\n'
                                f'- ids: `STD-P[0-9]{{2}}-[0-9]{{2}}` from `{specs}` column `spec_id`'),
                               f'id STD-P99-01 is not in {specs} column spec_id'),
            'ids-missing-column': ((SOURCE, SOURCE + f'- ids: `STD-P[0-9]+` from `{specs}` column `absent`\n'),
                                   f'cannot read ids from {specs}'),
            'ref-missing-table': ((PRODUCE, PRODUCE + f'- ref: `WRITERS.tsv` column `spec` -> `{scratch}/absent.tsv` '
                                   'column `spec_id`\n'), 'ref table'),
            'ref-relative-table': ((PRODUCE, PRODUCE + '- ref: `WRITERS.tsv` column `spec` -> `specs.tsv` column '
                                    '`spec_id`\n'), 'ref table must be an absolute path'),
            'ref-outside-writable': ((PRODUCE, PRODUCE + f'- ref: `/srv/elsewhere/W.tsv` column `spec` -> `{specs}` '
                                      'column `spec_id`\n'), 'ref output /srv/elsewhere/W.tsv lies outside'),
        }
        local_good = {
            'count-right': ((GOAL_END, GOAL_END + f' Judge the 27 rows of {listed}.'), '1 counts'),
            'count-where': ((GOAL_END, GOAL_END + f' Judge the {undecided} rows of {listed} where `verdict=`.'),
                            '1 counts'),
            'count-where-not': ((GOAL_END, GOAL_END + f' Skip the {27 - undecided} rows of {listed} where '
                                 '`verdict!=`.'), '1 counts'),
            'ids-table': ((GOAL_END, GOAL_END + ' Check STD-P02-14.\n\n'
                           f'- ids: `STD-P[0-9]{{2}}-[0-9]{{2}}` from `{specs}` column `spec_id`'), '1 id sets'),
            'ref-declared': ((PRODUCE, PRODUCE + f'- ref: `WRITERS.tsv` column `spec` -> `{specs}` column `spec_id`\n'),
                             '1 refs'),
            'header-from-template': ((PRODUCE, f'- `UNITS.tsv`: header `{unit_header}` (from '
                                      '`templates/unit-table.tsv`).\n'), 'OK brief:'),
        }
        for name, ((old, new), fragment) in {**VARIANTS, **local}.items():
            require(old in text, f'{name}: fixture text not found')
            changed = text.replace(old, new, 1)
            if name == 'blind-contains-input':
                changed = changed.replace(SOURCE, SOURCE + '- `/srv/verify/table/v0.1/out/Specs.tsv`: the specs.\n')
            brief.write_text(changed)
            invoke(brief, HW, code=1, contains=(fragment,), label=name)
        for name, ((old, new), fragment) in {**GOOD_VARIANTS, **local_good}.items():
            require(old in text, f'{name}: fixture text not found')
            brief.write_text(text.replace(old, new, 1))
            invoke(brief, HW, code=0, contains=(fragment,), absent=('ERROR',), label=name)
        order = text.replace('## Writable paths\n', '## Writable paths moved\n', 1).replace(
            '## Done evidence\n', '## Writable paths\n\n- `/srv/verify/out/U-01/`\n\n## Done evidence\n', 1)
        brief.write_text(order)
        invoke(brief, HW, code=1, contains=('sections out of order',))
        blind = text.replace('- Blind: no', '- Blind: yes\n- `/srv/verify/answers/`: the known results', 1)
        brief.write_text(blind)
        invoke(brief, HW, code=0, contains=('blind=yes',))
        brief.write_text(text.replace('## Hand-back', '## Notes\n\nExtra sections are allowed.\n\n## Hand-back', 1))
        invoke(brief, HW, code=0, contains=('OK brief: 7 sections',))
        graded = text.replace(AS_YOU_GO, AS_YOU_GO + '\n\n- `FINDINGS.tsv`: finding records.', 1).replace(
            'python3 /srv/verify/tools/check_writers.py /srv/verify/out/U-01/WRITERS.tsv',
            'python3 scripts/grade_findings.py /srv/verify/out/U-01/FINDINGS.tsv', 1)
        brief.write_text(graded)
        invoke(brief, HW, code=0, contains=('2 done checks',), label='findings-with-grader')
        # S4: sections and hand-back fields come from the template, not from a list in the checker.
        sections = scratch / 'sections' / 'task-brief.md'
        sections.parent.mkdir()
        sections.write_text(template.read_text().replace('## Hand-back', '## Budget\n\nHours.\n\n## Hand-back', 1))
        invoke(good, HW, '--template', sections, code=1, contains=("missing section '## Budget'",),
               label='template-adds-section')
        fields = scratch / 'fields' / 'task-brief.md'
        fields.parent.mkdir()
        fields.write_text(template.read_text().replace('rules broken: none', 'budget: hours used\nrules broken: none', 1))
        invoke(good, HW, '--template', fields, code=1, contains=('missing budget:',), label='template-adds-field')
        invoke(good, HW, '--template', scratch / 'absent.md', code=1, contains=('ERROR template:',),
               label='template-missing')
        brief.write_bytes(b'\xff\xfe')
        invoke(brief, HW, code=1, contains=('ERROR',))
        invoke(scratch / 'absent.md', code=1, contains=('ERROR',), absent=('not generated',))
    require(before == {path: digest(path) for path in before}, 'a fixture changed')
    total = len(VARIANTS) + len(local)
    print(f'PASS check_brief: 1 good brief, 1 bad brief, the template, {total} defect variants, '
          f'{len(GOOD_VARIANTS) + len(local_good)} passing variants, {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
