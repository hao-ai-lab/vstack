#!/usr/bin/env python3
"""Exercise gpu_pack.py on CPU with a stand-in nvidia-smi that reads GPU memory from files.

Two mistakes seen in use come first: a hand-written pack of two one-GPU tests whose scripts both pinned themselves
to the first CPU they inherited, so both ran on one CPU; and job order kept by hand-made file names in a queue
shared with a team that has priority."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parents[1] / 'gpu_pack.py'
BASH = '/usr/bin/bash'
# What a test's own run script did: pin to the first CPU of the affinity it inherited.
PROBE = ('first=$(taskset -cp $$ | sed "s/.*: *//; s/[,-].*//"); '
         'echo "first=$first gpu=$CUDA_VISIBLE_DEVICES cpus=$VSTACK_RUN_CPUS"')
checks = 0


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def invoke(*args, code, contains=(), env=None, label=''):
    global checks
    result = subprocess.run([sys.executable, '-B', str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                            timeout=120, env=env)
    output = result.stdout + result.stderr
    require(result.returncode == code, f'{label or args}: expected exit {code}, got {result.returncode}: {output}')
    for fragment in contains:
        require(fragment in output, f'{label or args}: missing {fragment!r} in {output}')
    checks += 1
    return output


def spec(path, runs, job='z20260101T0000Z-ours-pack'):
    path.write_text(json.dumps({'job': job, 'runs': runs}))
    return path


def run(name, gpu, cpus, cmd, limit=60, **extra):
    return {'name': name, 'gpu': gpu, 'cpus': cpus, 'limit_s': limit, 'cmd': [BASH, '-c', cmd], **extra}


def main():
    invoke('--help', code=0, contains=('check', 'order'))
    invoke('check', code=2, contains=('ERROR arguments:',), label='no-spec')
    cpus = sorted(os.sched_getaffinity(0))
    slots = cpus[:4]
    scratch = Path(tempfile.mkdtemp(prefix='gpu-pack-'))
    try:
        gpu_dir = scratch / 'gpus'
        gpu_dir.mkdir()
        for index in range(4):
            (gpu_dir / str(index)).write_text('0\n')
        smi = scratch / 'nvidia-smi'
        smi.write_text('#!/usr/bin/bash\n# stand-in: memory.used of GPU -i N read from $FAKE_GPU_DIR/N\n'
                       'while (( $# )); do [[ $1 == -i ]] && { cat "$FAKE_GPU_DIR/$2"; exit; }; shift; done\n'
                       'exit 1\n')
        smi.chmod(0o755)
        env = dict(os.environ, FAKE_GPU_DIR=str(gpu_dir))
        env.pop('CUDA_VISIBLE_DEVICES', None)
        common = ['--smi', smi, '--drain-s', '2', '--grace-s', '1']

        # The past mistake: two runs left on the CPUs they inherit. The check refuses the shared CPUs.
        shared = ','.join(map(str, cpus))
        inherit = spec(scratch / 'inherit.json', [run('k1', 0, shared, PROBE), run('k3', 1, shared, PROBE)])
        invoke('check', inherit, code=1, contains=('are also given to runs[1]; each run gets its own CPUs',),
               label='shared-cpus')
        invoke('run', inherit, '--out', scratch / 'inherit-out', *common, code=1, env=env,
               contains=('refused before any run started',), label='shared-cpus-run')
        require(not (scratch / 'inherit-out').exists(), 'a refused job created its output')

        # A good pack: one GPU and one CPU per run; the probe's first CPU differs in every run.
        good = spec(scratch / 'good.json', [run(f'r{i}', i, str(c), PROBE) for i, c in enumerate(slots)])
        invoke('check', good, '--mine', 'z', code=0, contains=(f'{len(slots)} runs, one GPU and own CPUs each',),
               label='check-good')
        out = scratch / 'good-out'
        invoke('run', good, '--out', out, '--claim', scratch / 'claim-good', *common, code=0, env=env,
               contains=('OK pack: ', 'gpu_after=0MiB'), label='run-good')
        seen = []
        for index, cpu in enumerate(slots):
            log = (out / f'r{index}' / 'run.log').read_text()
            require(f'first={cpu} gpu={index} cpus={cpu}' in log, f'run r{index} log: {log!r}')
            result = json.loads((out / f'r{index}' / 'result.json').read_text())
            require(result['cpus_seen'] in (str(cpu), None) and result['gpu_clean'] and result['rc'] == 0,
                    f'result {result}')
            seen.append(cpu)
        require(len(set(seen)) == len(slots), 'two runs shared a CPU')
        require(json.loads((out / 'PACK.json').read_text())['passed'], 'PACK.json')
        # The same job offered to another queue: the claim makes it run once.
        invoke('run', good, '--out', scratch / 'second-out', '--claim', scratch / 'claim-good', *common, code=0,
               env=env, contains=('SKIP pack: ', 'already ran'), label='claim-taken')
        require(not (scratch / 'second-out').exists(), 'the second queue ran the job again')
        held = scratch / 'claim-held'
        held.mkdir()
        (held / 'owner.txt').write_text('host: elsewhere\npid: 1\n')
        invoke('run', good, '--out', scratch / 'held-out', '--claim', held, *common, code=3, env=env,
               contains=('has no done record',), label='claim-held')
        invoke('run', good, '--out', out, *common, code=1, env=env, contains=('exists; every job writes a new',),
               label='out-exists')

        # Time cap, a GPU left in use, a failing run, stray processes.
        capped = spec(scratch / 'capped.json', [run('slow', 0, str(slots[0]), 'exec sleep 30', limit=1)])
        started = time.time()
        invoke('run', capped, '--out', scratch / 'capped-out', *common, code=1, env=env,
               contains=('timed_out=yes', 'FAIL pack: 1 of 1 runs failed: slow'), label='time-cap')
        require(time.time() - started < 15, 'the cap did not stop the run')
        leak = spec(scratch / 'leak.json', [run('leak', 1, str(slots[0]), f'echo 500 > {gpu_dir}/1')])
        invoke('run', leak, '--out', scratch / 'leak-out', *common, code=1, env=env,
               contains=('gpu_after=500MiB', 'runs failed: leak'), label='gpu-not-idle-after')
        invoke('run', good, '--out', scratch / 'busy-out', '--claim', scratch / 'claim-busy', *common, code=1,
               env=env, contains=('GPU 1 holds 500 MiB before the job',), label='gpu-busy-before')
        require(not (scratch / 'claim-busy').exists(), 'a refused job took the claim')
        (gpu_dir / '1').write_text('0\n')
        mixed = spec(scratch / 'mixed.json', [run('ok', 0, str(slots[0]), 'true'),
                                              run('bad', 1, str(slots[-1]), 'exit 3')])
        invoke('run', mixed, '--out', scratch / 'mixed-out', *common, code=1, env=env,
               contains=('RUN bad gpu=1', 'rc=3', 'runs failed: bad'), label='one-run-fails')
        stray = spec(scratch / 'stray.json', [run('stray', 0, str(slots[0]), 'sleep 60 & echo started')])
        started = time.time()
        invoke('run', stray, '--out', scratch / 'stray-out', *common, code=0, env=env, label='strays')
        require(time.time() - started < 15, 'a stray process kept the job alive')
        require(json.loads((scratch / 'stray-out' / 'stray' / 'result.json').read_text())['strays_stopped'],
                'stray not recorded')
        # Runs sharing a lock file (a compile lock) run one after another.
        lock = str(scratch / 'compile.lock')
        locked = spec(scratch / 'locked.json', [run('a', 0, str(slots[0]), 'sleep 1', lock=lock),
                                                run('b', 1, str(slots[-1]), 'sleep 1', lock=lock)])
        invoke('run', locked, '--out', scratch / 'locked-out', *common, code=0, env=env, label='lock')
        a, b = (json.loads((scratch / 'locked-out' / n / 'result.json').read_text()) for n in 'ab')
        require(b['started'] >= a['ended'] or a['started'] >= b['ended'], f'locked runs overlapped: {a} {b}')

        # Inputs of an outside review of 0.125.0. Runs sharing a lock wait for each other, not for the job's start.
        chain = spec(scratch / 'chain.json', [run(f'c{i}', i, str(cpu), 'sleep 1.2', limit=2, lock=lock)
                                              for i, cpu in enumerate(slots[:3])])
        invoke('run', chain, '--out', scratch / 'chain-out', *common, code=0, env=env, label='lock-chain')
        for i in range(len(slots[:3])):
            require((scratch / 'chain-out' / f'c{i}' / 'result.json').is_file(), f'no result.json for c{i}')
        # A null lock is no lock.
        nolock = spec(scratch / 'nolock.json', [run('n', 0, str(slots[0]), 'true', lock=None)])
        invoke('check', nolock, code=0, label='null-lock-check')
        invoke('run', nolock, '--out', scratch / 'nolock-out', *common, code=0, env=env, label='null-lock-run')
        # A program that cannot start fails its run; the other run finishes and the records are written.
        missing = spec(scratch / 'missing.json', [run('ok', 0, str(slots[0]), 'sleep 1'),
                                                  dict(run('gone', 1, str(slots[-1]), 'true'), cmd=['/nonexistent/x'])])
        invoke('run', missing, '--out', scratch / 'missing-out', '--claim', scratch / 'claim-missing', *common, code=1,
               env=env, contains=('RUN ok gpu=0', 'rc=0', 'start_error=', 'runs failed: gone'), label='start-error')
        require(json.loads((scratch / 'missing-out' / 'ok' / 'result.json').read_text())['rc'] == 0, 'ok run lost')
        require((scratch / 'missing-out' / 'PACK.json').is_file(), 'no PACK.json after a start error')
        require((scratch / 'claim-missing' / 'done.txt').is_file(), 'no done record after a start error')
        # An existing output directory is refused before the claim, so another queue still runs the job.
        taken = scratch / 'claim-out-exists'
        invoke('run', good, '--out', out, '--claim', taken, *common, code=1, env=env,
               contains=('exists; every job writes a new',), label='out-exists-before-claim')
        require(not taken.exists(), 'a refused queue took the claim')
        invoke('run', good, '--out', scratch / 'other-queue-out', '--claim', taken, *common, code=0, env=env,
               contains=('OK pack: ',), label='other-queue-runs')

        # The job's own GPUs and CPUs.
        visible = dict(env, CUDA_VISIBLE_DEVICES='0,1')
        invoke('run', good, '--out', scratch / 'visible-out', *common, code=1, env=visible,
               contains=('is not among the job', '(0,1)'), label='gpu-not-visible') if len(slots) > 2 else None
        outside = spec(scratch / 'outside.json', [run('far', 0, str(max(cpus) + 1), 'true')])
        invoke('run', outside, '--out', scratch / 'outside-out', *common, code=1, env=env,
               contains=('outside the job',), label='cpu-outside')

        # Spec errors.
        bad_specs = {
            'five-runs': ([run(f'r{i}', i, str(100 + i), 'true') for i in range(5)], 'packs 1 to 4 runs'),
            'same-gpu': ([run('a', 0, '1', 'true'), run('b', 0, '2', 'true')], 'GPU 0 is already used'),
            'no-cap': ([{k: v for k, v in run('a', 0, '1', 'true').items() if k != 'limit_s'}], 'time cap'),
            'cap-too-long': ([run('a', 0, '1', 'true', limit=5000)], 'time cap in seconds, 1 to 1200'),
            'relative-program': ([dict(run('a', 0, '1', 'true'), cmd=['bash', 'x.sh'])], 'absolute program path'),
            'same-name': ([run('a', 0, '1', 'true'), run('a', 1, '2', 'true')], 'name a repeats'),
            'bad-cpus': ([run('a', 0, 'one', 'true')], 'cpus is a CPU list'),
            'overlap': ([run('a', 0, '1-3', 'true'), run('b', 1, '3,4', 'true')], 'CPUs 3 are also given'),
            'unknown-field': ([dict(run('a', 0, '1', 'true'), gpus=[0, 1])], 'unknown fields gpus'),
            'relative-lock': ([run('a', 0, '1', 'true', lock='x.lock')], 'lock is an absolute path'),
            'reversed-cpus': ([run('a', 0, '3-1', 'true')], 'has a range whose start exceeds its end'),
            'reserved-name': ([dict(run('a', 0, '1', 'true'), name='PACK.json')], 'is reserved for the job summary'),
        }
        for name, (runs, fragment) in bad_specs.items():
            invoke('check', spec(scratch / f'{name}.json', runs), code=1, contains=(fragment,), label=name)
        invoke('check', spec(scratch / 'theirs.json', [run('a', 0, '1', 'true')], job='20260101T0000Z-pack'),
               '--mine', 'z', code=1, contains=('does not start with z',), label='not-our-prefix')
        (scratch / 'broken.json').write_text('{')
        invoke('check', scratch / 'broken.json', code=1, contains=('ERROR ',), label='invalid-json')

        # Queue order: our job files sort after every job of the team with priority.
        queue = scratch / 'queue'
        queue.mkdir()
        for name in ('20260101T0100Z-team-a.job', '20260101T0300Z-team-b.job', 'z20260101T0200Z-ours-c.job'):
            (queue / name).write_text('job\n')
        invoke('order', queue, '--mine', 'z', code=0, contains=('OK order: 3 jobs, ours after all 2',),
               label='order-good')
        (queue / '0-ours-e.job').write_text('job\n')
        invoke('order', queue, '--mine', '0-ours', code=1,
               contains=('0-ours-e.job sorts before 3 jobs of the other team',), label='order-bad')
        invoke('order', scratch / 'no-queue', '--mine', 'z', code=1, contains=('not a directory',),
               label='order-absent')
    finally:
        shutil.rmtree(scratch)
    print(f'PASS gpu_pack: {len(bad_specs)} bad specs, {checks} CLI checks')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(f'ERROR self-test: {exc}', file=sys.stderr)
        raise SystemExit(1)
