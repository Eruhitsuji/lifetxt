"""CLI surface for the opt-in periodic Git-commit worker (#731).

`git-commit-worker run` is the actual oneshot action the generated systemd
service's `ExecStart=` invokes. See :mod:`lifetxt.git_commit_worker` for the
underlying commit logic this module only parses arguments and renders
output for.
"""

from __future__ import annotations

import argparse
import json
import sys

from .atomic import write_console_text
from .git_commit_worker import GitCommitWorkerError, run_commit


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m lifetxt git-commit-worker",
        description=(
            "Opt-in periodic Git-commit worker for server-managed lifetxt "
            "data. Stages and commits only the configured path allowlist in "
            "an already-existing Git repository; never runs `git init` and "
            "never mutates unrelated files."
        ),
    )
    subparsers = parser.add_subparsers(dest="git_commit_worker_action", required=True)

    run_sub = subparsers.add_parser(
        "run", help="Run one commit attempt against the configured allowlist."
    )
    run_sub.add_argument(
        "--repo-root", required=True, metavar="PATH", help="Existing Git repository."
    )
    run_sub.add_argument(
        "--path",
        dest="paths",
        action="append",
        required=True,
        metavar="PATH",
        help="Allowlisted path to stage (relative to --repo-root, or "
        "absolute). May be given more than once.",
    )
    run_sub.add_argument(
        "--branch",
        required=True,
        metavar="NAME",
        help="Expected current branch; a mismatch or detached HEAD refuses the run.",
    )
    run_sub.add_argument(
        "--lock-file",
        metavar="PATH",
        help="Concurrency lock file. Omitting it disables locking.",
    )
    run_sub.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format."
    )
    run_sub.set_defaults(func=_command_run)
    return parser


def main(argv=None):
    values = list(sys.argv[1:] if argv is None else argv)
    if values and values[0] == "git-commit-worker":
        values = values[1:]
    args = build_parser().parse_args(values)
    try:
        return args.func(args)
    except GitCommitWorkerError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1


def _render(args, payload, text_lines):
    if args.format == "json":
        write_console_text(
            sys.stdout, json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        )
    else:
        write_console_text(sys.stdout, "\n".join(text_lines) + "\n")


def _command_run(args):
    result = run_commit(
        args.repo_root, args.paths, args.branch, lock_path=args.lock_file
    )
    status = result["status"]
    if status == "committed":
        lines = [
            "Committed %s (%s)" % (result["commit"], result["message"]),
        ] + ["  - %s" % p for p in result["paths"]]
    elif status == "no_op":
        lines = [result["message"]]
    else:
        lines = ["Refused (%s): %s" % (result["reason"], result["message"])]
    _render(args, result, lines)
    return 0 if status != "refused" else 1
