# GPU check jobs in a shared queue

A real-engine check ([Gate 3](exposure-gate.md#gate-3-real-engine)) often needs one GPU for a few minutes. When the
GPUs come from a queue shared with another team that has priority, write each job from the template below and run
it with [`scripts/gpu_pack.py`](../scripts/gpu_pack.py). Two things went wrong when this was done by hand: two
one-GPU tests packed into one job both pinned themselves to the first CPU they inherited and ran on one CPU, and
the order behind the other team was kept by hand-made file names and a hand-written list.

## Rules

| Rule | Enforced by |
| :--- | :--- |
| One job packs one to four runs; each run has one GPU of its own. | `gpu_pack.py check` and `run` |
| Each run has CPUs of its own, inside the job's own CPU affinity; no two runs share a CPU. | `check`; `run` checks the affinity and pins each run |
| Each run has a time cap no longer than the queue allows (default 1200 s); at the cap it is stopped (TERM, then KILL). | `check`; `run` |
| Every GPU of the job is idle before the job, and each returns to idle after its run; stray processes a run leaves are stopped. | `run` (fails the job otherwise) |
| A job offered to several queues runs once: the first queue to start it takes the claim, the others skip it. | `run --claim DIR` (an atomic `mkdir`) |
| Our job names sort after every job of the team with priority. | `check --mine PREFIX`; `order QUEUE_DIR --mine PREFIX` |
| Runs that compile share a lock file and run one after another. | the run's `lock` field |
| Every job writes a new output directory. | `run` |

The queue's own rules (which hosts, how long, whether a model may be loaded or anything compiled) come from the
agreement with the other team; put its cap in `--max-limit-s` and its name prefix in `--mine`.

## Template

```json
{
  "job": "zYYYYMMDDTHHMMZ-ours-NAME",
  "runs": [
    {"name": "k1", "gpu": 0, "cpus": "0-3", "limit_s": 900,
     "cmd": ["/usr/bin/bash", "/abs/path/kit-k1/run_gpu.sh", "TAG"]},
    {"name": "k2", "gpu": 1, "cpus": "4-7", "limit_s": 900,
     "cmd": ["/usr/bin/bash", "/abs/path/kit-k2/run_gpu.sh", "TAG"],
     "lock": "/var/tmp/compile.lock", "nice": 19}
  ]
}
```

Fields: `job` (the queue file name stem; with `--mine`, it must start with our prefix), and per run `name`, `gpu`
(one physical index), `cpus` (a CPU list such as `0-3` or `4,5`), `limit_s`, `cmd` (an absolute program path and
its arguments), optionally `lock` (an absolute path; `null` means none) and `nice` (0 to 19). A CPU range runs
upwards (`3-1` is refused), and `PACK.json` is not a run name, because the job summary uses it. Each run sees `CUDA_VISIBLE_DEVICES` set
to its GPU, `VSTACK_RUN_CPUS` and `OMP_NUM_THREADS` for its CPUs, and starts in its own directory
`OUT/NAME/` with its log in `run.log`.

## Use

```sh
python3 scripts/gpu_pack.py check JOB.json --mine z --max-limit-s 1200
python3 scripts/gpu_pack.py order QUEUE_DIR --mine z
# The command the queue runs, inside the job's allocation:
python3 scripts/gpu_pack.py run JOB.json --out OUT_DIR --claim CLAIM_DIR --mine z --max-limit-s 1200
```

`run` prints one `RUN` line per run (GPU, CPUs, exit code, wall time, whether it hit its cap, GPU memory after) and
ends with `OK pack: ...` or `FAIL pack: ...`; `OUT_DIR/PACK.json` and `OUT_DIR/NAME/result.json` hold the same
facts. A queue that loses the claim prints `SKIP pack: ... already ran` and exits 0. A claim that is held without
a done record (its run died) exits 3 and is left for a person to inspect, so a job is never run twice by accident.
Use the same `CLAIM_DIR` in every queue the job is offered to, and a fresh one for every new job. A queue whose
`OUT_DIR` already exists is refused before it takes the claim, so another queue can still run the job. Runs that
share a lock wait for each other without a deadline of their own; a run gives up with `lock_timeout` only when
the lock is held outside the job for its whole cap. A run whose program cannot start fails with `start_error`
and the other runs go on; an unexpected error stops every run and still writes `PACK.json` and the done record.

Limits: GPU memory is read with `nvidia-smi` (`--smi` names another program, as the tests do); a process that
leaves its run's process group (a double fork into a new session) is not stopped, but the GPU check still fails
the job if it holds memory. The packer does not choose GPUs or hosts; the queue does.
