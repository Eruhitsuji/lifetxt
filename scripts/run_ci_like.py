#!/usr/bin/env python
"""Run lifetxt checks inside disposable virtual environments.

Examples:
  python scripts/run_ci_like.py --python python3.12
  python scripts/run_ci_like.py --python "py -3.10" --python "py -3.12"
  python scripts/run_ci_like.py --python python3.12 --no-web
"""

from __future__ import print_function

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile


def _run(command, cwd, env=None):
    print("+ " + " ".join(command), flush=True)
    subprocess.check_call(command, cwd=cwd, env=env)


def _python_in_venv(venv_dir):
    if os.name == "nt":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def _label(command):
    safe = "-".join(os.path.basename(part).replace(".", "-") for part in command)
    return safe or "python"


def run_for_interpreter(command, root, include_web, keep_venv, skip_smoke):
    cache_root = os.path.join(root, ".cache", "ci-like")
    if keep_venv:
        venv_dir = os.path.join(cache_root, _label(command))
        if os.path.exists(venv_dir):
            shutil.rmtree(venv_dir)
        os.makedirs(cache_root, exist_ok=True)
        cleanup = False
    else:
        venv_dir = tempfile.mkdtemp(prefix="lifetxt-ci-")
        cleanup = True
    try:
        _run(command + ["-m", "venv", venv_dir], cwd=root)
        python = _python_in_venv(venv_dir)
        _run([python, "-m", "pip", "install", "--upgrade", "pip"], cwd=root)
        _run([python, "-m", "pip", "install", "-e", "."], cwd=root)
        if include_web:
            _run([python, "-m", "pip", "install", "-r", "requirements-web.txt", "httpx"], cwd=root)
        _run([python, "-m", "compileall", "lifetxt", "tests", "scripts"], cwd=root)
        _run([python, "-m", "unittest", "discover"], cwd=root)
        for sample in ("examples/minimal_life.txt", "examples/status_presence.txt", "examples/messages_life.txt"):
            _run([python, "-m", "lifetxt", "check", sample], cwd=root)
        if not skip_smoke:
            _run([python, "scripts/smoke_test.py"], cwd=root)
    finally:
        if cleanup:
            shutil.rmtree(venv_dir, ignore_errors=True)


def build_parser():
    parser = argparse.ArgumentParser(description="Run the same core checks as GitHub Actions in clean virtual environments.")
    parser.add_argument(
        "--python",
        dest="interpreters",
        action="append",
        help='Python launcher command. Repeat for a matrix, e.g. --python python3.10 --python "py -3.12".',
    )
    parser.add_argument("--no-web", action="store_true", help="Do not install optional Web dependencies; exercises skip guards and the dependency-free CLI.")
    parser.add_argument("--keep-venv", action="store_true", help="Keep reusable environments under .cache/ci-like instead of deleting them.")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip scripts/smoke_test.py for a faster edit/test loop.")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    commands = [shlex.split(value, posix=os.name != "nt") for value in (args.interpreters or [sys.executable])]
    for command in commands:
        if not command:
            raise SystemExit("--python cannot be empty")
        run_for_interpreter(command, root, not args.no_web, args.keep_venv, args.skip_smoke)
    print("CI-like checks passed for %d interpreter(s)." % len(commands))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
