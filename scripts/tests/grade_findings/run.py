#!/usr/bin/env python3
"""Exercise the CLI against fixed good/bad fixtures and temporary malformed records."""

import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / 'grade_findings.py'
ROOT = HERE.parents[2]
checks = 0


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def invoke(*args, ok, contains=None):
    global checks
    result = subprocess.run([sys.executable, '-B', str(SCRIPT), *map(str, args)],
                            capture_output=True, text=True, timeout=10)
    require((result.returncode == 0) == ok,
            f'{args}: expected success={ok}, got {result.returncode}: {result.stdout}{result.stderr}')
    if not ok:
        require(result.stderr and all(line.startswith('ERROR ') for line in result.stderr.splitlines()),
                f'{args}: missing structured errors: {result.stderr}')
    for part in (contains,) if isinstance(contains, str) else contains or ():
        require(part in result.stdout + result.stderr, f'{args}: missing {part!r}')
    checks += 1
    return result


def read(path):
    with path.open(newline='') as stream:
        reader = csv.DictReader((line for line in stream if line.strip() and not line.startswith('#')), delimiter='\t')
        return reader.fieldnames, list(reader)


def write(path, header, rows, comment=False):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=header, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        if comment:
            stream.write('# preserve this comment\n\n')
        writer.writerows(rows)


def main():
    header, good = read(HERE / 'good.tsv')
    _, bad = read(HERE / 'bad.tsv')
    original_good = (HERE / 'good.tsv').read_bytes()
    original_bad = (HERE / 'bad.tsv').read_bytes()
    invoke('--help', ok=True, contains='Positional arguments')
    invoke(ok=False, contains='ERROR arguments:')
    invoke(HERE / 'good.tsv', ok=True, contains=f'{len(good)} findings checked')
    invoke(HERE / 'bad.tsv', ok=False)
    invoke(ROOT / 'templates/finding-record.tsv', ok=False, contains='no finding records')
    with tempfile.TemporaryDirectory(prefix='grade-findings-') as directory:
        scratch = Path(directory)
        source = scratch / 'record.tsv'
        output = scratch / 'computed.tsv'
        # Independent expectations in good.tsv are compared with fully recomputed columns.
        blank = [dict(row, non_default_settings='stale', tier='', grade='', route='') for row in good]
        write(source, header, blank, comment=True)
        before = source.read_bytes()
        invoke(source, '--write', output, ok=True)
        actual = read(output)[1]
        require(actual == good, 'computed columns differ from the fixed expected table: ' +
                repr([(want['finding_id'], want, got) for want, got in zip(good, actual) if want != got]))
        require('# preserve this comment\n\n' in output.read_text(), 'comments were lost')
        require(source.read_bytes() == before, 'input changed during --write')
        invoke(output, ok=True)
        second = scratch / 'second.tsv'
        invoke(output, '--write', second, ok=True)
        require(second.read_bytes() == output.read_bytes(), 'output does not stabilize on revalidation')
        expected = {
            'missing-reference': ':arm_reference:', 'self-review': ':reviewer:',
            'wrong-grade': ':grade:', 'wrong-tier': ':tier:', 'wrong-route': ':route:',
            'missing-kind': ':reference_kind:', 'bad-method': ':method:', 'bad-count': ':hits:',
            'zero-arm-runs': ':arm_reference:', 'missing-entrypoint': ':entrypoint:',
            'unclosed-command': ':launch_cmd:', 'no-command': ':launch_cmd:',
            'missing-reviewer': ':reviewer:', 'mixed-arms': ':arm_reference:',
            'bad-gate': ':gate1b:', 'bad-evidence': ':evidence_level:', 'missing-injected': ':injected:',
            # Verdicts: confidence never caps the grade; narrow and undetermined need their facts.
            'narrow-no-condition': ':review_verdict:', 'undetermined-no-unknown': ':review_verdict:',
            'narrow-capped': ':grade:', 'spec-graded': ':grade:', 'partial-routed': ':route:',
            # Launch commands: placeholders are refused, unknown is never tier0, same executable.
            'placeholder-launch': ':launch_cmd:', 'placeholder-both': ':default_launch_cmd:',
            'other-executable': ':launch_cmd:', 'unknown-tier0': ':tier:', 'unknown-graded': ':grade:',
            # Free text in structured fields.
            'free-hit-unit': ':hit_unit:', 'free-commit': ':upstream_checked_at:',
            'free-dup-search': ':dup_search:', 'free-reviewer': ':reviewer:', 'free-injected': ':injected:',
            'free-precondition': ':preconditions:', 'bad-precondition-kind': ':preconditions:',
            'empty-precondition-text': ':preconditions:', 'missing-preconditions': ':preconditions:',
            'control-external': ':entry_kind:',
            # Hit counts carry their kind.
            'zero-random': ':hit_kind:', 'none-with-runs': ':hit_kind:', 'missing-hit-kind': ':hit_kind:',
            # Ambiguous facts must be recorded at their lower reading.
            'higher-reading': ':ambiguous_facts:', 'higher-serious': ':ambiguous_facts:',
            'bad-ambiguous-field': ':ambiguous_facts:', 'same-ambiguous': ':ambiguous_facts:',
            'ambiguous-unknown': ':ambiguous_facts:', 'ambiguous-contradicts-control': ':ambiguous_facts:',
            # A consequence that is not serious says why; a wrong output of the request itself is serious.
            'own-output-not-serious': ':impact:', 'no-without-class': ':impact:',
            'serious-with-minor-class': ':impact:', 'empty-class-text': ':impact:', 'private-no-class': ':impact:',
            'unknown-class': ':impact:',
            # A service-ending effect needs the availability marker, and the refusal names the marker and the class.
            'exit-unmarked': (':impact: states a process exit', 'availability: marker'),
            'engine-dead-unmarked': (':impact: states a process exit', 'availability: marker'),
            'refused-unmarked': (':impact: states refused new requests', 'availability: marker'),
            'later-fail-unmarked': (':impact: states refused new requests', 'availability: marker'),
            'inflight-unmarked': (':impact: states failure of other in-flight requests', 'availability: marker'),
            'cross-only-exit': (':impact: states a process exit', 'availability: marker'),
            'marker-late': (':impact: states a process exit', 'availability: marker'),
            'dos-unmarked': (':impact: states failure of other in-flight requests', 'availability: marker'),
            'marker-no-text':':impact: a marker needs the concrete impact',
            'availability-wrong-route': ":route: stored 'upstream_report' differs from computed 'private_report'",
            'availability-serious-class': ':impact: error: names a consequence that is not serious',
        }
        require(set(expected) == {row['finding_id'] for row in bad}, 'bad fixtures and expectations differ')
        for row in bad:
            write(source, header, [row])
            rejected = scratch / 'rejected.tsv'
            invoke(source, '--write', rejected, ok=False, contains=expected[row['finding_id']])
            require(not rejected.exists(), 'invalid input created an output')
        for field in ('method', 'found_by', 'gate1a', 'gate1b', 'evidence_level', 'entry_kind',
                      'single_model_only', 'hit_kind', 'reference_kind', 'serious_consequence', 'review_verdict',
                      'tier', 'grade', 'route'):
            write(source, header, [dict(good[0], **{field: 'invalid'})])
            invoke(source, ok=False, contains=f':{field}:')
        # unknown is accepted only for the facts the grading rules name.
        for field in ('method', 'found_by', 'gate1a', 'gate1b', 'evidence_level', 'single_model_only',
                      'hit_kind', 'reference_kind', 'review_verdict', 'injected', 'hits', 'arm_stock'):
            write(source, header, [dict(good[0], **{field: 'unknown'})])
            invoke(source, ok=False, contains=f':{field}:')
        # The template's commented examples are valid records with correct computed columns.
        examples = [line[2:] for line in (ROOT / 'templates/finding-record.tsv').read_text().splitlines(True)
                    if line.startswith('# ')]
        source.write_text('\t'.join(header) + '\n' + ''.join(examples))
        invoke(source, ok=True, contains=f'{len(examples)} findings checked')
        for fields in (header[:-1], list(reversed(header)), header + ['extra']):
            source.write_text('\t'.join(fields) + '\n')
            invoke(source, ok=False, contains='header must be')
        write(source, header, [])
        invoke(source, ok=False, contains='no finding records')
        source.write_text('')
        invoke(source, ok=False, contains='missing header')
        source.write_text('\t'.join(header) + '\nshort\n')
        invoke(source, ok=False, contains=f'expected {len(header)} columns')
        source.write_text('\t'.join(header) + '\n"unterminated\n')
        invoke(source, ok=False, contains='invalid TSV')
        source.write_bytes(b'\xff')
        invoke(source, ok=False, contains='ERROR ')
        write(source, header, [good[0], good[0]])
        invoke(source, ok=False, contains='duplicate finding_id')
        for field, value in (('hits', '-1'), ('runs', 'unknown'), ('arm_stock', '4/3'),
                             ('arm_patched', '-1/3'), ('summary', 'line\nbreak')):
            write(source, header, [dict(good[0], **{field: value})])
            invoke(source, ok=False)
        no_fix = dict(good[0], arm_stock='n/a', arm_patched='n/a', arm_reference='n/a')
        write(source, header, [no_fix])
        invoke(source, ok=False, contains='must be n/a when no fix is claimed')
        write(source, header, [good[0]])
        before = source.read_bytes()
        invoke(source, '--write', source, ok=False, contains='output must be a new file')
        alias = scratch / 'alias.tsv'
        alias.symlink_to(source)
        invoke(source, '--write', alias, ok=False, contains='output must be a new file')
        hardlink = scratch / 'hardlink.tsv'
        os.link(source, hardlink)
        invoke(source, '--write', hardlink, ok=False, contains='output must be a new file')
        existing = scratch / 'existing.tsv'
        existing.write_text('keep this output\n')
        invoke(source, '--write', existing, ok=False, contains='output must be a new file')
        require(existing.read_text() == 'keep this output\n', 'existing output changed')
        require(source.read_bytes() == before, 'input changed through alias or in-place output')
        invoke(scratch / 'absent.tsv', ok=False, contains='ERROR ')
        invoke(source, '--write', scratch / 'missing-parent' / 'out.tsv', ok=False, contains='ERROR ')
    require((HERE / 'good.tsv').read_bytes() == original_good, 'good fixture changed')
    require((HERE / 'bad.tsv').read_bytes() == original_bad, 'bad fixture changed')
    print(f'PASS grade_findings: {len(good)} good rows, {len(bad)} bad fixtures, {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
