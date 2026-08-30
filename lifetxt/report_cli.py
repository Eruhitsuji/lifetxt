"""Named periodic Markdown report profiles.

This module owns only reproducible report profile resolution and generated-file
output.  The existing ``share --format markdown`` command remains the report
body renderer and source of filtering/statistics semantics.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import io
import json
import os
import string
import sys
import tempfile

from . import report_v2
from .atomic import atomic_write_text, write_console_text
from .extra_common import (
    _load_config,
    _load_items,
    _resolved_input_paths,
    _resolved_path,
)
from .ids import id_key_from_config
from .timezone_policy import now as timezone_now
from .timezone_policy import resolve_timezone_name
from .timezone_policy import today as timezone_today

REPORT_SCHEMA = "lifetxt-report-v1"
PERIODS = report_v2.PERIODS
MODES = ("replace", "create", "append")
V1_PROFILE_KEYS = frozenset(
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
V2_ONLY_KEYS = frozenset(("sections", "format", "audience", "compare", "email"))
PROFILE_KEYS = V1_PROFILE_KEYS | V2_ONLY_KEYS
OUTPUT_FIELDS = frozenset(("date", "year", "month", "iso_year", "iso_week"))
EMAIL_CONFIG_KEYS = frozenset(
    ("to", "subject", "smtp_host_env", "smtp_user_env", "smtp_pass_env")
)

resolve_period = report_v2.resolve_period


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m lifetxt report",
        description="Generate named periodic Markdown reports from configured profiles.",
    )
    subparsers = parser.add_subparsers(dest="report_command", required=True)

    list_parser = subparsers.add_parser("list", help="List configured report profiles.")
    list_parser.set_defaults(func=_command_list)

    preview = subparsers.add_parser(
        "preview",
        help="Render one configured report to stdout without writing its target.",
    )
    preview.add_argument("name", help="Configured report profile name.")
    _add_period_selection_arguments(preview)
    preview.add_argument(
        "--format",
        choices=report_v2.FORMATS,
        help="Override a Report v2 profile's configured output format.",
    )
    preview.set_defaults(func=_command_preview)

    run = subparsers.add_parser("run", help="Generate one configured report file.")
    run.add_argument("name", help="Configured report profile name.")
    _add_period_selection_arguments(run)
    run.set_defaults(func=_command_run)

    send = subparsers.add_parser(
        "send",
        help="Render one configured report and email it via its `email` settings.",
    )
    send.add_argument("name", help="Configured report profile name.")
    _add_period_selection_arguments(send)
    send.add_argument(
        "--dry-run",
        action="store_true",
        help="Render and print what would be sent without contacting SMTP.",
    )
    send.set_defaults(func=_command_send)
    return parser


def _add_period_selection_arguments(subparser):
    subparser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="Generate the calendar period containing this date instead of today.",
    )
    subparser.add_argument(
        "--previous",
        action="store_true",
        help="Generate the immediately completed previous calendar period.",
    )


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


def _validate_email_config(name, value):
    if not isinstance(value, dict):
        raise ValueError("Report profile %s email must be an object." % name)
    unknown = sorted(set(value) - EMAIL_CONFIG_KEYS)
    if unknown:
        raise ValueError(
            "Report profile %s email has unknown key(s): %s"
            % (name, ", ".join(str(key) for key in unknown))
        )
    to_value = value.get("to")
    if not to_value or not (
        (isinstance(to_value, str) and to_value.strip())
        or (
            isinstance(to_value, list)
            and all(isinstance(v, str) and v.strip() for v in to_value)
            and to_value
        )
    ):
        raise ValueError(
            "Report profile %s email.to must be a non-empty string or array of strings."
            % name
        )
    for key in ("subject", "smtp_host_env", "smtp_user_env", "smtp_pass_env"):
        if key in value and (not isinstance(value[key], str) or not value[key].strip()):
            raise ValueError(
                "Report profile %s email.%s must be a non-empty string." % (name, key)
            )
    return dict(value)


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
            "Report profile %s period must be one of: %s." % (name, ", ".join(PERIODS))
        )
    mode = value.get("mode", "replace")
    if mode not in MODES:
        raise ValueError(
            "Report profile %s mode must be one of: %s." % (name, ", ".join(MODES))
        )

    is_v2 = "sections" in value

    if not is_v2:
        v1_unknown = sorted(set(value) & V2_ONLY_KEYS - {"email"})
        if v1_unknown:
            raise ValueError(
                "Report profile %s uses Report v2 key(s) %s without `sections`."
                % (name, ", ".join(v1_unknown))
            )

    for key in ("output", "title", "project", "type", "tag"):
        if key in value and (not isinstance(value[key], str) or not value[key].strip()):
            raise ValueError(
                "Report profile %s %s must be a non-empty string." % (name, key)
            )
    for key in ("open", "frontmatter"):
        if key in value and not isinstance(value[key], bool):
            raise ValueError(
                "Report profile %s %s must be true or false." % (name, key)
            )

    result = dict(value)
    result["period"] = period
    result["mode"] = mode
    result.setdefault("frontmatter", True)

    if is_v2:
        output_format = value.get("format", "markdown")
        if output_format not in report_v2.FORMATS:
            raise ValueError(
                "Report profile %s format must be one of: %s."
                % (name, ", ".join(report_v2.FORMATS))
            )
        audience = value.get("audience", "private")
        if audience not in report_v2.AUDIENCES:
            raise ValueError(
                "Report profile %s audience must be one of: %s."
                % (name, ", ".join(report_v2.AUDIENCES))
            )
        compare = value.get("compare")
        if compare is not None and compare not in report_v2.COMPARE_MODES:
            raise ValueError(
                "Report profile %s compare must be one of: %s."
                % (name, ", ".join(report_v2.COMPARE_MODES))
            )
        try:
            report_v2.validate_sections(value.get("sections"), audience=audience)
        except report_v2.ReportError as exc:
            raise ValueError("Report profile %s: %s" % (name, exc))
        result["format"] = output_format
        result["audience"] = audience
        if "email" in value:
            result["email"] = _validate_email_config(name, value["email"])
    elif "email" in value:
        result["email"] = _validate_email_config(name, value["email"])

    return result


def _profile_named(config_data, name):
    profiles = _profiles(config_data)
    if name not in profiles:
        available = ", ".join(sorted(profiles)) or "(none configured)"
        raise ValueError(
            "Report profile not found: %s. Available: %s" % (name, available)
        )
    return profiles[name]


def _parse_anchor_date(value):
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValueError("Invalid --date value: %s. Use YYYY-MM-DD." % value)


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


def _resolve_anchor_day(config_data, timezone_name, date_override=None):
    if date_override:
        return _parse_anchor_date(date_override)
    return timezone_today(timezone_name)


def _period_context(profile, config_data, date_override=None, previous=False):
    if date_override and previous:
        raise ValueError("Use either --date or --previous, not both.")
    timezone_name = _timezone_name(config_data)
    day = _resolve_anchor_day(config_data, timezone_name, date_override)
    start, end = resolve_period(profile["period"], day)
    if previous:
        start, end = report_v2.previous_period(profile["period"], start, end)
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
            raise ValueError(
                "Report output placeholders do not accept format specs or conversions."
            )
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

    # `share` always writes its rendered Markdown to a file (defaulting to
    # ./share.md when no -o is given); it has no stdout mode. Point it at a
    # disposable temp file and read that back, so this report profile's body
    # is the real rendered content rather than share's "Wrote share.md (N
    # item(s))." confirmation line, and so no stray share.md is left in the
    # current working directory.
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    )
    temp_path = handle.name
    handle.close()
    try:
        argv = _share_argv(
            profile,
            start,
            end,
            config_path=config_path,
            workspace_name=workspace_name,
        )
        argv.extend(("-o", temp_path))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = _legacy_main(argv)
        if result:
            raise ValueError(
                "share report rendering failed with exit code %s." % result
            )
        with open(temp_path, "r", encoding="utf-8-sig", newline="") as body_handle:
            return body_handle.read()
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


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


def render_report(
    name,
    profile,
    config_data,
    config_path=None,
    workspace_name=None,
    date_override=None,
    previous=False,
):
    timezone_name, start, end, generated = _period_context(
        profile, config_data, date_override=date_override, previous=previous
    )
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


def render_report_v2(
    name,
    profile,
    config_data,
    config_path=None,
    workspace_name=None,
    date_override=None,
    previous=False,
    format_override=None,
):
    """Build and render a Report v2 (``sections``-based) profile.

    Parses the configured workspace once into a :class:`report_v2.ReportContext`,
    runs the configured section providers, and renders the resulting Report
    Model in the requested format. Returns ``(text, start, end, model)``.
    """
    if date_override and previous:
        raise ValueError("Use either --date or --previous, not both.")
    timezone_name = _timezone_name(config_data)
    day = _resolve_anchor_day(config_data, timezone_name, date_override)
    start, end = resolve_period(profile["period"], day)
    if previous:
        start, end = report_v2.previous_period(profile["period"], start, end)
    generated = timezone_now(timezone_name)

    items = _load_items([], config_data)
    id_key = id_key_from_config(config_data)
    context = report_v2.ReportContext(
        items,
        config_data,
        day,
        profile["period"],
        start,
        end,
        timezone_name,
        id_key=id_key,
        config_path=config_path,
        workspace_name=workspace_name,
    )

    previous_context = None
    if profile.get("compare") == "previous":
        prev_start, prev_end = report_v2.previous_period(profile["period"], start, end)
        previous_context = context.with_period(prev_start, prev_end)

    model = report_v2.build_report_model(
        name, profile, context, generated, previous_context=previous_context
    )
    output_format = format_override or profile.get("format", "markdown")
    text = report_v2.render_model(model, output_format)
    return text, start, end, model


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


def _render_named_report(
    args, config_data, config_path=None, workspace_name=None, format_override=None
):
    profile = _profile_named(config_data, args.name)
    date_override = getattr(args, "date", None)
    previous = getattr(args, "previous", False)
    if "sections" in profile:
        text, start, end, _model = render_report_v2(
            args.name,
            profile,
            config_data,
            config_path=config_path,
            workspace_name=workspace_name,
            date_override=date_override,
            previous=previous,
            format_override=format_override,
        )
    else:
        if format_override:
            raise ValueError(
                "--format is only supported for report profiles that declare `sections` (Report v2)."
            )
        text, start, end = render_report(
            args.name,
            profile,
            config_data,
            config_path=config_path,
            workspace_name=workspace_name,
            date_override=date_override,
            previous=previous,
        )
    return profile, text, start, end


def _command_preview(args, config_data, config_path=None, workspace_name=None):
    _profile, text, _start, _end = _render_named_report(
        args,
        config_data,
        config_path=config_path,
        workspace_name=workspace_name,
        format_override=getattr(args, "format", None),
    )
    write_console_text(sys.stdout, text)
    return 0


def _command_run(args, config_data, config_path=None, workspace_name=None):
    profile, text, start, _end = _render_named_report(
        args, config_data, config_path=config_path, workspace_name=workspace_name
    )
    path = _resolved_output(profile, start, config_data)
    _write_report(path, text, profile["mode"])
    write_console_text(sys.stdout, "Wrote report %s: %s\n" % (args.name, path))
    return 0


def _resolve_email_subject(template, name, start, end):
    try:
        return template.format(
            period_start=start.isoformat(), period_end=end.isoformat(), report=name
        )
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError("Invalid report email subject template: %s" % exc)


def _command_send(args, config_data, config_path=None, workspace_name=None):
    profile = _profile_named(config_data, args.name)
    email_config = profile.get("email")
    if not email_config:
        raise ValueError(
            "Report profile %s has no `email` configuration for `report send`."
            % args.name
        )
    _profile, text, start, end = _render_named_report(
        args, config_data, config_path=config_path, workspace_name=workspace_name
    )

    from .mail_delivery import send_smtp_text

    subject = _resolve_email_subject(
        email_config.get("subject") or "lifetxt report: %s" % args.name,
        args.name,
        start,
        end,
    )
    send_smtp_text(
        subject,
        text,
        email_config.get("to"),
        host_env=email_config.get("smtp_host_env", "LIFETXT_SMTP_HOST"),
        user_env=email_config.get("smtp_user_env", "LIFETXT_SMTP_USER"),
        pass_env=email_config.get("smtp_pass_env", "LIFETXT_SMTP_PASS"),
        dry_run=getattr(args, "dry_run", False),
        output=sys.stdout,
    )
    return 0
