"""Zero-config, dependency-free first-run tour (`lifetxt tour`, #590).

Builds a tiny, in-memory Beginner Profile sample -- never written to disk --
parses it with the real parser, and runs it through the real
:func:`lifetxt.command_center.command_center` engine (the same engine behind
`lifetxt today`) so the tour demonstrates actual derived lifetxt value
instead of reimplementing any due/agenda/business logic of its own. No file,
config, or workspace is created or modified. An injectable reference date
keeps the sample and its tests deterministic while remaining useful relative
to the real current date when run for real.
"""

from __future__ import unicode_literals

import datetime
import json
from collections import OrderedDict

from .command_center import command_center
from .parser import parse_text
from .timezone_policy import today as timezone_today


def build_tour_sample(reference_date):
    """Return ``(source_text, items)`` for the built-in sample.

    Uses only the Beginner / Minimal Profile vocabulary documented in
    docs/en/getting-started.md: ``T``/``E``/``N`` types, ``[ ]``/``[N]``
    statuses, and ``due``/``from``/``to`` time keys -- no advanced syntax
    before the first value demonstration. Anchored to ``reference_date`` so a
    real run shows a task due today and a meeting tomorrow.
    """
    tomorrow = reference_date + datetime.timedelta(days=1)
    source_text = (
        '[ ] T "Buy milk" due:%s\n'
        '[ ] E "Team meeting" from:%sT10:00 to:%sT10:30\n'
        '[N] N "Idea"\n'
    ) % (reference_date.isoformat(), tomorrow.isoformat(), tomorrow.isoformat())
    items, _diagnostics = parse_text(source_text)
    return source_text, items


def tour_report(reference_date=None):
    """Build the sample and run it through the real "today" engine.

    Returns ``(reference_date, source_text, report)``. ``report`` is exactly
    what :func:`lifetxt.command_center.command_center` returns for the
    sample -- no due/agenda/summary rule is reimplemented here, and nothing
    is written to disk (``command_center`` never writes).
    """
    if reference_date is None:
        reference_date = timezone_today()
    source_text, items = build_tour_sample(reference_date)
    report = command_center(items, {}, reference_date)
    return reference_date, source_text, report


def _bucket_lines(label, rows, limit=5):
    if not rows:
        return []
    lines = ["%s (%d):" % (label, len(rows))]
    for row in rows[:limit]:
        due = " due:%s" % row["due"] if row.get("due") else ""
        lines.append("  %s %s%s" % (row["status"], row["title"], due))
    if len(rows) > limit:
        lines.append("  ... and %d more" % (len(rows) - limit))
    return lines


def render_tour_text(reference_date, source_text, report):
    """The "lifetxt in 30 seconds" terminal presentation.

    A fourth, independent presentation of the shared ``command_center``
    result -- alongside the existing CLI ``today``, TUI Today view, and Web
    Today dashboard renderers -- not a second computation of it.
    """
    lines = ["lifetxt in 30 seconds", "", "1. A readable life record"]
    lines.extend(source_text.rstrip("\n").splitlines())
    lines.append("")
    lines.append(
        "2. What lifetxt can derive (a real `lifetxt today` run, for %s)"
        % reference_date.isoformat()
    )
    derived = []
    derived.extend(_bucket_lines("Due today", report["due_today"]))
    derived.extend(_bucket_lines("Overdue", report["overdue"]))
    derived.extend(_bucket_lines("Upcoming", report["upcoming"]))
    derived.extend(_bucket_lines("Next actions", report["next_actions"]))
    if not derived:
        derived = ["All clear -- nothing due, overdue, or upcoming in this sample."]
    lines.extend(derived)
    lines.append("")
    lines.append("Next")
    lines.append("  lifetxt init")
    lines.append('  lifetxt add "Buy milk ^tomorrow"')
    lines.append("  lifetxt today")
    lines.append("")
    lines.append("Docs: docs/en/getting-started.md")
    return "\n".join(lines) + "\n"


def render_tour_json(reference_date, source_text, report):
    payload = OrderedDict(
        (
            ("reference_date", reference_date.isoformat()),
            ("sample", source_text),
            ("today", report),
        )
    )
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def command_tour(args, config_data):
    """CLI entry point dispatched from `lifetxt/extra_cli.py`.

    Takes no life.txt path, config, or workspace input: the tour is
    intentionally self-contained so it works identically from a clean
    installed artifact with no existing user data.
    """
    from .extra_common import _write_output

    reference_date, source_text, report = tour_report()
    output_format = getattr(args, "format", "text") or "text"
    if output_format == "json":
        text = render_tour_json(reference_date, source_text, report)
    else:
        text = render_tour_text(reference_date, source_text, report)
    _write_output(text, getattr(args, "output", None))
    return 0
