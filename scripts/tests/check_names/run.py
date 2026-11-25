#!/usr/bin/env python3
"""Exercise check_names.py on a generated source tree and good and bad tables.

The bad rows repeat a mistake seen in use: a sentence named an abbreviated class (a prefix of the real class name)
and passed every other check."""

from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / 'check_names.py'
checks = 0
SOURCE = {
    'engine/spec.py': (
        'class MultiModuleMTPSpeculator:\n'
        '    """Proposes draft tokens; see GhostInDocstring."""\n'
        '    def propose(self, batch):\n'
        '        self.pending_ids = []\n'
        '        # GhostClass is mentioned only in this comment\n'
        '        return batch["max_tokens"]\n'
        '\n'
        'def free_slots(pool):\n'
        '    return pool\n'),
    'kernels/copy.cu': '// GhostKernel only in a comment\n__global__ void copy_blocks_kernel(int* slot_map) {}\n',
    # Inputs of an outside review of 0.125.0: a // inside a string literal is not a comment, and a docstring that
    # is one word is prose.
    'kernels/url.cpp': 'const char* u = "http://example.com"; int real_var = 1; /* GhostBlock */ char c = \'/\';\n',
    'engine/doc.py': '"""GhostModuleDoc"""\n\nclass Holder:\n    """GhostClassDoc"""\n    key = "slot_key"\n',
    'docs/notes.md': 'ManagerInDocs is described here but defined nowhere.\n',
}
GOOD = {
    'g-class-method': '`MultiModuleMTPSpeculator.propose` sets `self.pending_ids` before it returns',
    'g-call-and-key': 'free_slots() returns every slot; the request max_tokens bounds the batch',
    'g-plural': 'Each of the MultiModuleMTPSpeculators proposes draft tokens',
    'g-pattern': 'The `*_slots` helpers and copy_blocks_kernel(slot_map) agree, e.g. for v0.4',
    'g-path': 'Read at engine/spec.py:4 and kernels/copy.cu:2 at the pinned commit',
    'g-allowed': 'FlashInfer kernels read the pool after propose()',
    'g-literals': 'Calling `propose(batch)` with `"<think>"` and `--max-num-seqs 4` keeps the order',
    'g-after-url-string': 'real_var is set once; Holder keeps slot_key',
}
# id: (sentence, names the check must report, in order)
BAD = {
    'b-abbreviated-class': ('MultiModuleMTP proposes draft tokens', ['MultiModuleMTP']),
    'b-comment-only': ('GhostClass holds the slots; GhostKernel copies them', ['GhostClass', 'GhostKernel']),
    'b-docstring-only': ('GhostInDocstring keeps the queue', ['GhostInDocstring']),
    'b-singular': ('`free_slot` releases one slot', ['free_slot']),
    'b-pattern': ('The `*_ghost` helpers free the slots', ['*_ghost']),
    'b-path': ('Read at engine/sched.py:10', ['engine/sched.py']),
    'b-document-only': ('ManagerInDocs owns the pool', ['ManagerInDocs']),
    'b-typo': ('copy_block_kernel writes the slot map', ['copy_block_kernel']),
    'b-dotted-member': ('`MultiModuleMTPSpeculator.propose_all` runs first', ['propose_all']),
    'b-one-word-docstring': ('GhostModuleDoc and GhostClassDoc hold the slots', ['GhostModuleDoc', 'GhostClassDoc']),
    'b-block-comment': ('GhostBlock copies them', ['GhostBlock']),
}


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
    if code in (0, 1) and '--help' not in args:
        last = output.splitlines()[-1]
        require(last.startswith('OK names: ' if code == 0 else 'FAIL names: '), f'{label}: last line {last!r}')
    checks += 1
    return output


def table(path, rows, header='id\tsentence\tnote'):
    path.write_text(header + '\n' + ''.join(f'{key}\t{text}\tfree note GhostNote\n' for key, text in rows.items()))
    return path


def main():
    invoke('--help', code=0, contains=('abbreviated class name',))
    invoke('src', 'table.tsv', code=2, contains=('ERROR arguments:',), label='no-column')
    with tempfile.TemporaryDirectory(prefix='check-names-') as directory:
        scratch = Path(directory)
        source = scratch / 'src'
        for name, text in SOURCE.items():
            (source / name).parent.mkdir(parents=True, exist_ok=True)
            (source / name).write_text(text)
        allow = scratch / 'allow.tsv'
        allow.write_text('name\treason\nFlashInfer\ta product name, not a code identifier\n')
        good = table(scratch / 'good.tsv', GOOD)
        invoke(source, good, '--column', 'sentence', '--allow', allow, code=0,
               contains=(f'OK names: {len(GOOD)} rows',), label='good')
        # The note column is not checked unless named.
        invoke(source, good, '--column', 'sentence', '--column', 'note', '--allow', allow, code=1,
               contains=('note: not in the source: GhostNote',), label='second-column')
        invoke(source, good, '--column', 'sentence', code=1, contains=('g-allowed sentence: not in the source: '
                                                                         'FlashInfer',), label='allow-needed')
        bad = table(scratch / 'bad.tsv', {key: text for key, (text, _) in BAD.items()})
        invoke(source, bad, '--column', 'sentence', code=1,
               contains=(f'FAIL names: {len(BAD)} of {len(BAD)} rows',), label='bad')
        for key, (text, names) in BAD.items():
            one = table(scratch / 'one.tsv', {key: text})
            invoke(source, one, '--column', 'sentence', code=1,
                   contains=(f'{key} sentence: not in the source: {", ".join(names)}\n',), label=key)
        unused = scratch / 'unused.tsv'
        unused.write_text('name\treason\nFlashInfer\tproduct\nDeepSeek\tproduct\n')
        invoke(source, good, '--column', 'sentence', '--allow', unused, code=1,
               contains=("entry 'DeepSeek' excuses no word",), label='allow-unused')
        noreason = scratch / 'noreason.tsv'
        noreason.write_text('name\treason\nFlashInfer\t\n')
        invoke(source, good, '--column', 'sentence', '--allow', noreason, code=1,
               contains=('needs a name and a reason',), label='allow-without-reason')
        invoke(source, good, '--column', 'claim', code=1, contains=('no column claim',), label='absent-column')
        invoke(source, good, '--column', 'sentence', '--id-column', 'row', code=1, contains=('no column row',),
               label='absent-id-column')
        renamed = table(scratch / 'renamed.tsv', {'x': 'MultiModuleMTP runs'}, header='note\tsentence\tid')
        invoke(source, renamed, '--column', 'sentence', '--id-column', 'id', code=1,
               contains=('renamed.tsv:2 free note GhostNote sentence:',), label='id-column')
        short = scratch / 'short.tsv'
        short.write_text('id\tsentence\tnote\nonly-two\tfree_slots()\n')
        invoke(source, short, '--column', 'sentence', code=1, contains=('expected 3 columns',), label='short-row')
        empty_table = scratch / 'empty.tsv'
        empty_table.write_text('id\tsentence\tnote\n# a comment row\n')
        invoke(source, empty_table, '--column', 'sentence', code=1, contains=('no rows',), label='no-rows')
        docs_only = scratch / 'docs-only'
        (docs_only / 'docs').mkdir(parents=True)
        (docs_only / 'docs' / 'notes.md').write_text(SOURCE['docs/notes.md'])
        invoke(docs_only, good, '--column', 'sentence', code=1, contains=('no source files',), label='no-code')
        invoke(scratch / 'absent', good, '--column', 'sentence', code=1, contains=('not a directory',),
               label='absent-source')
        invoke(source, scratch / 'absent.tsv', '--column', 'sentence', code=1, contains=('ERROR ',),
               label='absent-table')
    print(f'PASS check_names: {len(GOOD)} good rows, {len(BAD)} bad rows, {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
