#!/usr/bin/env python
"""Record a deterministic, dependency-free core workflow benchmark."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path


SIZES = {"small": 100, "medium": 1000, "large": 5000}
COMMANDS = (
    ("check", ["check"]),
    ("json", ["to-json", "--pretty"]),
    ("filter", ["filter", "--open", "--type", "task"]),
    ("summary", ["summary"]),
)


def fixture(size):
    rows = []
    for index in range(size):
        rows.append(
            '# [ ] T "Task {0}" id:task_{0:05d} project:benchmark tag:stable\n'.format(
                index
            )
        )
    return "".join(rows)


def run_case(root, label, count, command):
    with tempfile.TemporaryDirectory(prefix="lifetxt-benchmark-") as directory:
        path = Path(directory) / "benchmark.life.txt"
        path.write_text(fixture(count), encoding="utf-8")
        started = time.perf_counter()
        result = subprocess.run(
            [sys.executable, "-m", "lifetxt", *command, str(path)],
            cwd=root,
            capture_output=True,
            check=False,
        )
        elapsed = time.perf_counter() - started
        if result.returncode:
            raise RuntimeError(
                "benchmark command failed: {}\n{}".format(
                    " ".join(command), result.stderr.decode("utf-8", "replace")
                )
            )
        return {
            "elapsed_seconds": round(elapsed, 6),
            "stdout_bytes": len(result.stdout),
            "stderr_bytes": len(result.stderr),
        }


def benchmark(root):
    results = {}
    for label, count in SIZES.items():
        results[label] = {
            name: run_case(root, label, count, command) for name, command in COMMANDS
        }
    return {
        "schema": "lifetxt-core-benchmark-v1",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "interpreter": sys.executable,
        "fixture_sizes": SIZES,
        "results": results,
        "measurement": {
            "metric": "wall_clock_seconds",
            "repeat_policy": "single deterministic run per case; compare trends, not one-run thresholds",
            "resource_proxy": "stdout and stderr byte counts",
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", default=Path(__file__).resolve().parents[1], type=Path
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = benchmark(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"ok": True, "fixture_sizes": report["fixture_sizes"]}, sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
