"""Named periodic Markdown report profiles.

This module owns only reproducible report profile resolution and generated-file
output.  The existing ``share --format markdown`` command remains the report
body renderer and source of filtering/statistics semantics.
"""

from __future__ import annotations

import argparse
import calendar
import contextlib
import datetime
import io
import json
import os
import string
import sys

from .atomic import atomic_write_text, write_console_text
from .extra_common import _load_config, _resolved_input_paths, _resolved_path
from .timezone_policy import now as timezone_now
from .timezone_policy import resolve_timezone_name
from .timezone_policy import today as timezone_today

REPORT_SCHEMA = "lifetxt-report-v1"
PERIODS = ("daily", "weekly", "monthly")
MODES = ("replace", "create", "append")
PROFILE_KEYS = frozenset(
    (
        "period",
        "output",
        "title",
        "project",
        "type",
        "tag",
        "open",
        "mode",
        "frontmatter",
    )
)
OUTPUT_FIELDS = frozenset(("date", "year", "month", "iso_year", "iso_week"))


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m lifetxt report",
        description="Generate named periodic Markdown reports from configured profiles.",
    )
    subparsers = parser.add_subparsers(dest="report_command", required=True)

    list_parser = subparsers.add_parser("list", help="List configured report profiles.")
    list_parser.set_defaults(func=_command_list)

    preview = subparsers.add_parser(
        "preview", help="Render one configured report to stdout without writing its target."
    )
    preview.add_argument("name", help="Configured report profile name.")
    preview.set_defaults(func=_command_preview)

    run = subparsers.add_parser("run", help="Generate one configured report file.")
    run.add_argument("name", help="Configured report profile name.")
    run.set_defaults(func=_command_run)
    return parser


def main(argv=None, config_path=None, workspace_name=None):
    values = list(sys.argv[1:] if argv is None else argv)
    if values and values[0] == "report":
        values = values[1:]
    args = build_parser().parse_args(values)
    config_data = _load_config(config_path, workspace_name)
    return args.func(
        args,
        config_data=config_data,
        config_path=config_path,
        workspace_name=workspace_name,
    )


def _profiles(config_data):
    value = config_data.get("reports")
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Config reports must be an object of named report profiles.")
    result = {}
    for name in sorted(value):
        text_name = str(name).strip()
        if not text_name:
            raise ValueError("Report profile names must not be empty.")
        result[text_name] = _validate_profile(text_name, value[name])
    return result


def _validate_profile(name, value):
    if not isinstance(value, dict):
        raise ValueError("Report profile %s must be an object." % name)
    unknown = sorted(set(value) - PROFILE_KEYS)
    if unknown:
        raise ValueError(
            "Report profile %s has unknown key(s): %s"
            % (name, ", ".join(str(key) for key in unknown))
        )
    period = value.get("period")
    if period not in PERIODS:
        raise ValueError(
            "Report profile %s period must be one of: %s."
            % (name, ", ".join(PERIODS))
        )
    mode = value.get("mode", "replace")
    if mode not in MODES:
        raise ValueError(
            "Report profile %s mode must be one of: %s."
            % (name, ", ".join(MODES))
        )
    for key in ("output", "title", "project", "type", "tag"):
        if key in value and (not isinstance(value[key], str) or not value[key].strip()):
            raise ValueError("Report profile %s %s must be a non-empty string." % (name, key))
    for key in ("open", "frontmatter"):
        if key in value and not isinstance(value[key], bool):
            raise ValueError("Report profile %s %s must be true or false." % (name, key))
    result = dict(value)
    result["period"] = period
    result["mode"] = mode
    result.setdefault("frontmatter", True)
    return result


def _profile_named(config_data, name):
    profiles = _profiles(config_data)
    if name not in profiles:
        available = ", ".join(sorted(profiles)) or "(none configured)"
        raise ValueError("Report profile not found: %s. Available: %s" % (name, available))
    return profiles[name]


def resolve_period(period, day):
    if period == "daily":
        return day, day
    if period == "weekly":
        start = day - datetime.timedelta(days=day.weekday())
        return start, start + datetime.timedelta(days=6)
    if period == "monthly":
        start = day.replace(day=1)
        end = day.replace(day=calendar.monthrange(day.year, day.month)[1])
        return start, end
    raise ValueError("Unsupported report period: %s" % period)


def _timezone_text(config_data):
    try:
        paths = _resolved_input_paths([], config_data)
    except (OSError, ValueError):
        paths = []
    for path in paths:
        if path == "-" or not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            return handle.read()
    return ""


def _timezone_name(config_data):
    return resolve_timezone_name(config_data, text=_timezone_text(config_data))


def _period_context(profile, config_data):
    timezone_name = _timezone_name(config_data)
    day = timezone_today(timezone_name)
    start, end = resolve_period(profile["period"], day)
    generated = timezone_now(timezone_name)
    return timezone_name, start, end, generated


def resolve_output_template(template, start):
    iso_year, iso_week, _iso_day = start.isocalendar()
    values = {
        "date": start.isoformat(),
        "year": "%04d" % start.year,
        "month": "%02d" % start.month,
        "iso_year": "%04d" % iso_year,
        "iso_week": "%02d" % iso_week,
    }
    formatter = string.Formatter()
    for _literal, field_name, format_spec, conversion in formatter.parse(template):
        if field_name is None:
            continue
        if field_name not in OUTPUT_FIELDS:
            raise ValueError("Unknown report output placeholder: {%s}" % field_name)
        if format_spec or conversion:
            raise ValueError("Report output placeholders do not accept format specs or conversions.")
    try:
        return template.format_map(values)
    except (KeyError, ValueError) as exc:
        raise ValueError("Invalid report output template: %s" % exc)


def _share_argv(profile, start, end, config_path=None, workspace_name=None):
    argv = []
    if config_path:
        argv.extend(("--config", config_path))
    if workspace_name:
        argv.extend(("--workspace", workspace_name))
    argv.extend(
        (
            "share",
            "--format",
            "markdown",
            "--after",
            start.isoformat(),
            "--before",
            end.isoformat(),
        )
    )
    if profile.get("title"):
        argv.extend(("--title", profile["title"]))
    if profile.get("project"):
        argv.extend(("--project", profile["project"]))
    if profile.get("type"):
        argv.extend(("--type", profile["type"]))
    if profile.get("tag"):
        argv.extend(("--tag", profile["tag"]))
    if profile.get("open"):
        argv.append("--open")
    return argv


def _render_share(profile, start, end, config_path=None, workspace_name=None):
    from .entrypoint import _legacy_main

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = _legacy_main(
            _share_argv(
                profile,
                start,
                end,
                config_path=config_path,
                workspace_name=workspace_name,
            )
        )
    if result:
        raise ValueError("share report rendering failed with exit code %s." % result)
    return output.getvalue()


def _frontmatter(name, profile, start, end, generated, timezone_name):
    lines = [
        "---",
        "generator: lifetxt",
        "report_schema: %s" % REPORT_SCHEMA,
        "report: %s" % json.dumps(name, ensure_ascii=False),
        "period: %s" % profile["period"],
        "period_start: %s" % start.isoformat(),
        "period_end: %s" % end.isoformat(),
        "generated_at: %s" % json.dumps(generated.isoformat(timespec="seconds")),
        "timezone: %s" % json.dumps(timezone_name, ensure_ascii=False),
        "---",
        "",
    ]
    return "\n".join(lines)


def render_report(name, profile, config_data, config_path=None, workspace_name=None):
    timezone_name, start, end, generated = _period_context(profile, config_data)
    body = _render_share(
        profile,
        start,
        end,
        config_path=config_path,
        workspace_name=workspace_name,
    )
    if body and not body.endswith("\n"):
        body += "\n"
    if profile.get("frontmatter", True):
        body = _frontmatter(name, profile, start, end, generated, timezone_name) + body
    return body, start, end


def _resolved_output(profile, start, config_data):
    template = profile.get("output")
    if not template:
        raise ValueError("Report profile is missing required output for `report run`.")
    rendered = resolve_output_template(template, start)
    config_path = config_data.get("_path")
    base = os.path.dirname(os.path.abspath(config_path)) if config_path else None
    return _resolved_path(rendered, base=base)


def _write_report(path, text, mode):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if mode == "create":
        if os.path.exists(path):
            raise ValueError("Report output already exists in create mode: %s" % path)
        atomic_write_text(path, text)
        return
    if mode == "append":
        current = ""
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8-sig", newline="") as handle:
                current = handle.read()
        if current and not current.endswith("\n"):
            current += "\n"
        atomic_write_text(path, current + text)
        return
    atomic_write_text(path, text)


def _command_list(args, config_data, config_path=None, workspace_name=None):
    profiles = _profiles(config_data)
    if not profiles:
        write_console_text(sys.stdout, "No report profiles configured.\n")
        return 0
    lines = ["NAME\tPERIOD\tMODE\tOUTPUT"]
    for name in sorted(profiles):
        profile = profiles[name]
        lines.append(
            "%s\t%s\t%s\t%s"
            % (name, profile["period"], profile["mode"], profile.get("output", ""))
        )
    write_console_text(sys.stdout, "\n".join(lines) + "\n")
    return 0


def _command_preview(args, config_data, config_path=None, workspace_name=None):
    profile = _profile_named(config_data, args.name)
    text, _start, _end = render_report(
        args.name,
        profile,
        config_data,
        config_path=config_path,
        workspace_name=workspace_name,
    )
    write_console_text(sys.stdout, text)
    return 0


def _command_run(args, config_data, config_path=None, workspace_name=None):
    profile = _profile_named(config_data, args.name)
    text, start, _end = render_report(
        args.name,
        profile,
        config_data,
        config_path=config_path,
        workspace_name=workspace_name,
    )
    path = _resolved_output(profile, start, config_data)
    _write_report(path, text, profile["mode"])
    write_console_text(sys.stdout, "Wrote report %s: %s\n" % (args.name, path))
    return 0
