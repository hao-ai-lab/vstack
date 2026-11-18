#!/usr/bin/env python3
"""Exercise check_hygiene.py on generated good and bad trees.

The bad text is assembled at run time (code points, split strings) so that this repository's own hygiene scan
finds nothing in this file."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'lib'))
from gitrepo import Repo  # noqa: E402
SCRIPT = HERE.parents[1] / 'check_hygiene.py'
checks = 0
CJK = chr(0x4E2D) + chr(0x6587)
HOME = '/' + 'home/alice/'
MAC = '/' + 'Users/bob/'
WINDOWS = 'C:' + '\\Users\\carol\\notes.txt'
CLAUDE = 'https://claude' + '.ai/chat/0123abcd'
CHATGPT = 'https://chatgpt' + '.com/share/abc-123'
ALLOW = 'rule\tpath\treason\ncase-data\ttemplates/*\ttemplates hold neutral examples\n'
GOOD = {
    'README.md': '# Example\n\nPlain English text with a link to https://example.com/docs.\n',
    'data/cases.tsv': 'unit\tsite\nU-01\tsrc/pool.py:42\n',
    'templates/units.tsv': 'unit_id\tstatus\n',
    'scripts/hygiene-allow.tsv': ALLOW,
}
# name: (files to add or replace, extra arguments, expected fragments)
BAD = {
    'cjk-text': ({'notes.md': f'Intro\nmixed {CJK} text\n'}, [], [f'HIT cjk notes.md:2: {CJK}']),
    'cjk-file-name': ({f'{CJK}.md': 'English only\n'}, [], [f'HIT cjk {CJK}.md: file name: {CJK}']),
    'cjk-inside-data': ({'data/cases.tsv': f'unit\tsite\nU-01\t{CJK}\n'}, [], ['HIT cjk data/cases.tsv:2']),
    'home-path': ({'docs/setup.md': f'Run from {HOME}work.\n'}, [], [f'HIT personal-path docs/setup.md:1: {HOME}']),
    'mac-path': ({'docs/setup.md': f'Open {MAC}Desktop.\n'}, [], [f'HIT personal-path docs/setup.md:1: {MAC}']),
    'windows-path': ({'docs/setup.md': f'Copy {WINDOWS}.\n'}, [], ['HIT personal-path docs/setup.md:1: C:']),
    'chat-claude': ({'docs/notes.md': f'See {CLAUDE} for the thread.\n'}, [], [f'HIT chat-link docs/notes.md:1: {CLAUDE[8:]}']),
    'chat-gpt': ({'docs/notes.md': f'See {CHATGPT}.\n'}, [], [f'HIT chat-link docs/notes.md:1: {CHATGPT[8:]}']),
    'case-data-tsv': ({'notes/units.tsv': 'unit\n'}, [], ['HIT case-data notes/units.tsv: .tsv file outside data/']),
    'case-data-log': ({'run.log': 'done\n'}, [], ['HIT case-data run.log: .log file outside data/']),
    'not-utf8': ({'docs/latin.md': b'caf\xe9\n'}, [], ['HIT encoding docs/latin.md:1: not valid UTF-8']),
    'private-term': ({'README.md': 'Built for ProjectX.\nJob JOB-42 ran.\n'}, ['--deny', '{tmp}/deny.txt'],
                     ['HIT private-term README.md:1: ProjectX', 'HIT private-term README.md:2: JOB-42']),
    'allow-is-per-rule': ({'notes.md': f'{HOME}x\n', 'scripts/hygiene-allow.tsv': ALLOW + 'cjk\tnotes.md\tquoted\n'},
                          [], ['HIT personal-path notes.md:1', 'allow entry cjk notes.md excuses no hit']),
    'allow-without-reason': ({'scripts/hygiene-allow.tsv': ALLOW + 'cjk\tnotes.md\t\n'}, [],
                             ['every allow entry needs a path glob and a reason']),
    'allow-unknown-rule': ({'scripts/hygiene-allow.tsv': ALLOW + 'spelling\tREADME.md\tnames\n'}, [],
                           ["unknown rule 'spelling'"]),
    'allow-unused': ({'scripts/hygiene-allow.tsv': ALLOW + 'chat-link\tdocs/*\told links\n'}, [],
                     ['allow entry chat-link docs/* excuses no hit; remove it']),
    'allow-bad-header': ({'scripts/hygiene-allow.tsv': 'rule\tglob\n'}, [], ['header must be rule path reason']),
    'allow-missing': ({}, ['--allow', '{tmp}/absent.tsv'], ['ERROR ']),
    'deny-empty': ({}, ['--deny', '{tmp}/empty.txt'], ['no deny terms']),
    'deny-bad-regex': ({}, ['--deny', '{tmp}/badre.txt'], ['ERROR ']),
}


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
    if code in (0, 1) and '--help' not in args:
        last = output.splitlines()[-1]
        require(last.startswith('OK hygiene: ' if code == 0 else 'FAIL hygiene: '), f'{label}: last line {last!r}')
        # A brief matches the summary with 'last line ends with', so its last word is fixed.
        if code == 0 or 'HIT ' in output:
            require(last.endswith(' allowed' if code == 0 else ' files'), f'{label}: last word of {last!r}')
    checks += 1
    return output


def build(root, files):
    if root.exists():
        shutil.rmtree(root)
    for name, text in {**GOOD, **files}.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text if isinstance(text, bytes) else text.encode())
    (root / 'assets').mkdir(exist_ok=True)
    (root / 'assets' / 'logo.bin').write_bytes(b'\x89PNG\x00\x00' + CJK.encode() + HOME.encode())


def main():
    invoke('--help', code=0, contains=('personal-path', 'case-data'))
    invoke('--no-such-option', code=2, contains=('ERROR arguments:',))
    with tempfile.TemporaryDirectory(prefix='check-hygiene-') as directory:
        scratch = Path(directory)
        (scratch / 'deny.txt').write_text('# private terms\nprojectx\nre:\\bJOB-[0-9]+\n')
        (scratch / 'empty.txt').write_text('# nothing\n')
        (scratch / 'badre.txt').write_text('re:(\n')
        tree = scratch / 'tree'
        build(tree, {})
        invoke(tree, '--walk', code=0, contains=('OK hygiene: 5 files, 0 hits (private-term not run: no --deny); 1 allowed\n',),
               label='good')
        invoke(tree, '--walk', '--deny', scratch / 'deny.txt', code=0, contains=('OK hygiene: 5 files, 0 hits; 1 allowed\n',),
               label='good-with-deny')
        (tree / 'scripts' / 'hygiene-allow.tsv').write_text(ALLOW + 'private-term\tREADME.md\tproduct name\n')
        invoke(tree, '--walk', code=0, label='unrun-rule-entry-not-unused')
        for name, (files, extra, fragments) in BAD.items():
            build(tree, files)
            args = [arg.replace('{tmp}', str(scratch)) for arg in extra]
            invoke(tree, '--walk', *args, code=1, contains=fragments, label=name)
        build(tree, {})
        (tree / 'link.md').symlink_to(HOME + 'notes.md')
        invoke(tree, '--walk', code=1, contains=(f'HIT personal-path link.md:1: {HOME}',), label='symlink-target')
        (tree / 'link.md').unlink()
        (tree / '.git').mkdir()
        (tree / '.git' / 'notes.md').write_text(f'{CJK}\n')
        invoke(tree, '--walk', code=0, label='walk-skips-git-dir')
        plain = scratch / 'plain'
        build(plain, {})
        invoke(plain, code=1, contains=('ERROR ',), label='no-git-without-walk')
        invoke(scratch / 'absent', code=1, contains=('not a directory',), label='absent-root')
        empty = scratch / 'empty'
        empty.mkdir()
        invoke(empty, '--walk', code=1, contains=('no files to scan',), label='empty-tree')
        histories = commit_cases(scratch / 'history')
    print(f'PASS check_hygiene: 1 good tree, {len(BAD)} bad trees, {histories} histories, {checks} CLI checks')
    return 0


def commit_cases(root):
    """--commits: the tree is clean, but the push range still carries an uncleaned version."""
    clean = {**GOOD, 'docs/notes.md': 'Run from the project root.\n'}
    leaky = {**GOOD, 'docs/notes.md': f'Run from {HOME}work.\n'}
    repo = Repo(root)
    base = repo.commit(GOOD, 'base: published history')
    leak = repo.commit(leaky, 'docs: add notes')
    repo.commit(clean, 'docs: neutral paths in notes')
    repo.checkout_files(clean)
    head = repo.ref()
    cases = 0

    def run(spec, code, contains=(), label=''):
        nonlocal cases
        cases += 1
        return invoke(root, '--walk', '--commits', spec, code=code, contains=contains, label=label)

    # The past mistake: cleaning only the working tree. The tree scan passes; the commit scan does not.
    invoke(root, '--walk', code=0, label='history-tree-only-passes')
    run(f'{base}..main', 1, (f'HIT personal-path {leak[:12]}:docs/notes.md:1: {HOME}', '2 commits, '),
        'history-cleaned-later')
    run(f'{leak}..main', 0, ('OK hygiene: 1 commits, 1 file versions, 5 files, 0 hits',), 'history-after-the-leak')
    run('main..main', 1, ('the range has no commits',), 'history-empty-range')
    run(f'main..{base}', 1, ('the range has no commits',), 'history-reversed-range')
    run('nosuch..main', 1, ('ERROR ', 'rev-list failed'), 'history-unknown-base')
    invoke(root, '--walk', '--commits=--all', code=1, contains=('expected a revision range',), label='history-option')
    # A file added and deleted again inside the range, a message, a symlink and a side branch merged in.
    repo.commit({**clean, 'run.log': 'done\n'}, 'add a run log')
    repo.commit(clean, 'drop the run log')
    run(f'{head}..main', 1, ('HIT case-data ', ':run.log: .log file outside data/'), 'history-deleted-in-range')
    second = repo.commit(clean, f'notes\n\nSee {CHATGPT} for the thread.\n')
    run(f'{second}~1..main', 1, (f'HIT chat-link {second[:12]} message:3: {CHATGPT[8:]}',),
        'history-message')
    third = repo.commit({**clean, 'link.md': ('link', HOME + 'notes.md')}, 'add a link')
    repo.commit(clean, 'drop the link')
    run(f'{second}..main', 1, (f'HIT personal-path {third[:12]}:link.md:1: {HOME}',), 'history-symlink')
    fork = repo.ref()
    side = repo.commit({**clean, 'docs/side.md': f'{CJK}\n'}, 'side work', parents=[fork], ref='side')
    repo.commit({**clean, 'docs/side.md': 'side\n'}, 'side cleaned', ref='side')
    main_tip = repo.commit({**clean, 'docs/more.md': 'more\n'}, 'more docs')
    repo.commit({**clean, 'docs/more.md': 'more\n', 'docs/side.md': 'side\n'}, 'merge side',
                parents=[main_tip, repo.ref('side')])
    run(f'{fork}..main', 1, (f'HIT cjk {side[:12]}:docs/side.md:1: {CJK}',), 'history-merged-branch')
    # Allow entries excuse file versions by path, never messages; templates stay allowed in history too.
    tip = repo.ref()
    repo.commit({**clean, 'templates/units.tsv': 'unit_id\tstatus\tnote\n'}, 'template column')
    run(f'{tip}..main', 0, ('0 hits', '; 2 allowed'), 'history-allowed-template')
    return cases


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
