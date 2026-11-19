#!/usr/bin/env python3
"""Run up to four one-GPU runs as one job of a GPU queue shared with another team, each run on its own GPU and its
own CPUs, with a time cap, GPU memory back to idle afterwards, and one claim across the queues it was offered to.

  gpu_pack.py check SPEC.json [--max-limit-s N] [--mine PREFIX]      validate a job (no GPU needed)
  gpu_pack.py run SPEC.json --out DIR [--claim DIR] [options]         run it inside the queue's allocation
  gpu_pack.py order QUEUE_DIR --mine PREFIX [--glob PATTERN]          the queue order leaves the other team first

SPEC.json: {"job": NAME, "runs": [{"name": N, "gpu": INDEX, "cpus": "0-3", "limit_s": SECONDS,
"cmd": ["/abs/program", "arg", ...], "lock": "/abs/lock-file" (optional), "nice": 0-19 (optional)}, ...]}.
The check refuses more than four runs, two runs on one GPU, CPU lists that overlap (two runs that would share a
CPU) or hold a reversed range (3-1), a missing or too long time cap, a program given without an absolute path,
and the run name PACK.json; a null lock means no lock. 'run' also refuses a GPU outside CUDA_VISIBLE_DEVICES, CPUs
outside the job's own affinity, a GPU that is not idle before the job and an output directory that exists, all
before it takes the claim (mkdir, atomic: the first queue to start the job runs it, the others skip it); it starts
every run
in its own process group pinned to its CPUs with CUDA_VISIBLE_DEVICES set to its GPU, stops a run at its cap
(TERM, then KILL after --grace-s), stops stray processes a run leaves, waits for each GPU to return to idle, and
writes DIR/NAME/run.log, DIR/NAME/result.json and DIR/PACK.json. Runs that name the same lock file run one after
another (for example a compile lock): a run waits while another run of the job holds the lock, and gives up
(lock_timeout) only when the lock is held outside the job for its whole cap. A run whose program cannot start
fails with start_error while the others go on; an unexpected error stops every run and still writes PACK.json
and the claim's done record. The job passes only when every run exits 0 within its cap and every GPU is
idle afterwards. 'order' lists a queue as the queue reads it (sorted by file name) and fails when one of our job
files would sort before a job of the other team.
"""

import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time

MAX_RUNS = 4
RESERVED = {"pack.json"}  # DIR/PACK.json is the job summary, so no run may be named so
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
CPU_LIST = re.compile(r"[0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*")


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, f"ERROR arguments: {message}\n")


def cpu_set(text):
    cpus = set()
    for part in text.split(","):
        low, _, high = part.partition("-")
        cpus |= set(range(int(low), int(high or low) + 1))
    return cpus


def cpu_text(cpus):
    return ",".join(str(c) for c in sorted(cpus))


def load_spec(path):
    try:
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        return None, [f"{path}: {exc}"]
    return spec, []


def check_spec(spec, max_limit, mine=None):
    """Problems of a job spec; an empty list means it is valid."""
    if not isinstance(spec, dict) or not isinstance(spec.get("runs"), list):
        return ["the spec is a JSON object with a job name and a list of runs"]
    problems = []
    job = spec.get("job")
    if not isinstance(job, str) or not NAME.fullmatch(job):
        problems.append("job: a name of letters, digits, '.', '_' and '-'")
    elif mine and not job.startswith(mine):
        problems.append(f"job: {job} does not start with {mine}, so the queue may order it before the other team")
    runs = spec["runs"]
    if not 1 <= len(runs) <= MAX_RUNS:
        problems.append(f"runs: one job packs 1 to {MAX_RUNS} runs, found {len(runs)}")
    names, gpus, cpus_of = {}, {}, {}
    for number, run in enumerate(runs, 1):
        where = f"runs[{number}]"
        if not isinstance(run, dict):
            problems.append(f"{where}: an object")
            continue
        extra = set(run) - {"name", "gpu", "cpus", "limit_s", "cmd", "lock", "nice"}
        if extra:
            problems.append(f"{where}: unknown fields {', '.join(sorted(extra))}")
        name = run.get("name")
        if not isinstance(name, str) or not NAME.fullmatch(name):
            problems.append(f"{where}: name of letters, digits, '.', '_' and '-'")
        elif name.lower() in RESERVED:
            problems.append(f"{where}: name {name} is reserved for the job summary in the output directory")
        elif name in names:
            problems.append(f"{where}: name {name} repeats runs[{names[name]}]")
        else:
            names[name] = number
        gpu = run.get("gpu")
        if not isinstance(gpu, int) or isinstance(gpu, bool) or gpu < 0:
            problems.append(f"{where}: gpu is one GPU index")
        elif gpu in gpus:
            problems.append(f"{where}: GPU {gpu} is already used by runs[{gpus[gpu]}]; one GPU per run")
        else:
            gpus[gpu] = number
        cpus = run.get("cpus")
        if not isinstance(cpus, str) or not CPU_LIST.fullmatch(cpus):
            problems.append(f"{where}: cpus is a CPU list such as 0-3 or 4,5")
        elif any(int(low) > int(high) for low, _, high in (part.partition("-") for part in cpus.split(","))
                 if high):
            problems.append(f"{where}: cpus {cpus} has a range whose start exceeds its end")
        else:
            mine_cpus = cpu_set(cpus)
            for other, theirs in cpus_of.items():
                if mine_cpus & theirs:
                    problems.append(f"{where}: CPUs {cpu_text(mine_cpus & theirs)} are also given to runs[{other}]; "
                                    "each run gets its own CPUs")
            cpus_of[number] = mine_cpus
        limit = run.get("limit_s")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 0 < limit <= max_limit:
            problems.append(f"{where}: limit_s is the run's time cap in seconds, 1 to {max_limit}")
        cmd = run.get("cmd")
        if not isinstance(cmd, list) or not cmd or not all(isinstance(word, str) and word for word in cmd):
            problems.append(f"{where}: cmd is a list of words")
        elif not os.path.isabs(cmd[0]):
            problems.append(f"{where}: cmd starts with an absolute program path, not {cmd[0]}")
        lock = run.get("lock")
        if lock is not None and (not isinstance(lock, str) or not os.path.isabs(lock)):
            problems.append(f"{where}: lock is an absolute path")
        nice = run.get("nice", 0)
        if not isinstance(nice, int) or isinstance(nice, bool) or not 0 <= nice <= 19:
            problems.append(f"{where}: nice is 0 to 19")
    return problems


def gpu_used_mib(smi, gpu):
    out = subprocess.run([smi, "--query-gpu=memory.used", "--format=csv,noheader,nounits", "-i", str(gpu)],
                         capture_output=True, text=True, timeout=30)
    value = out.stdout.strip().splitlines()[0].strip() if out.returncode == 0 and out.stdout.strip() else ""
    if not value.isdigit():
        raise RuntimeError(f"cannot read the memory of GPU {gpu} from {smi}: {out.stdout}{out.stderr}".strip())
    return int(value)


def take_claim(claim):
    """True when this process holds the claim; False when another queue took it and finished or is running."""
    try:
        claim.mkdir()
    except FileExistsError:
        return False
    (claim / "owner.txt").write_text(f"host: {socket.gethostname()}\npid: {os.getpid()}\n"
                                     f"started: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
    return True


class Run:
    def __init__(self, spec, out, smi):
        self.spec, self.smi = spec, smi
        self.name, self.gpu, self.cpus = spec["name"], spec["gpu"], cpu_set(spec["cpus"])
        self.dir = out / self.name
        self.proc = self.lock_fd = None
        self.state, self.waiting_since = "waiting", time.time()
        self.result = {"name": self.name, "gpu": self.gpu, "cpus": cpu_text(self.cpus), "limit_s": spec["limit_s"],
                       "cmd": spec["cmd"], "rc": None, "timed_out": False, "strays_stopped": False}

    def try_lock(self):
        if self.spec.get("lock") is None:
            return True
        if self.lock_fd is None:
            self.lock_fd = os.open(self.spec["lock"], os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    def start(self):
        self.dir.mkdir(parents=True)
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(self.gpu), VSTACK_RUN_NAME=self.name,
                   VSTACK_RUN_CPUS=cpu_text(self.cpus), OMP_NUM_THREADS=str(len(self.cpus)))
        cpus, nice = self.cpus, self.spec.get("nice", 0)

        def pin():
            os.sched_setaffinity(0, cpus)
            if nice:
                os.nice(nice)

        self.log = (self.dir / "run.log").open("wb")
        self.started = time.time()
        self.proc = subprocess.Popen(self.spec["cmd"], cwd=self.dir, env=env, stdin=subprocess.DEVNULL,
                                     stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True,
                                     preexec_fn=pin)
        self.result["started"] = round(self.started, 3)
        try:
            self.result["cpus_seen"] = cpu_text(os.sched_getaffinity(self.proc.pid))
        except OSError:  # already gone
            self.result["cpus_seen"] = None
        self.state = "running"

    def signal_group(self, sig):
        try:
            os.killpg(self.proc.pid, sig)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def poll(self, grace):
        if self.proc.poll() is None:
            elapsed = time.time() - self.started
            if elapsed > self.spec["limit_s"] and not self.result["timed_out"]:
                self.result["timed_out"] = True
                self.signal_group(signal.SIGTERM)
                self.term_sent = time.time()
            elif self.result["timed_out"] and time.time() - self.term_sent > grace:
                self.signal_group(signal.SIGKILL)
            return False
        self.result["rc"] = self.proc.returncode
        self.result["wall_s"] = round(time.time() - self.started, 3)
        # A run is done when its process group is gone; stop what it left behind.
        if self.signal_group(signal.SIGTERM):
            self.result["strays_stopped"] = True
            deadline = time.time() + grace
            while time.time() < deadline and self.signal_group(0):
                time.sleep(0.1)
            self.signal_group(signal.SIGKILL)
        self.log.close()
        return True

    def drain(self, idle, wait):
        """Called once per loop after the run ended; done when its GPU is idle or the wait is over."""
        now = time.time()
        if not hasattr(self, "drain_until"):
            self.drain_until, self.next_check = now + wait, now
        if now < self.next_check:
            return
        self.next_check = now + 1
        try:
            used = gpu_used_mib(self.smi, self.gpu)
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            used, self.result["gpu_error"] = None, str(exc)
        if used is not None and used > idle and now < self.drain_until:
            return
        self.result["gpu_mib_after"] = used
        self.result["gpu_clean"] = used is not None and used <= idle
        if self.lock_fd is not None:
            os.close(self.lock_fd)
        self.result["ended"] = round(time.time(), 3)
        self.dir.mkdir(parents=True, exist_ok=True)  # also for a run that never started
        (self.dir / "result.json").write_text(json.dumps(self.result, indent=1) + "\n")
        self.state = "done"


def run_job(args):
    spec, problems = load_spec(args.spec)
    if not problems:
        problems = check_spec(spec, args.max_limit_s, args.mine)
    if not problems:
        visible = os.environ.get("CUDA_VISIBLE_DEVICES")
        allowed = os.sched_getaffinity(0)
        for run in spec["runs"]:
            if visible is not None and str(run["gpu"]) not in visible.split(","):
                problems.append(f"{run['name']}: GPU {run['gpu']} is not among the job's GPUs ({visible})")
            outside = cpu_set(run["cpus"]) - allowed
            if outside:
                problems.append(f"{run['name']}: CPUs {cpu_text(outside)} are outside the job's CPUs "
                                f"({cpu_text(allowed)})")
    if not problems:
        try:
            for run in spec["runs"]:
                used = gpu_used_mib(args.smi, run["gpu"])
                if used > args.idle_mib:
                    problems.append(f"{run['name']}: GPU {run['gpu']} holds {used} MiB before the job; another "
                                    "process uses it")
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            problems.append(str(exc))
    if problems:
        for problem in problems:
            print(f"ERROR {problem}")
        print(f"FAIL pack: refused before any run started; {len(problems)} problems")
        return 1
    claim = Path(args.claim) if args.claim else None
    if claim is not None and (claim / "done.txt").is_file():
        print(f"SKIP pack: {spec['job']} already ran under claim {claim}")
        return 0
    out = Path(args.out)
    # Refuse before the claim is taken, so that another queue offered the same job still runs it.
    if out.exists() or out.is_symlink():
        print(f"ERROR {out} exists; every job writes a new output directory\nFAIL pack: refused before any run "
              "started")
        return 1
    if claim is not None and not take_claim(claim):
        owner = (claim / "owner.txt").read_text() if (claim / "owner.txt").is_file() else "unknown\n"
        if (claim / "done.txt").is_file():
            print(f"SKIP pack: {spec['job']} already ran under claim {claim}")
            return 0
        print(f"SKIP pack: claim {claim} is held and has no done record; owner {owner.strip()}; if that run "
              "died, check its output before removing the claim")
        return 3
    try:
        out.mkdir(parents=True)
    except OSError as exc:
        if claim is not None:  # give the claim back: this queue ran nothing
            (claim / "owner.txt").unlink(missing_ok=True)
            claim.rmdir()
        print(f"ERROR {out}: {exc}\nFAIL pack: refused before any run started")
        return 1
    runs = [Run(run, out, args.smi) for run in spec["runs"]]
    print(f"pack {spec['job']}: {len(runs)} runs on {socket.gethostname()}")
    try:
        results = run_all(runs, args)
    except (Exception, KeyboardInterrupt) as exc:
        # Stop every run still alive, so that no process is left on a GPU, and record the failure.
        for run in runs:
            if run.proc is not None and run.proc.poll() is None:
                run.signal_group(signal.SIGTERM)
        time.sleep(min(args.grace_s, 5))
        for run in runs:
            if run.proc is not None:
                run.signal_group(signal.SIGKILL)
        summary = {"job": spec["job"], "host": socket.gethostname(), "runs": [run.result for run in runs],
                   "passed": False, "error": f"{type(exc).__name__}: {exc}"}
        (out / "PACK.json").write_text(json.dumps(summary, indent=1) + "\n")
        if claim is not None:
            (claim / "done.txt").write_text(f"passed: False\nout: {out}\nerror: {type(exc).__name__}\n")
        print(f"ERROR pack stopped by {type(exc).__name__}: {exc}\nFAIL pack: every run stopped")
        return 1
    failed = [r for r in results if r["rc"] != 0 or r["timed_out"] or not r.get("gpu_clean")]
    for r in results:
        print(f"RUN {r['name']} gpu={r['gpu']} cpus={r['cpus']} rc={r['rc']} wall={r.get('wall_s')}s "
              f"timed_out={'yes' if r['timed_out'] else 'no'} gpu_after={r.get('gpu_mib_after')}MiB"
              + (" lock_timeout=yes" if r.get("lock_timeout") else "")
              + (f" start_error={r['start_error']!r}" if r.get("start_error") else ""))
    summary = {"job": spec["job"], "host": socket.gethostname(), "runs": results, "passed": not failed}
    (out / "PACK.json").write_text(json.dumps(summary, indent=1) + "\n")
    if claim is not None:
        (claim / "done.txt").write_text(f"passed: {not failed}\nout: {out}\n")
    if failed:
        print(f"FAIL pack: {len(failed)} of {len(runs)} runs failed: " + ", ".join(r["name"] for r in failed))
        return 1
    print(f"OK pack: {len(runs)} runs, every rc 0 within its cap, GPUs back to idle")
    return 0


def run_all(runs, args):
    """Start, cap and drain every run; return their results."""
    while any(run.state != "done" for run in runs):
        for run in runs:
            if run.state == "waiting":
                if run.try_lock():
                    try:
                        run.start()
                    except (OSError, subprocess.SubprocessError) as exc:
                        # The program could not start (missing, not executable, CPUs refused): the run fails,
                        # the others go on, and its GPU is still checked.
                        run.result.update(rc=None, start_error=f"{type(exc).__name__}: {exc}")
                        if getattr(run, "log", None) is not None:
                            run.log.close()
                        run.state = "draining"
                elif any(other is not run and other.state in {"running", "draining"}
                         and other.spec.get("lock") == run.spec.get("lock") for other in runs):
                    run.waiting_since = time.time()  # a run of this job holds the lock; its own cap bounds it
                elif time.time() - run.waiting_since > run.spec["limit_s"]:
                    run.result.update(rc=None, lock_timeout=True)
                    run.state = "draining"  # held outside this job for a whole cap: give up, record it
            elif run.state == "running" and run.poll(args.grace_s):
                run.state = "draining"
            if run.state == "draining":
                run.drain(args.idle_mib, args.drain_s)
        time.sleep(0.2)
    return [run.result for run in runs]


def queue_order(args):
    queue = Path(args.queue)
    if not queue.is_dir():
        print(f"ERROR {queue}: not a directory\nFAIL order: 1 errors")
        return 1
    names = sorted(p.name for p in queue.glob(args.glob) if p.is_file())
    theirs = [n for n in names if not n.startswith(args.mine)]
    problems = []
    for position, name in enumerate(names, 1):
        owner = "ours" if name.startswith(args.mine) else "other"
        print(f"{position}\t{owner}\t{name}")
        if owner == "ours":
            later = [n for n in theirs if n > name]
            if later:
                problems.append(f"{name} sorts before {len(later)} jobs of the other team (first {later[0]}); "
                                "name it so that it sorts after them")
    for problem in problems:
        print(f"ERROR {problem}")
    if problems:
        print(f"FAIL order: {len(problems)} of our jobs would run before the other team's")
        return 1
    print(f"OK order: {len(names)} jobs, ours after all {len(theirs)} of the other team")
    return 0


def main():
    parser = Parser(description=__doc__.split("\n\n")[0], epilog=__doc__.split("\n\n", 1)[1] + (
        "\nExit 0: valid / passed / skipped because another queue ran it; 1: refused or failed; 2: usage; "
        "3: the claim is held without a done record."), formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    check = sub.add_parser("check", help="validate a job spec")
    run = sub.add_parser("run", help="run a job spec")
    for p in (check, run):
        p.add_argument("spec", metavar="SPEC.json")
        p.add_argument("--max-limit-s", type=int, default=1200, help="the queue's cap per run (default 1200)")
        p.add_argument("--mine", metavar="PREFIX", help="our job names start with this, sorting after the others")
    run.add_argument("--out", required=True, metavar="DIR", help="a new output directory")
    run.add_argument("--claim", metavar="DIR", help="claim directory shared by every queue the job was offered to")
    run.add_argument("--smi", default="nvidia-smi", help="the nvidia-smi program")
    run.add_argument("--idle-mib", type=int, default=0, help="GPU memory that counts as idle (default 0)")
    run.add_argument("--drain-s", type=int, default=60, help="how long a GPU may take to return to idle")
    run.add_argument("--grace-s", type=int, default=20, help="seconds between TERM and KILL at the cap")
    order = sub.add_parser("order", help="check the order of a queue directory")
    order.add_argument("queue", metavar="QUEUE_DIR")
    order.add_argument("--mine", required=True, metavar="PREFIX")
    order.add_argument("--glob", default="*.job")
    args = parser.parse_args()
    if args.command == "order":
        return queue_order(args)
    if args.command == "run":
        args.begun = time.time()
        return run_job(args)
    spec, problems = load_spec(args.spec)
    problems = problems or check_spec(spec, args.max_limit_s, args.mine)
    for problem in problems:
        print(f"ERROR {problem}")
    if problems:
        print(f"FAIL pack: {len(problems)} problems")
        return 1
    print(f"OK pack: {spec['job']}, {len(spec['runs'])} runs, one GPU and own CPUs each")
    return 0


if __name__ == "__main__":
    sys.exit(main())
