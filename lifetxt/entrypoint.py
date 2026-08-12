"""Compatibility-preserving CLI entry point for newer workflow commands.

The original :mod:`lifetxt.cli` remains the authoritative implementation for
existing commands.  This module intercepts only commands and flags added after
that parser was established, then delegates everything else unchanged.
"""

import datetime
import json
import sys
from collections import OrderedDict

from .timezone_policy import today as timezone_today


_EXTRA_COMMANDS = frozenset(
    (
        "next",
        "show",
        "edit",
        "path",
        "count",
        "invoice",
        "standup",
        "to-ics",
        "from-todo",
        "from-markdown",
        "safety",
        "format",
        "capabilities",
        "attachment",
    )
)

_DOCTOR_SAFETY_FLAGS = frozenset(
    (
        "--workspace-safety",
        "--archive",
        "--timer-state",
        "--revision-metrics",
        "--cleanup-stale",
        "--fold-policy",
        "--gap-policy",
    )
)


def _extract_config_arg(argv):
    raw = list(sys.argv[1:] if argv is None else argv)
    config_path = None
    workspace_name = None
    cleaned = []
    index = 0
    while index < len(raw):
        value = raw[index]
        if value == "--config":
            if index + 1 >= len(raw):
                raise ValueError("--config requires a path.")
            config_path = raw[index + 1]
            index += 2
            continue
        if value.startswith("--config="):
            config_path = value.split("=", 1)[1]
            index += 1
            continue
        if value == "--workspace":
            if index + 1 >= len(raw):
                raise ValueError("--workspace requires a name.")
            workspace_name = raw[index + 1]
            index += 2
            continue
        if value.startswith("--workspace="):
            workspace_name = value.split("=", 1)[1]
            index += 1
            continue
        cleaned.append(value)
        index += 1
    return raw, cleaned, config_path, workspace_name


def _install_config_template_extension():
    """Add the documented top-level editor setting without duplicating config code."""
    from . import config as config_module

    if getattr(config_module, "_lifetxt_editor_extension", False):
        return
    original = config_module.config_template

    def config_template_with_editor():
        data = original()
        if "editor" not in data:
            expanded = OrderedDict()
            for key, value in data.items():
                if key == "paths":
                    expanded[key] = value
                    expanded["editor"] = ""
                else:
                    expanded[key] = value
            data = expanded
        return data

    config_module.config_template = config_template_with_editor
    config_module._lifetxt_editor_extension = True


def _legacy_main(argv):
    _install_config_template_extension()
    from . import cli as cli_module
    from .archive_safety_v3 import archive_safety_context
    from .runtime_safety_v2 import install_cli_timezone_context

    install_cli_timezone_context(cli_module)
    with archive_safety_context(cli_module):
        return cli_module.main(argv)


def _review_selector_args(argv, today=None):
    """Translate review convenience selectors into the legacy shared range flags."""
    args = list(argv)
    today = today or timezone_today()
    selectors = [
        name for name in ("--last-week", "--last-month", "--year") if name in args
    ]
    if not selectors:
        return args
    if len(selectors) > 1:
        raise ValueError("Use only one of --last-week, --last-month, or --year.")
    if any(name in args for name in ("--week", "--month", "--from", "--to")):
        raise ValueError(
            "Convenience review selectors cannot be combined with --week, --month, --from, or --to."
        )

    selector = selectors[0]
    index = args.index(selector)
    if selector == "--last-week":
        del args[index]
        current_monday = today - datetime.timedelta(days=today.weekday())
        start = current_monday - datetime.timedelta(days=7)
        end = current_monday - datetime.timedelta(days=1)
        args.extend(("--from", start.isoformat(), "--to", end.isoformat()))
    elif selector == "--last-month":
        del args[index]
        first_this_month = today.replace(day=1)
        last_previous = first_this_month - datetime.timedelta(days=1)
        args.extend(
            ("--month", "%04d-%02d" % (last_previous.year, last_previous.month))
        )
    else:
        year = today.year
        if index + 1 < len(args) and not args[index + 1].startswith("-"):
            value = args[index + 1]
            if len(value) != 4 or not value.isdigit():
                raise ValueError("--year accepts a four-digit year.")
            year = int(value)
            del args[index : index + 2]
        else:
            del args[index]
        args.extend(("--from", "%04d-01-01" % year, "--to", "%04d-12-31" % year))
    return args


def _print_help():
    _install_config_template_extension()
    from .cli import build_parser

    build_parser().print_help()
    sys.stdout.write(
        "\nAdditional workflow commands:\n"
        "  next, show, edit, path, count, invoice, standup, to-ics, from-todo, from-markdown\n"
        "Release-safety and Format 1.0 commands:\n"
        "  safety locks|serve-target|timezone|revisions|transactions|write-routes|release-gate\n"
        "  attachment put|reference|delete|status\n"
        "  format info|check|canon|migrate|downgrade|schemas, capabilities\n"
        "  doctor --workspace-safety\n"
        "Additional flags:\n"
        "  review --last-week|--last-month|--year [YYYY]|--someday\n"
        "  files --open ID, who --workload, quick --journal, completion powershell\n"
        "See docs/en/new-cli-workflows.md and docs/en/release-safety-foundations.md.\n"
    )
    return 0


def _uses_workspace_safety_doctor(argv):
    for value in argv:
        if value in _DOCTOR_SAFETY_FLAGS:
            return True
        if any(value.startswith(flag + "=") for flag in _DOCTOR_SAFETY_FLAGS):
            return True
    return False


def main(argv=None):
    try:
        raw, cleaned, config_path, workspace_name = _extract_config_arg(argv)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1

    if not cleaned:
        return _legacy_main(raw)
    if cleaned == ["--help"] or cleaned == ["-h"]:
        return _print_help()

    command = cleaned[0]
    try:
        if command == "import-ics" and "--preset" in cleaned:
            preset_index = cleaned.index("--preset")
            if preset_index + 1 < len(cleaned) and cleaned[preset_index + 1] == "todo":
                transformed = (
                    ["from-todo"]
                    + cleaned[1:preset_index]
                    + cleaned[preset_index + 2 :]
                )
                from .extra_cli import main as extra_main

                return extra_main(
                    transformed,
                    config_path=config_path,
                    workspace_name=workspace_name,
                )
        if command == "review":
            if "--someday" in cleaned:
                from .extra_cli import main as extra_main

                return extra_main(
                    cleaned,
                    config_path=config_path,
                    workspace_name=workspace_name,
                )
            transformed = _review_selector_args(cleaned)
            if transformed != cleaned:
                if config_path:
                    transformed.extend(("--config", config_path))
                if workspace_name:
                    transformed.extend(("--workspace", workspace_name))
                return _legacy_main(transformed)
        if command == "files" and "--open" in cleaned:
            from .extra_cli import main as extra_main

            return extra_main(
                cleaned,
                config_path=config_path,
                workspace_name=workspace_name,
            )
        if command == "who" and "--workload" in cleaned:
            from .extra_cli import main as extra_main

            return extra_main(
                cleaned,
                config_path=config_path,
                workspace_name=workspace_name,
            )
        if command == "quick" and "--journal" in cleaned:
            from .extra_cli import main as extra_main

            return extra_main(
                cleaned,
                config_path=config_path,
                workspace_name=workspace_name,
            )
        if command == "completion" and (
            "powershell" in cleaned
            or (
                "install" in cleaned
                and "--shell" in cleaned
                and "powershell" in cleaned
            )
        ):
            from .extra_cli import main as extra_main

            return extra_main(
                cleaned,
                config_path=config_path,
                workspace_name=workspace_name,
            )
        if command == "doctor" and _uses_workspace_safety_doctor(cleaned[1:]):
            from .extra_cli import main as extra_main

            return extra_main(
                cleaned,
                config_path=config_path,
                workspace_name=workspace_name,
            )
        if command in _EXTRA_COMMANDS:
            from .extra_cli import main as extra_main

            return extra_main(
                cleaned,
                config_path=config_path,
                workspace_name=workspace_name,
            )
        return _legacy_main(raw)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1
    except OSError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
