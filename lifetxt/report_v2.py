"""Report v2: a composition layer over lifetxt's existing deterministic
domain aggregations.

Report v2 parses the configured workspace **once** per invocation into a
:class:`ReportContext`, then runs each configured section through a small
provider registry that adapts an *already-existing* domain aggregation
function (:func:`lifetxt.review.build_review`, :func:`lifetxt.stats.build_stats`,
:func:`lifetxt.agenda.agenda_records`, :func:`lifetxt.command_center.command_center`,
:func:`lifetxt.projects.portfolio`, :func:`lifetxt.nextaction.next_action_items`,
:func:`lifetxt.inbox.inbox_summary`, :func:`lifetxt.health.build_health`) and
assembles the results into one deterministic Report Model.  Renderers
(Markdown/JSON/HTML) are pure presentation functions over that already-built
model; no renderer re-parses life.txt, calls a provider, or reimplements a
section's semantics.

A v1 report profile (no ``sections`` key) is untouched and keeps rendering
through :mod:`lifetxt.report_cli`'s existing ``share --format markdown``
delegation. A profile that declares ``sections`` opts into this module.
"""

from __future__ import annotations

import calendar
import datetime
import json as json_module
from collections import OrderedDict

REPORT_SCHEMA_V2 = "lifetxt-report-v2"
PERIODS = ("daily", "weekly", "monthly")
FORMATS = ("markdown", "json", "html")
AUDIENCES = ("private", "external")
COMPARE_MODES = ("previous",)

# Section types allowed when a profile's audience is "external". The first
# slice is deliberately conservative: aggregate-only sections are allowed,
# and every allowed section's data is still passed through
# :func:`redact_for_external_audience` before rendering.
EXTERNAL_SAFE_SECTION_TYPES = frozenset(("stats", "health", "project-health"))

# Report-wide `scope` keys (#613): applied once to the parsed item set,
# before any section provider runs, using the shared filtering primitive
# every other lifetxt surface (CLI filter/agenda/query) already uses.
SCOPE_KEYS = frozenset(("project", "tag", "type", "open", "status", "person"))
_SCOPE_LIST_OR_STRING_KEYS = ("project", "tag", "type", "status", "person")


class ReportError(ValueError):
    """Raised for Report v2 configuration, resolution, or composition errors."""


def resolve_period(period, day):
    """Return the (start, end) date window containing ``day`` for ``period``."""
    if period == "daily":
        return day, day
    if period == "weekly":
        start = day - datetime.timedelta(days=day.weekday())
        return start, start + datetime.timedelta(days=6)
    if period == "monthly":
        start = day.replace(day=1)
        end = day.replace(day=calendar.monthrange(day.year, day.month)[1])
        return start, end
    raise ReportError("Unsupported report period: %s" % period)


def previous_period(period, start, end):
    """Return the (start, end) window immediately before ``[start, end]``."""
    if period == "daily":
        prev = start - datetime.timedelta(days=1)
        return prev, prev
    if period == "weekly":
        prev_start = start - datetime.timedelta(days=7)
        return prev_start, prev_start + datetime.timedelta(days=6)
    if period == "monthly":
        prev_end = start - datetime.timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        return prev_start, prev_end
    raise ReportError("Unsupported report period: %s" % period)


def next_period(period, start, end):
    """Return the (start, end) window immediately after ``[start, end]``."""
    if period == "daily":
        nxt = end + datetime.timedelta(days=1)
        return nxt, nxt
    if period == "weekly":
        nxt_start = end + datetime.timedelta(days=1)
        return nxt_start, nxt_start + datetime.timedelta(days=6)
    if period == "monthly":
        nxt_start = end + datetime.timedelta(days=1)
        last_day = calendar.monthrange(nxt_start.year, nxt_start.month)[1]
        return nxt_start, nxt_start.replace(day=last_day)
    raise ReportError("Unsupported report period: %s" % period)


class ReportContext:
    """Parsed-once composition context shared by every section provider."""

    def __init__(
        self,
        items,
        config_data,
        reference_date,
        period,
        period_start,
        period_end,
        timezone_name,
        id_key="id",
        config_path=None,
        workspace_name=None,
    ):
        self.items = items
        self.config_data = config_data
        self.reference_date = reference_date
        self.period = period
        self.period_start = period_start
        self.period_end = period_end
        self.timezone_name = timezone_name
        self.id_key = id_key
        self.config_path = config_path
        self.workspace_name = workspace_name
        self._command_center_cache = {}

    def command_center_result(
        self,
        horizon_days=3,
        next_actions_limit=None,
        inbox_limit=5,
        ticket_stale_after_days=None,
    ):
        """Return (and cache) one :func:`command_center` call for this context.

        Several section providers (``command-center``, ``next-actions``,
        ``inbox``, ``ticket-attention``) read from the same underlying
        aggregation; caching by argument tuple keeps a report invocation
        that uses more than one of them from recomputing it.
        """
        from .command_center import command_center

        cache_key = (
            horizon_days,
            next_actions_limit,
            inbox_limit,
            ticket_stale_after_days,
        )
        if cache_key not in self._command_center_cache:
            self._command_center_cache[cache_key] = command_center(
                self.items,
                config=self.config_data,
                today=self.reference_date,
                horizon_days=horizon_days,
                next_actions_limit=next_actions_limit,
                inbox_limit=inbox_limit,
                ticket_stale_after_days=ticket_stale_after_days,
            )
        return self._command_center_cache[cache_key]

    def with_period(self, period_start, period_end):
        """A shallow view of this context over a different period window.

        Used to compose the previous-period comparison run (#604): the same
        parsed items and reference date, but a different ``period_start``/
        ``period_end`` fed to every section provider.
        """
        return ReportContext(
            self.items,
            self.config_data,
            self.reference_date,
            self.period,
            period_start,
            period_end,
            self.timezone_name,
            id_key=self.id_key,
            config_path=self.config_path,
            workspace_name=self.workspace_name,
        )


# ---------------------------------------------------------------------------
# Section providers -- thin adapters over existing domain aggregations.
# ---------------------------------------------------------------------------


def _provider_review(context, options):
    from .review import build_review

    return build_review(
        context.items,
        context.period_start,
        context.period_end,
        project=options.get("project"),
        id_key=context.id_key,
        today=context.reference_date,
    )


def _provider_stats(context, options):
    from .stats import build_stats

    group = options.get("group", "daily")
    return build_stats(context.items, context.period_start, context.period_end, group)


def _agenda_range(context, selector):
    if selector in (None, "period"):
        return context.period_start, context.period_end
    if selector == "next-period":
        return next_period(context.period, context.period_start, context.period_end)
    if selector == "previous-period":
        return previous_period(context.period, context.period_start, context.period_end)
    raise ReportError("Unknown agenda report range: %s" % selector)


def _provider_agenda(context, options):
    from .agenda import agenda_records

    start, end = _agenda_range(context, options.get("range"))
    range_start = datetime.datetime.combine(start, datetime.time.min)
    range_end = datetime.datetime.combine(end, datetime.time.max)
    records = agenda_records(context.items, range_start, range_end)
    return OrderedDict(
        (
            ("from", start.isoformat()),
            ("to", end.isoformat()),
            ("records", records),
        )
    )


def _provider_command_center(context, options):
    return context.command_center_result(
        horizon_days=int(options.get("horizon", 3)),
        next_actions_limit=options.get("next_actions_limit"),
        inbox_limit=int(options.get("inbox_limit", 5)),
        ticket_stale_after_days=options.get("ticket_stale_after_days"),
    )


def _provider_project_health(context, options):
    from .projects import portfolio

    rows = portfolio(
        context.items,
        config=context.config_data,
        today=context.reference_date,
        include_archived=bool(options.get("include_archived", False)),
    )
    return OrderedDict((("projects", rows),))


def _provider_next_actions(context, options):
    from .command_center import _next_actions

    limit = options.get("limit")
    return OrderedDict((("items", _next_actions(context.items, limit)),))


def _provider_inbox(context, options):
    from .command_center import _inbox_section

    return _inbox_section(context.config_data, options.get("limit", 5))


def _provider_ticket_attention(context, options):
    from .command_center import _ticket_attention

    stale_after_days = options.get("stale_after_days")
    rows = _ticket_attention(context.items, context.reference_date, stale_after_days)
    return OrderedDict((("tickets", rows),))


def _provider_health(context, options):
    from .health import build_health

    findings = build_health(
        context.items,
        context.reference_date,
        since_days=int(options.get("since_days", 30)),
        lookahead_days=int(options.get("lookahead_days", 7)),
        ignore_codes=options.get("ignore_codes") or (),
        kinds=options.get("kinds") or (),
        config=context.config_data,
    )
    return OrderedDict((("findings", findings), ("count", len(findings))))


SECTION_PROVIDERS = OrderedDict(
    (
        ("review", _provider_review),
        ("stats", _provider_stats),
        ("agenda", _provider_agenda),
        ("command-center", _provider_command_center),
        ("project-health", _provider_project_health),
        ("next-actions", _provider_next_actions),
        ("inbox", _provider_inbox),
        ("ticket-attention", _provider_ticket_attention),
        ("health", _provider_health),
    )
)

_SECTION_TITLES = {
    "review": "Review",
    "stats": "Statistics",
    "agenda": "Agenda",
    "command-center": "Command Center",
    "project-health": "Project Health",
    "next-actions": "Next Actions",
    "inbox": "Inbox",
    "ticket-attention": "Tickets Needing Attention",
    "health": "Health",
}


def _reserved_option_keys():
    return frozenset(("type", "title"))


def validate_sections(sections, audience="private"):
    """Validate a v2 ``sections`` list, raising :class:`ReportError` on failure."""
    if not isinstance(sections, list) or not sections:
        raise ReportError("Report `sections` must be a non-empty array.")
    for entry in sections:
        if not isinstance(entry, dict):
            raise ReportError("Each report section must be an object with a `type`.")
        section_type = entry.get("type")
        if section_type not in SECTION_PROVIDERS:
            raise ReportError(
                "Unknown report section type: %r. Known types: %s"
                % (section_type, ", ".join(SECTION_PROVIDERS))
            )
        if audience == "external" and section_type not in EXTERNAL_SAFE_SECTION_TYPES:
            raise ReportError(
                "Report section type %r is not allowed for audience=external. "
                "Allowed: %s"
                % (section_type, ", ".join(sorted(EXTERNAL_SAFE_SECTION_TYPES)))
            )
    return sections


def validate_scope(scope):
    """Validate a report-wide ``scope`` object, raising :class:`ReportError`.

    ``scope`` may be ``None`` (no report-wide filter), in which case an
    empty dict is returned.
    """
    if scope is None:
        return {}
    if not isinstance(scope, dict):
        raise ReportError("Report `scope` must be an object.")
    unknown = sorted(set(scope) - SCOPE_KEYS)
    if unknown:
        raise ReportError(
            "Report scope has unknown key(s): %s" % ", ".join(str(k) for k in unknown)
        )
    for key in _SCOPE_LIST_OR_STRING_KEYS:
        if key in scope and not isinstance(scope[key], (list, str)):
            raise ReportError(
                "Report scope.%s must be a string or an array of strings." % key
            )
    if "open" in scope and not isinstance(scope["open"], bool):
        raise ReportError("Report scope.open must be true or false.")
    return scope


def _scope_list(scope, key):
    value = scope.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return value


def apply_scope(items, scope):
    """Filter ``items`` once by ``scope``, shared by every section provider.

    Reuses :func:`lifetxt.agenda.filter_items` -- the same surface-neutral
    filtering primitive the CLI ``filter``/``agenda`` commands and `query`
    already use -- rather than a report-only filter engine. A provider may
    narrow this result further (e.g. ``agenda``'s own ``range`` option) but
    section providers never see an item this function excluded.
    """
    if not scope:
        return items
    from .agenda import filter_items

    return filter_items(
        items,
        open_only=bool(scope.get("open", False)),
        statuses=_scope_list(scope, "status"),
        kinds=_scope_list(scope, "type"),
        projects=_scope_list(scope, "project"),
        tags=_scope_list(scope, "tag"),
        persons=_scope_list(scope, "person"),
    )


# ---------------------------------------------------------------------------
# External-safe redaction (#603) -- aggregate-only by default.
# ---------------------------------------------------------------------------

_EXTERNAL_UNSAFE_KEYS = frozenset(
    (
        "title",
        "titles",
        "blocked_title",
        "source",
        "path",
        "summary",
        "text",
        "body",
        "excerpt",
        "message",
        "assignee",
        "owner",
        "recipient",
        "display_name",
        "reasons",
        "person",
        "records",
        "completed",
        "journal_entries",
        "mood_trend",
        "findings",
        "tickets",
        "items",
        "pending",
        "projects",
        "id",
    )
)


def redact_for_external_audience(value):
    """Strip verbatim personal content from section data (#603, first slice).

    Conservative by design: any key that could carry a raw title, path,
    excerpt, or other personal text is dropped; a dropped list is replaced by
    its own count under ``<key>_count`` so the aggregate shape survives.
    Everything else (numeric/boolean/short scalar summary fields) passes
    through unchanged. Applied recursively over the whole section payload.
    """
    if isinstance(value, dict):
        result = OrderedDict()
        for key, val in value.items():
            if key in _EXTERNAL_UNSAFE_KEYS:
                if isinstance(val, list):
                    result[str(key) + "_count"] = len(val)
                continue
            result[key] = redact_for_external_audience(val)
        return result
    if isinstance(value, list):
        return [redact_for_external_audience(item) for item in value]
    return value


def _defense_in_depth_redact(value):
    from .remote_access import redact_remote_value

    return redact_remote_value(value)


# ---------------------------------------------------------------------------
# Comparison (#604) -- a generic numeric diff over two section results.
# ---------------------------------------------------------------------------


def _numeric_diff(current, previous, prefix=""):
    diffs = OrderedDict()
    if isinstance(current, dict) and isinstance(previous, dict):
        for key in current:
            if key in previous:
                diffs.update(
                    _numeric_diff(current[key], previous[key], prefix + str(key) + ".")
                )
        return diffs
    is_number = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    if is_number(current) and is_number(previous):
        field = prefix.rstrip(".")
        diffs[field] = OrderedDict(
            (
                ("current", current),
                ("previous", previous),
                ("delta", current - previous),
            )
        )
    return diffs


# ---------------------------------------------------------------------------
# Report Model
# ---------------------------------------------------------------------------


def build_report_model(
    name,
    profile,
    context,
    generated_at,
    previous_context=None,
):
    """Build the deterministic Report Model for one report invocation.

    ``profile`` is a validated v2 report profile (``sections`` present).
    ``previous_context`` is supplied when ``profile.get("compare") ==
    "previous"``; each section is then also computed against it and a
    generic numeric diff is attached as ``section["compare"]``.
    """
    audience = profile.get("audience", "private")
    sections_config = validate_sections(profile.get("sections"), audience=audience)

    sections = []
    for section_config in sections_config:
        section_type = section_config["type"]
        provider = SECTION_PROVIDERS[section_type]
        options = {
            key: val
            for key, val in section_config.items()
            if key not in _reserved_option_keys()
        }
        data = provider(context, options)
        if audience == "external":
            data = redact_for_external_audience(data)
            data = _defense_in_depth_redact(data)

        entry = OrderedDict()
        entry["type"] = section_type
        entry["title"] = section_config.get("title") or _SECTION_TITLES.get(
            section_type, section_type
        )
        entry["data"] = data

        if previous_context is not None:
            previous_data = provider(previous_context, options)
            if audience == "external":
                previous_data = redact_for_external_audience(previous_data)
                previous_data = _defense_in_depth_redact(previous_data)
            compare = _numeric_diff(data, previous_data)
            entry["compare"] = compare or None
        sections.append(entry)

    model = OrderedDict()
    model["report_schema"] = REPORT_SCHEMA_V2
    model["report"] = name
    model["title"] = profile.get("title") or name
    model["period"] = profile["period"]
    model["period_start"] = context.period_start.isoformat()
    model["period_end"] = context.period_end.isoformat()
    model["generated_at"] = generated_at.isoformat(timespec="seconds")
    model["timezone"] = context.timezone_name
    model["audience"] = audience
    model["compare"] = profile.get("compare")
    model["sections"] = sections
    return model


# ---------------------------------------------------------------------------
# Renderers -- pure presentation functions over an already-built Report Model.
# ---------------------------------------------------------------------------


def render_json(model, pretty=True):
    return json_module.dumps(
        model,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    ) + ("\n" if pretty else "")


def _html_escape(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _flatten_for_bullets(value, depth=0):
    """A small, deterministic dict/list -> Markdown/HTML bullet dumper.

    Used as the generic fallback (and for several sections' full rendering)
    so every section type renders something readable without hand-writing a
    bespoke formatter for each one.
    """
    lines = []
    if isinstance(value, dict):
        for key, val in value.items():
            if isinstance(val, (dict, list)) and val:
                lines.append("%s%s:" % ("  " * depth, key))
                lines.extend(_flatten_for_bullets(val, depth + 1))
            else:
                lines.append("%s%s: %s" % ("  " * depth, key, val))
    elif isinstance(value, list):
        for entry in value:
            if isinstance(entry, (dict, list)):
                lines.append("%s-" % ("  " * depth))
                lines.extend(_flatten_for_bullets(entry, depth + 1))
            else:
                lines.append("%s- %s" % ("  " * depth, entry))
    else:
        lines.append("%s%s" % ("  " * depth, value))
    return lines


def _render_section_markdown(section_type, data):
    lines = []
    if section_type == "review":
        lines.append("- Completed tasks: %d" % data.get("completed_tasks", 0))
        lines.append("- Open tasks: %d" % data.get("open_tasks", 0))
        habits = data.get("habits") or {}
        for title, habit in habits.items():
            lines.append(
                "- Habit %s: %d/%d (%d%%), streak %d (best %d)"
                % (
                    title,
                    habit.get("done", 0),
                    habit.get("done", 0) + habit.get("open", 0),
                    habit.get("completion_rate", 0),
                    habit.get("current_streak", 0),
                    habit.get("longest_streak", 0),
                )
            )
        for project, minutes in (data.get("elapsed_by_project") or {}).items():
            lines.append("- Elapsed on %s: %s" % (project, minutes))
        if data.get("journals"):
            lines.append("- Journal entries: %d" % data["journals"])
        return lines
    if section_type == "stats":
        tasks = data.get("tasks") or {}
        lines.append(
            "- Tasks: %s / %s done (%s%%), %s overdue"
            % (
                tasks.get("done", 0),
                tasks.get("total", 0),
                tasks.get("rate", 0),
                tasks.get("overdue", 0),
            )
        )
        if data.get("journal_entries"):
            lines.append("- Journal entries: %d" % data["journal_entries"])
        return lines
    if section_type == "agenda":
        records = data.get("records") or []
        if not records:
            lines.append("- No agenda items in range.")
        for record in records:
            lines.append(
                "- %s [%s] %s"
                % (
                    record.get("when", ""),
                    record.get("status", ""),
                    record.get("title", ""),
                )
            )
        return lines
    if section_type == "health":
        findings = data.get("findings") or []
        if not findings:
            lines.append("- No health findings.")
        for finding in findings:
            lines.append(
                "- %s %s: %s"
                % (
                    finding.get("code", ""),
                    finding.get("title", ""),
                    finding.get("message", ""),
                )
            )
        return lines
    if section_type == "ticket-attention":
        tickets = data.get("tickets") or []
        if not tickets:
            lines.append("- No tickets need attention.")
        for row in tickets:
            lines.append(
                "- %s: %s"
                % (
                    row.get("id") or row.get("title") or "",
                    ", ".join(row.get("reasons") or []),
                )
            )
        return lines
    if section_type == "next-actions":
        actions = data.get("items") or []
        if not actions:
            lines.append("- No actionable items.")
        for row in actions:
            lines.append("- %s" % row.get("title", ""))
        return lines
    if section_type == "inbox":
        lines.append(
            "- Pending: %d, deferred: %d, total: %d"
            % (
                data.get("pending_count", 0),
                data.get("deferred_count", 0),
                data.get("total", 0),
            )
        )
        for row in data.get("pending") or []:
            lines.append("- %s" % row.get("summary", ""))
        return lines
    if section_type == "project-health":
        for row in data.get("projects") or []:
            lines.append(
                "- %s: %s (%s%% done)"
                % (
                    row.get("display_name") or row.get("name"),
                    row.get("health", ""),
                    row.get("progress_percent")
                    if row.get("progress_percent") is not None
                    else "?",
                )
            )
        if not data.get("projects"):
            lines.append("- No projects.")
        return lines
    if section_type == "command-center":
        counts = data.get("counts") or {}
        for key, value in counts.items():
            lines.append("- %s: %s" % (key, value))
        return lines
    return _flatten_for_bullets(data)


def render_markdown(model):
    lines = []
    lines.append("---")
    lines.append("generator: lifetxt")
    lines.append("report_schema: %s" % model["report_schema"])
    lines.append("report: %s" % json_module.dumps(model["report"], ensure_ascii=False))
    lines.append("period: %s" % model["period"])
    lines.append("period_start: %s" % model["period_start"])
    lines.append("period_end: %s" % model["period_end"])
    lines.append("generated_at: %s" % json_module.dumps(model["generated_at"]))
    lines.append(
        "timezone: %s" % json_module.dumps(model["timezone"], ensure_ascii=False)
    )
    lines.append("audience: %s" % model["audience"])
    lines.append("---")
    lines.append("")
    lines.append("# %s" % model["title"])
    lines.append("")
    lines.append(
        "Period: %s to %s (%s)"
        % (model["period_start"], model["period_end"], model["period"])
    )
    lines.append("")
    for section in model["sections"]:
        lines.append("## %s" % section["title"])
        lines.append("")
        lines.extend(_render_section_markdown(section["type"], section["data"]))
        compare = section.get("compare")
        if compare:
            lines.append("")
            lines.append("Compared to previous period:")
            for field, delta in compare.items():
                sign = "+" if delta["delta"] >= 0 else ""
                lines.append(
                    "- %s: %s -> %s (%s%s)"
                    % (field, delta["previous"], delta["current"], sign, delta["delta"])
                )
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def _render_section_html(section_type, data):
    return "<pre>%s</pre>" % _html_escape(
        "\n".join(_render_section_markdown(section_type, data))
    )


def render_html(model):
    parts = []
    parts.append("<!doctype html>")
    parts.append('<html lang="en"><head><meta charset="utf-8">')
    parts.append("<title>%s</title></head><body>" % _html_escape(model["title"]))
    parts.append("<h1>%s</h1>" % _html_escape(model["title"]))
    parts.append(
        "<p>Period: %s to %s (%s)</p>"
        % (
            _html_escape(model["period_start"]),
            _html_escape(model["period_end"]),
            _html_escape(model["period"]),
        )
    )
    parts.append("<p>Generated: %s</p>" % _html_escape(model["generated_at"]))
    for section in model["sections"]:
        parts.append("<h2>%s</h2>" % _html_escape(section["title"]))
        parts.append(_render_section_html(section["type"], section["data"]))
        compare = section.get("compare")
        if compare:
            parts.append("<h3>Compared to previous period</h3><ul>")
            for field, delta in compare.items():
                parts.append(
                    "<li>%s: %s -&gt; %s (%s)</li>"
                    % (
                        _html_escape(field),
                        _html_escape(delta["previous"]),
                        _html_escape(delta["current"]),
                        _html_escape(delta["delta"]),
                    )
                )
            parts.append("</ul>")
    parts.append("</body></html>")
    return "\n".join(parts) + "\n"


RENDERERS = OrderedDict(
    (
        ("markdown", render_markdown),
        ("json", render_json),
        ("html", render_html),
    )
)


def render_model(model, output_format):
    renderer = RENDERERS.get(output_format)
    if renderer is None:
        raise ReportError(
            "Unsupported report format: %s. Use one of: %s"
            % (output_format, ", ".join(RENDERERS))
        )
    return renderer(model)
