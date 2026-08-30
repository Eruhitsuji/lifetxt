"""CLI surface for `lifetxt server-report`.

`server-report plan|install|remove NAME --config PATH` installs or removes
one systemd oneshot+timer pair for an already-configured report profile on
an already-running deployment, without re-running `server-init`. See
:mod:`lifetxt.server_report` for the underlying plan-build/apply functions
this module only parses arguments and renders output for.
"""

from __future__ import annotations

import argparse
import json
import sys

from .atomic import write_console_text
from .server_report import (
    ServerReportError,
    apply_install,
    apply_remove,
    build_plan,
    build_remove_plan,
)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m lifetxt server-report",
        description=(
            "Install or remove one systemd report job for an already-running "
            "deployment, referencing a report profile already defined in the "
            "application config's `reports` section."
        ),
    )
    subparsers = parser.add_subparsers(dest="server_report_action", required=True)

    def _add_common(sub, needs_service_account=False):
        sub.add_argument("name", help="Report profile name (must already exist).")
        # Deliberately --app-config, not --config: the global --config flag
        # is stripped from argv by entrypoint._extract_config_arg before any
        # subcommand sees it (the same pitfall server-init/server-update
        # avoided with --server-config; see cap-ubuntu-server-deployment).
        sub.add_argument(
            "--app-config",
            dest="app_config_path",
            required=True,
            metavar="PATH",
            help="Application config.json containing the report profile.",
        )
        sub.add_argument(
            "--data-root",
            metavar="PATH",
            help="Deployment data root. Defaults to the directory containing --config.",
        )
        sub.add_argument(
            "--unit-dir",
            metavar="PATH",
            help="Directory to read/write systemd unit files. Defaults to <data-root>/systemd.",
        )
        sub.add_argument(
            "--format", choices=("text", "json"), default="text", help="Output format."
        )
        if needs_service_account:
            sub.add_argument("--service-user", required=True, metavar="NAME")
            sub.add_argument("--service-group", required=True, metavar="NAME")
            sub.add_argument(
                "--python",
                metavar="PATH",
                help="Target Python interpreter path. Defaults to a bare `lifetxt` on PATH.",
            )
            sub.add_argument(
                "--at",
                default="00:10",
                metavar="HH:MM",
                help="24-hour time the job's timer fires at, relative to the "
                "profile's own period boundary. Default: 00:10.",
            )
            sub.add_argument(
                "--send-email",
                action="store_true",
                help=(
                    "Also run `report send` after `report run` succeeds, "
                    "delivering the profile's configured email. Requires the "
                    "profile to already have a valid `email` section and "
                    "--environment-file."
                ),
            )
            sub.add_argument(
                "--environment-file",
                metavar="PATH",
                help=(
                    "Absolute path to a systemd EnvironmentFile= holding SMTP "
                    "credential environment variables. Only the path is ever "
                    "written into generated unit text or plan output -- never "
                    "its contents. Required with --send-email."
                ),
            )
        sub.add_argument(
            "--service-command",
            nargs="+",
            default=["systemctl"],
            metavar="ARGV",
            help="Command prefix used to enable/disable/start the timer. Default: systemctl.",
        )

    plan_sub = subparsers.add_parser(
        "plan", help="Preview the systemd unit files for one report job."
    )
    _add_common(plan_sub, needs_service_account=True)
    plan_sub.set_defaults(func=_command_plan)

    install_sub = subparsers.add_parser(
        "install", help="Write (and optionally enable) one report job's systemd units."
    )
    _add_common(install_sub, needs_service_account=True)
    install_sub.add_argument(
        "--yes", action="store_true", help="Actually write the unit files."
    )
    install_sub.add_argument(
        "--enable",
        action="store_true",
        help="Also run `systemctl enable` on the timer unit.",
    )
    install_sub.add_argument(
        "--start",
        action="store_true",
        help="Also run `systemctl enable --now` on the timer unit (implies --enable).",
    )
    install_sub.set_defaults(func=_command_install)

    remove_sub = subparsers.add_parser(
        "remove",
        help="Disable (best-effort) and delete one report job's systemd units.",
    )
    _add_common(remove_sub, needs_service_account=False)
    remove_sub.add_argument(
        "--yes", action="store_true", help="Actually disable and delete the unit files."
    )
    remove_sub.set_defaults(func=_command_remove)
    return parser


def main(argv=None):
    values = list(sys.argv[1:] if argv is None else argv)
    if values and values[0] == "server-report":
        values = values[1:]
    args = build_parser().parse_args(values)
    try:
        return args.func(args)
    except ServerReportError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1


def _render(args, payload, text_lines):
    if args.format == "json":
        write_console_text(
            sys.stdout, json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        )
    else:
        write_console_text(sys.stdout, "\n".join(text_lines) + "\n")


def _scheduled_email_line(plan):
    if plan["send_email"]:
        return (
            "Scheduled email: enabled (environment file: %s)" % plan["environment_file"]
        )
    return "Scheduled email: disabled"


def _command_plan(args):
    plan = build_plan(
        args.name,
        args.app_config_path,
        args.service_user,
        args.service_group,
        data_root=args.data_root,
        python=args.python,
        unit_dir=args.unit_dir,
        schedule_at=args.at,
        send_email=args.send_email,
        environment_file=args.environment_file,
    )
    lines = [
        "Plan for report job %r (%s):" % (args.name, plan["status"]),
        _scheduled_email_line(plan),
    ]
    for step in plan["steps"]:
        lines.append("- %s: %s" % (step["action"], step["path"]))
    if plan["conflicts"]:
        lines.append(
            "Conflicts (existing content differs): " + ", ".join(plan["conflicts"])
        )
    _render(args, plan, lines)
    return 0


def _command_install(args):
    plan = build_plan(
        args.name,
        args.app_config_path,
        args.service_user,
        args.service_group,
        data_root=args.data_root,
        python=args.python,
        unit_dir=args.unit_dir,
        schedule_at=args.at,
        send_email=args.send_email,
        environment_file=args.environment_file,
    )
    if not args.yes:
        lines = [
            "[dry-run] Would write:",
            _scheduled_email_line(plan),
        ] + ["  - %s (%s)" % (s["path"], s["action"]) for s in plan["steps"]]
        _render(args, plan, lines)
        return 0
    result = apply_install(
        plan,
        service_command=args.service_command,
        enable=args.enable or args.start,
        start=args.start,
    )
    lines = (
        ["Installed report job %r:" % args.name]
        + ["  - %s" % p for p in result["written"]]
        + [_scheduled_email_line(result)]
    )
    _render(args, result, lines)
    return 0


def _command_remove(args):
    unit_dir = args.unit_dir or _default_unit_dir(args)
    plan = build_remove_plan(args.name, unit_dir)
    if not args.yes:
        lines = ["[dry-run] Would remove:"] + ["  - %s" % p for p in plan["paths"]]
        _render(args, plan, lines)
        return 0
    result = apply_remove(plan, service_command=args.service_command)
    lines = ["Removed report job %r:" % args.name]
    lines += ["  - %s" % p for p in result["removed"]]
    if result["skipped"]:
        lines.append(
            "Skipped (not a lifetxt-generated unit file): "
            + ", ".join(result["skipped"])
        )
    _render(args, result, lines)
    return 0


def _default_unit_dir(args):
    import os

    data_root = args.data_root or os.path.dirname(os.path.abspath(args.app_config_path))
    return os.path.join(data_root, "systemd")
