"""Per-CLI-command cross-surface capability matrix (#676).

Extends two existing registries rather than hand-maintaining a third
command/feature table:

- :mod:`lifetxt.cli_taxonomy` (#629) supplies the authoritative catalog of
  canonical CLI commands (:func:`lifetxt.cli_taxonomy.all_commands`).
  Aliases are never listed separately -- ``all_commands()`` already returns
  canonical names only, so an alias folds into its canonical command by
  construction.
- :mod:`lifetxt.surface_runtime` (#50) supplies ``OPERATION_REGISTRY``, the
  shared semantic operation registry already used by the CLI/Web/MCP
  capability drift gate.

This module adds only the smallest new data needed to answer "for CLI
command X, is equivalent functionality available on Web UI, TUI, the REST
API, and MCP": a curated mapping from a CLI command to the operation(s) it
corresponds to, and a curated set of commands that are intentionally
CLI-only (launchers, local administration, import/export converters) where
cross-surface parity is not expected by design.

Every other command -- anything not yet connected to either of those two
curated sets -- reports ``unmapped`` rather than guessing. This is
deliberately conservative: a wrong ``not_applicable`` or ``unsupported``
claim is worse than an honest "not yet connected to authoritative surface
metadata" for a command this module has not been taught about.

``OPERATION_REGISTRY``'s existing ``surfaces`` tuple only distinguishes
``cli``/``web``/``mcp`` -- ``web`` bundles the browser UI and the REST API
together, and there is no ``tui`` surface at all. Rather than duplicating
or restructuring that registry, this module adds two independently
computed columns (``web_ui`` and ``api``) that currently read the same
``"web" in spec["surfaces"]`` fact (a documented, known limitation -- see
the module docstring above), plus a small curated ``tui`` operation set.
This satisfies the "distinguish Web UI from REST API" requirement with the
minimum new model while remaining honest about what is and is not actually
independently verified today.

This is purely additive: it does not change ``OPERATION_REGISTRY``, does
not change the existing ``lifetxt capabilities`` remote-client capability
document, and does not introduce a second command catalog.
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .cli_taxonomy import all_commands, command_category
from .surface_runtime import OPERATION_REGISTRY

SCHEMA = "lifetxt-capability-matrix-v1"

#: Stable, small support-state enum (#676 requirement 3).
FULL = "full"
PARTIAL = "partial"
UNSUPPORTED = "unsupported"
NOT_APPLICABLE = "not_applicable"
UNMAPPED = "unmapped"

SUPPORT_STATES = (FULL, PARTIAL, UNSUPPORTED, NOT_APPLICABLE, UNMAPPED)

#: The four surface columns this matrix reports, in display order. ``cli``
#: itself is not a column: every row is, by construction, a real CLI
#: command, so a CLI column would be trivially ``full`` for every row.
SURFACES = ("web_ui", "tui", "api", "mcp")

#: Curated CLI-command -> operation-name mapping. A command absent from
#: this mapping is either genuinely CLI-only (see ``_NOT_APPLICABLE``) or
#: not yet connected to authoritative metadata (``unmapped``). Multiple
#: operations are recorded when a command's behavior is intentionally a
#: composite of more than one semantic operation (e.g. ``today`` reads both
#: the agenda and the actionable-next-step list), which is exactly the
#: case #676 asks to resolve deterministically into ``partial`` rather than
#: a hand-guessed score.
_COMMAND_OPERATIONS = OrderedDict(
    (
        ("quick", ("create",)),
        ("add", ("create",)),
        ("done", ("complete",)),
        ("complete", ("complete",)),
        ("reopen", ("complete",)),
        ("progress", ("update",)),
        ("due", ("update",)),
        ("clone", ("create",)),
        ("today", ("agenda", "next")),
        ("agenda", ("agenda",)),
        ("review", ("review",)),
        ("next", ("next",)),
        ("recent", ("next",)),
        ("timer", ("timer",)),
        ("message", ("message",)),
        ("presence", ("presence",)),
        ("links", ("links",)),
        ("attachment", ("attachments",)),
        ("capabilities", ("capabilities",)),
        ("query", ("query",)),
        ("filter", ("query",)),
        ("search", ("query",)),
        ("find", ("query",)),
    )
)

#: Commands that are intentionally CLI-only by design: interactive
#: launchers for another surface, local/host administration, local data
#: recovery, or file-format import/export converters. Cross-surface parity
#: is not expected for these, so they report ``not_applicable`` on every
#: column rather than ``unmapped`` (which would imply they are simply not
#: yet connected) or ``unsupported`` (which would imply a gap).
_NOT_APPLICABLE = frozenset(
    (
        # Interface launchers -- these commands *are* another surface, or
        # start a process that talks to one; asking whether "web" supports
        # the "web" launcher is not a meaningful question.
        "tui",
        "web",
        "serve",
        "mcp",
        "remote",
        "fzf",
        "completion",
        "git-hook",
        "watch",
        "ai",
        # Local/host administration and deployment.
        "config",
        "workspace",
        "path",
        "doctor",
        "format",
        "safety",
        "update",
        "update-check",
        "server-init",
        "server-update",
        "server-report",
        # Local onboarding/informational commands with no server-side
        # equivalent by design.
        "init",
        "tour",
        "help",
        # Bulk/local-recovery/experimental commands.
        "archive",
        "batch",
        "encrypt",
        "decrypt",
        "migrate",
        "template",
        "demo",
        "vm",
        "rrule",
        "undo",
        "cleanup",
        "snapshot",
        "diff",
        # File-format import/export converters: local file <-> life.txt,
        # with no Web UI/TUI/API/MCP equivalent by design.
        "import",
        "import-ics",
        "sync-ics",
        "to-json",
        "to-jsonl",
        "to-csv",
        "from-json",
        "from-jsonl",
        "from-csv",
        "from-markdown",
        "from-todo",
        "to-ics",
    )
)

#: Operations the interactive curses TUI supports today through its slash
#: commands and views, reusing the same domain mutation/read functions the
#: CLI and Web API call. ``attachments``, ``acknowledge``, ``snooze``, and
#: ``capabilities`` have no dedicated TUI command/view yet.
_TUI_OPERATIONS = frozenset(
    name
    for name in OPERATION_REGISTRY
    if name not in ("attachments", "acknowledge", "snooze", "capabilities")
)


def _op_supports_surface(operation_name, surface):
    spec = OPERATION_REGISTRY.get(operation_name)
    if spec is None:
        return False
    if surface in ("web_ui", "api"):
        return "web" in spec["surfaces"]
    if surface == "mcp":
        return "mcp" in spec["surfaces"]
    if surface == "tui":
        return operation_name in _TUI_OPERATIONS
    return False


def command_operations(name):
    """The operation(s) a canonical CLI command corresponds to, if known."""
    return _COMMAND_OPERATIONS.get(name, ())


def command_surface_states(name):
    """``OrderedDict`` of ``{surface: support_state}`` for one CLI command."""
    operations = command_operations(name)
    if not operations:
        state = NOT_APPLICABLE if name in _NOT_APPLICABLE else UNMAPPED
        return OrderedDict((surface, state) for surface in SURFACES)
    result = OrderedDict()
    for surface in SURFACES:
        supported = [_op_supports_surface(op, surface) for op in operations]
        if all(supported):
            result[surface] = FULL
        elif any(supported):
            result[surface] = PARTIAL
        else:
            result[surface] = UNSUPPORTED
    return result


def matrix_row(name):
    return OrderedDict(
        (
            ("command", name),
            ("category", command_category(name)),
            ("operations", list(command_operations(name))),
            ("surfaces", command_surface_states(name)),
        )
    )


def matrix_rows():
    """One row per canonical CLI command, in ``all_commands()`` order."""
    return [matrix_row(name) for name in all_commands()]


def matrix_payload():
    """Stable, versioned JSON-compatible capability matrix document."""
    return OrderedDict(
        (
            ("schema", SCHEMA),
            ("support_states", list(SUPPORT_STATES)),
            ("surfaces", list(SURFACES)),
            ("commands", matrix_rows()),
        )
    )


def render_matrix_text(rows=None):
    """Fixed-width human-readable table, matching #676's example shape."""
    if rows is None:
        rows = matrix_rows()
    header = ("Command", "Web UI", "TUI", "API", "MCP")
    widths = [len(h) for h in header]
    table_rows = []
    for row in rows:
        cells = [row["command"]] + [row["surfaces"][s] for s in SURFACES]
        table_rows.append(cells)
        for i, cell in enumerate(cells):
            widths[i] = max(widths[i], len(cell))
    lines = []

    def _format(cells):
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    lines.append(_format(list(header)))
    lines.append("-" * (sum(widths) + 2 * (len(widths) - 1)))
    for cells in table_rows:
        lines.append(_format(cells))
    return "\n".join(lines) + "\n"
