#!/usr/bin/env python3
"""Exercise refuse_inline_python.py on commands to refuse and commands to allow, in both input modes.

The first refused command is the mistake seen in use: three agents each typed python3 - once, although their
briefs forbade inline Python."""

import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / 'refuse_inline_python.py'
GUARD = 'compute/guard.sh'
checks = 0
REFUSE = [
    'python3 -',
    'python3 - < /dev/null',
    "python3 -c 'print(1)'",
    "python -c 'import os'",
    "/usr/bin/python3 -B -c 'x = 1'",
    "python3 -Bc 'x'",
    'python3.12 -I -c pass',
    'pypy3 -',
    'ipython -c pass',
    'cd /tmp && python3 -c pass',
    'ls; python3 -c pass',
    'make || python3 -c pass',
    'echo x | python3',
    'cat a.py | python3 -',
    "python3 <<'EOF'\nprint(1)\nEOF",
    "python3 <<< 'print(1)'",
    'python3 < script.py',
    'bash -c "python3 -c \'print(1)\'"',
    "bash -lc 'python3 -'",
    "sh -c 'cd x && python3 -c pass'",
    'eval "python3 -c pass"',
    "echo $(python3 -c 'print(1)')",
    'echo "$(python3 -c \'print(1)\')"',
    "echo `python3 -c 'print(1)'`",
    'diff <(python3 -c pass) b.txt',
    'env A=1 python3 -c pass',
    'A=1 B=2 python3 -c pass',
    'nice -n 19 timeout 60 python3 -c pass',
    'timeout --signal KILL 5s python3 -',
    'taskset -c 0-3 python3 -c pass',
    'sudo -u bob python3 -c pass',
    'exec python3 -c pass',
    'uv run --with numpy python -c pass',
    'conda run -n env python -c pass',
    "find . -name '*.py' -exec python3 -c pass {} \\;",
    'xargs -n 1 python3 -c pass',
    "env -S 'python3 -c pass'",
    'for f in a b; do python3 -c pass; done',
    "if python3 -c 'import x'; then echo ok; fi",
    'echo hi # a comment\npython3 -c pass',
    'python3 -X dev -c pass',
    'python3 -W ignore -i',
    '( python3 -c pass )',
    "python3 -c 'print(1)",
    f'bash {GUARD} agent 4 /usr/bin/bash t/run.sh; python3 -c pass',
    # Inputs of an outside review of 0.125.0 that passed before 0.126.0.
    "echo 'print(1)' | python3 -- -",
    'python3 -- - <<EOF\nprint(1)\nEOF',
    "2>/dev/null python3 -c 'print(1)'",
    "python3 2>&1 -c 'print(1)'",
    "python3 0<<<'print(1)'",
    'echo "<<EOF"\npython3 -c \'print(1)\'',
    "# note <<EOF\npython3 -c 'print(1)'",
    '<<EOF python3\nprint(1)\nEOF',
    '<<EOF bash\npython3 -c \'print(1)\'\nEOF',
    "# check the table's rows\npython3 <<'EOF'\nprint(1)\nEOF",
    "# it's ok\npython3 -B -c \"print(1)\"",
    "echo \"$(echo ')'; python3 -c 'print(1)')\"",
    "env -S \"\" python3 -c 'print(1)'",
    "env -iS \"python3 -c 'print(1)'\"",
    "env \"-Spython3 -c 'print(1)'\"",
    "env --split-string=python3 -c 'print(1)'",
    "uv -q run python3 -c 'print(1)'",
    "uv --directory /tmp run python3 -c 'print(1)'",
    'bash --init-file /dev/null -c \'python3 -c "print(1)"\'',
    'bash --rcfile /dev/null -c \'python3 -c "print(1)"\'',
    "eval -- \"python3 -c 'print(1)'\"",
    "flock /tmp/lock -c \"python3 -c 'print(1)'\"",
    "py\\\nthon3 -c 'print(1)'",
    "coproc python3 -c 'print(1)'",
    "coproc worker { python3 -c 'print(1)'; }",
    "echo 'print(1)' | python3 /dev/stdin",
    'python3 /dev/stdin <<EOF\nprint(1)\nEOF',
    'python3 /proc/self/fd/0 < /dev/null',
    "python3 $'-c' pass",
]
ALLOW = [
    'python3 script.py',
    'python3 -B script.py --flag -c',
    'python3 -m pytest -q',
    'python3 -Bm json.tool data.json',
    'python3 --version',
    'python3 -V',
    'python3 -h',
    '/usr/bin/python3 -I -B -X dev tool.py',
    'python3 -- script.py',
    f'bash {GUARD} agent 4 /usr/bin/python3 -B file.py',
    f"bash /srv/project/{GUARD} agent 4 python3 -c 'print(1)'",
    f'{GUARD} agent 4 python3 -',
    f'cd /x && bash {GUARD} agent 4 /usr/bin/bash t/run.sh',
    f'bash {GUARD} agent 4 \\\n  /usr/bin/python3 -c pass',
    'which python3',
    'command -v python3',
    'type python3',
    'ls /usr/bin/python3*',
    "grep -n 'python3 -c' notes.md",
    "git commit -m 'python3 - is refused'",
    'echo python3 -c',
    "cat > run.sh <<'EOF'\npython3 -c pass\nEOF",
    'ps aux | grep python3',
    'python3-config --includes',
    'uv pip install numpy',
    'bash run.sh',
    'timeout 60 python3 run.py',
    'echo "the -c flag" # python3 -c in a comment',
    # Inputs of an outside review of 0.125.0 that were refused before 0.126.0.
    'python3 <<EOF script.py\ninput data\nEOF',
    "cat <<\\EOF > doc.md\npython3 -c 'example'\nEOF",
    "# don't use python3 -c\ngit status",
    'echo "2 > 1" && python3 tool.py 2>/dev/null',
    "env -u PYTHONPATH -i python3 tool.py",
    'bash --norc tool.sh',
    "echo '$(python3 -c pass)'",
    'python3 -- tool.py',
]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run(args, code, stdin=None, contains=(), label=''):
    global checks
    result = subprocess.run([sys.executable, '-B', str(SCRIPT), *args], input=stdin,
                            capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    require(result.returncode == code, f'{label or args}: expected exit {code}, got {result.returncode}: {output}')
    for fragment in contains:
        require(fragment in output, f'{label or args}: missing {fragment!r} in {output}')
    checks += 1
    return output


def main():
    run(['--help'], 0, contains=('PreToolUse',))
    run(['--no-such-option'], 1, contains=('ERROR arguments:',))
    for command in REFUSE:
        run(['--guard', GUARD, '--command', command], 2, contains=('refused: inline Python',), label=repr(command))
    for command in ALLOW:
        run(['--guard', GUARD, '--command', command], 0, label=repr(command))
    # Hook mode: the JSON a Claude Code PreToolUse hook receives.
    event = {'session_id': 's', 'tool_name': 'Bash', 'tool_input': {'command': 'python3 - < /dev/null'}}
    run(['--guard', GUARD, '--hint', f'bash {GUARD} ROLE 4 /usr/bin/python3 -B FILE ARGS'], 2,
        stdin=json.dumps(event), contains=('python3 - reads the program from standard input',
                                           f'through the project guard ({GUARD})', 'For example: bash'),
        label='hook-refuse')
    event['tool_input']['command'] = 'python3 tool.py'
    run(['--guard', GUARD], 0, stdin=json.dumps(event), label='hook-allow')
    run([], 0, stdin=json.dumps({'tool_name': 'Read', 'tool_input': {'file_path': 'python3 -c'}}),
        label='hook-other-tool')
    run([], 0, stdin=json.dumps({'tool_name': 'Bash', 'tool_input': {}}), label='hook-no-command')
    run([], 1, stdin='not json', contains=('ERROR hook input is not JSON',), label='hook-bad-json')
    print(f'PASS refuse_inline_python: {len(REFUSE)} refused, {len(ALLOW)} allowed, {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
