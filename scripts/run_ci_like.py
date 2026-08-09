#!/usr/bin/env python
"""Run lifetxt checks inside disposable virtual environments.

Examples:
  python scripts/run_ci_like.py --profile cli --python python3.12
  python scripts/run_ci_like.py --profile web --python "py -3.12"
  python scripts/run_ci_like.py --profile mcp --python python3.12
  python scripts/run_ci_like.py --profile release --python python3.12
"""

from __future__ import print_function

import argparse
import glob
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

PROFILES = ("core", "cli", "web", "mcp", "release")


def _run(command, cwd, env=None):
    print("+ " + " ".join(command), flush=True)
    subprocess.check_call(command, cwd=cwd, env=env)


def _python_in_venv(venv_dir):
    if os.name == "nt":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def _script_in_venv(venv_dir, name):
    suffix = ".exe" if os.name == "nt" else ""
    directory = "Scripts" if os.name == "nt" else "bin"
    return os.path.join(venv_dir, directory, name + suffix)


def _label(command):
    safe = "-".join(os.path.basename(part).replace(".", "-") for part in command)
    return safe or "python"


def _install_profile_dependencies(python, root, profile, include_web):
    _run([python, "-m", "pip", "install", "--upgrade", "pip"], cwd=root)
    _run([python, "-m", "pip", "install", "-e", "."], cwd=root)
    if include_web:
        _run(
            [python, "-m", "pip", "install", "-r", "requirements-web.txt"],
            cwd=root,
        )
        _run([python, "-m", "pip", "install", "-e", ".[dev]"], cwd=root)
    if profile == "release":
        _run(
            [
                python,
                "-m",
                "pip",
                "install",
                "build",
                "jsonschema>=4",
                "twine",
                "tomli; python_version<'3.11'",
            ],
            cwd=root,
        )


def _run_tests(python, root, profile):
    _run([python, "-m", "compileall", "lifetxt", "tests", "scripts"], cwd=root)
    if profile == "mcp":
        _run(
            [python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_mcp*.py"],
            cwd=root,
        )
        _run([python, "-m", "unittest", "tests.test_surface_runtime"], cwd=root)
    else:
        _run([python, "-m", "unittest", "discover"], cwd=root)


def _run_examples(python, root):
    for sample in (
        "examples/minimal_life.txt",
        "examples/status_presence.txt",
        "examples/messages_life.txt",
    ):
        _run([python, "-m", "lifetxt", "check", sample], cwd=root)


def _run_release_profile(python, root):
    samples = [
        "examples/minimal_life.txt",
        "examples/status_presence.txt",
        "examples/messages_life.txt",
    ]
    manifest = os.path.join(root, ".cache", "release-policy-manifest.json")
    manifest_dir = os.path.dirname(manifest)
    if not os.path.isdir(manifest_dir):
        os.makedirs(manifest_dir)
    _run(
        [
            python,
            "scripts/check_release_policy.py",
            "--root",
            root,
            "--pretty",
            "--output",
            manifest,
        ]
        + samples,
        cwd=root,
    )
    _run(
        [python, "-m", "lifetxt", "safety", "release-gate", "--root", root] + samples,
        cwd=root,
    )

    wheel_dir = tempfile.mkdtemp(prefix="lifetxt-wheel-")
    install_dir = tempfile.mkdtemp(prefix="lifetxt-wheel-install-")
    smoke_dir = tempfile.mkdtemp(prefix="lifetxt-wheel-smoke-")
    try:
        _run(
            [python, "-m", "build", "--sdist", "--wheel", "--outdir", wheel_dir],
            cwd=root,
        )
        archives = sorted(glob.glob(os.path.join(wheel_dir, "*")))
        if not archives:
            raise RuntimeError("Build produced no distribution archives.")
        _run([python, "-m", "twine", "check"] + archives, cwd=root)
        wheels = sorted(glob.glob(os.path.join(wheel_dir, "*.whl")))
        if len(wheels) != 1:
            raise RuntimeError("Expected exactly one wheel, found %d." % len(wheels))
        _run([python, "-m", "venv", install_dir], cwd=root)
        wheel_python = _python_in_venv(install_dir)
        _run([wheel_python, "-m", "pip", "install", "--upgrade", "pip"], cwd=smoke_dir)
        _run([wheel_python, "-m", "pip", "install", wheels[0]], cwd=smoke_dir)
        _run([wheel_python, "-m", "lifetxt", "--help"], cwd=smoke_dir)
        _run([_script_in_venv(install_dir, "lifetxt"), "--help"], cwd=smoke_dir)
        _run(
            [
                wheel_python,
                "-m",
                "lifetxt",
                "check",
                os.path.join(root, "examples", "minimal_life.txt"),
            ],
            cwd=smoke_dir,
        )
    finally:
        shutil.rmtree(wheel_dir, ignore_errors=True)
        shutil.rmtree(install_dir, ignore_errors=True)
        shutil.rmtree(smoke_dir, ignore_errors=True)


def run_for_interpreter(command, root, profile, include_web, keep_venv, skip_smoke):
    cache_root = os.path.join(root, ".cache", "ci-like")
    if keep_venv:
        venv_dir = os.path.join(cache_root, "%s-%s" % (profile, _label(command)))
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
        _install_profile_dependencies(python, root, profile, include_web)
        _run_tests(python, root, profile)
        if profile != "mcp":
            _run_examples(python, root)
        if not skip_smoke and profile != "mcp":
            _run([python, "scripts/smoke_test.py"], cwd=root)
        if profile == "release":
            _run_release_profile(python, root)
    finally:
        if cleanup:
            shutil.rmtree(venv_dir, ignore_errors=True)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run named lifetxt CI profiles in clean virtual environments."
    )
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        default="core",
        help="Validation profile. release is the strict publication gate.",
    )
    parser.add_argument(
        "--python",
        dest="interpreters",
        action="append",
        help='Python launcher command. Repeat for a matrix, e.g. --python python3.10 --python "py -3.12".',
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Override the profile and omit optional Web dependencies.",
    )
    parser.add_argument(
        "--keep-venv",
        action="store_true",
        help="Keep reusable environments under .cache/ci-like instead of deleting them.",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip scripts/smoke_test.py for a faster edit/test loop.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    commands = [
        shlex.split(value, posix=os.name != "nt")
        for value in (args.interpreters or [sys.executable])
    ]
    include_web = args.profile in ("core", "web", "release") and not args.no_web
    for command in commands:
        if not command:
            raise SystemExit("--python cannot be empty")
        run_for_interpreter(
            command,
            root,
            args.profile,
            include_web,
            args.keep_venv,
            args.skip_smoke,
        )
    print(
        "CI-like %s profile passed for %d interpreter(s)."
        % (args.profile, len(commands))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
