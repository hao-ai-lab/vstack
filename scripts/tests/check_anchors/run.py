#!/usr/bin/env python3
"""Run saved positive and negative fixtures without changing repository inputs."""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    fixtures = json.loads((HERE / "fixtures.json").read_text())
    failures = []
    for case in fixtures["cases"]:
        with tempfile.TemporaryDirectory(prefix=HERE.name + "-") as directory:
            scratch = Path(directory)
            for name, text in case.get("files", {}).items():
                path = scratch / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            for name, target in case.get("symlinks", {}).items():
                (scratch / name).symlink_to(scratch / target)
            before = {name: hashlib.sha256((scratch / name).read_bytes()).hexdigest()
                      for name in case.get("files", {})}
            args = [arg.replace("{tmp}", str(scratch)) for arg in case["args"]]
            result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / fixtures["script"]), *args],
                                    text=True, capture_output=True, timeout=10)
            output = result.stdout + result.stderr
            problems = []
            if result.returncode != case["exit"]:
                problems.append(f"exit {result.returncode}, expected {case['exit']}")
            if "stdout" in case and result.stdout != case["stdout"]:
                problems.append(f"stdout {result.stdout!r}, expected {case['stdout']!r}")
            for fragment in case.get("contains", []):
                if fragment not in output:
                    problems.append(f"missing output {fragment!r}")
            if case["exit"] == 0 and "ERROR " in output:
                problems.append("successful result contains ERROR")
            after = {name: hashlib.sha256((scratch / name).read_bytes()).hexdigest() for name in before}
            if before != after:
                problems.append("input changed")
            if problems:
                failures.append(case["name"])
                print(f"FAIL {case['name']}: {'; '.join(problems)}\n{output}")
    if failures:
        print(f"FAIL {HERE.name}: {len(failures)}/{len(fixtures['cases'])} cases")
        return 1
    print(f"PASS {HERE.name}: {len(fixtures['cases'])} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
