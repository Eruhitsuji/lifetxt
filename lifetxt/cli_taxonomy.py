"""Command taxonomy metadata for role-based `--help`, progressive-disclosure
beginner help, and the machine-readable `lifetxt help --json` surface (#629).

Design constraint from the issue: reuse existing sources of truth instead of
hand-duplicating a second command registry. The real, authoritative list of
command names always comes from :func:`lifetxt.cli.build_parser`'s subparser
tree plus the well-known extended-command sets already defined in
`lifetxt/entrypoint.py` (``_EXTRA_COMMANDS``, ``_PERSONAL_CONTEXT_COMMANDS``,
and the two specially-routed ``report``/``server-report`` commands) --
:func:`all_commands` derives this at runtime and is never a hardcoded list.

``CATEGORIES``, ``AUDIENCES``, and the safety/example/related-command
metadata below are the only genuinely new data this module adds: pure UX
information (grouping, audience flow, copyable examples) that has no
existing authoritative source elsewhere in the codebase. ``WRITE_COMMANDS``
and ``DESTRUCTIVE_COMMANDS`` are a best-effort classification for human/AI
guidance -- not an enforcement mechanism. The actual permission boundary for
untrusted AI clients remains MCP's ``--profile read|assist|full`` (#502).

Every command name used anywhere in this module is checked by
``tests/test_cli_taxonomy.py`` against the real, runtime-derived command set:
a command added to the CLI without a matching taxonomy entry fails that test
rather than silently falling through to "uncategorized" in production.
"""

from __future__ import unicode_literals

import json
from collections import OrderedDict


#: Cache of `cli.build_parser()` itself (not just its subparser map), because
#: this module also needs each subcommand's `help=` text off the raw
#: `_SubParsersAction` pseudo-actions, which `lifetxt.completion`'s own
#: `_subparser_map()` cache does not expose. Built at most once per process.
_PARSER_CACHE = {}


def _build_parser_cached():
    if "parser" not in _PARSER_CACHE:
        from .cli import build_parser

        _PARSER_CACHE["parser"] = build_parser()
    return _PARSER_CACHE["parser"]


def _subparsers_action():
    parser = _build_parser_cached()
    for action in parser._actions:
        if action.__class__.__name__ == "_SubParsersAction":
            return action
    return None


def _canonical_names_and_aliases():
    """``{canonical_name: (alias, ...)}`` for every `build_parser` subcommand.

    argparse's `_SubParsersAction.choices` contains one entry per alias too,
    all pointing at the identical subparser object, so aliases are recovered
    by grouping choices by parser identity and picking the one name whose
    value matches that subparser's own `prog` (the name `add_parser` was
    actually given, never an alias).
    """
    action = _subparsers_action()
    if action is None:
        return {}
    by_identity = {}
    for name, subparser in action.choices.items():
        by_identity.setdefault(id(subparser), []).append(name)
    result = {}
    for names in by_identity.values():
        subparser = action.choices[names[0]]
        prog_last = subparser.prog.rsplit(" ", 1)[-1]
        canonical = prog_last if prog_last in names else sorted(names, key=len)[-1]
        result[canonical] = tuple(n for n in names if n != canonical)
    return result


def _parser_command_help():
    """``{canonical_name: help_text}`` from the subparsers' own `help=` text.

    This is the text argparse itself renders in the flat `--help` listing --
    a more complete source than `lifetxt.completion._command_help`, which
    reads `.description` and is blank for most subcommands here.
    """
    action = _subparsers_action()
    if action is None:
        return {}
    canonical_by_alias_target = {}
    for canonical, aliases in _canonical_names_and_aliases().items():
        canonical_by_alias_target[canonical] = canonical
        for alias in aliases:
            canonical_by_alias_target[alias] = canonical
    result = {}
    for pseudo in getattr(action, "_choices_actions", ()):
        canonical = canonical_by_alias_target.get(pseudo.dest, pseudo.dest)
        if canonical not in result:
            result[canonical] = (pseudo.help or "").strip()
    return result


#: Manual one-line summaries for commands dispatched outside
#: `cli.build_parser()` (extended commands, Personal Context, report,
#: server-report), which have no argparse subparser of their own to read a
#: `help=` string from.
_EXTRA_SUMMARIES = {
    "tour": "Zero-config, dependency-free 30-second demonstration of what "
    "lifetxt derives from a sample life.txt. Writes nothing.",
    "help": "Progressive-disclosure, goal-based, and machine-readable help: "
    "audience guides, one-command lookups, and a JSON capability catalog.",
    "next": "List actionable next steps: open tasks and habits that are not "
    "blocked, someday-tagged, or otherwise deferred.",
    "show": "Show one item's full detail by ID.",
    "edit": "Open an item in $EDITOR through a safe temporary-copy "
    "review-and-apply flow.",
    "path": "Report the resolved life.txt, config, and workspace paths "
    "lifetxt would use.",
    "count": "Count items grouped by status, type, tag, person, project, "
    "context, or assignee.",
    "invoice": "Summarize tracked time as a billable invoice for a date range.",
    "standup": "Generate a daily standup summary: done yesterday, doing "
    "today, blockers.",
    "to-ics": "Export life.txt events to an iCalendar (.ics) file.",
    "from-todo": "Convert a plain todo.txt-style file to life.txt items.",
    "safety": "Release-safety and recovery administration: locks, "
    "transactions, timezone, revisions, write-routes, release-gate.",
    "format": "Inspect or migrate a life.txt file's Format version: info, "
    "check, canon, migrate, downgrade, schemas.",
    "capabilities": "Report which operations this build supports across "
    "CLI, Web, and MCP.",
    "attachment": "Attach, reference, delete, or inspect file: and dir: attachments.",
    "context": "Deterministic Personal Context views: health, why, and capsule.",
    "memory": "Stage a reviewable correction to a Personal AI Memory "
    "record through Unified Inbox.",
    "decisions": "List recorded decisions (tag:decision items).",
    "report": "Run or preview a named periodic Markdown/JSON/HTML report profile.",
    "server-report": "Install, remove, or plan a scheduled report job on "
    "an already-running server deployment.",
}


def all_commands():
    """Every real top-level command name, derived at runtime.

    Union of `cli.build_parser()`'s canonical subcommand names,
    `entrypoint._EXTRA_COMMANDS`, `entrypoint._PERSONAL_CONTEXT_COMMANDS`,
    and the two specially-routed `report`/`server-report` names -- never a
    hand-copied list, so this can't drift from what `lifetxt` actually runs.
    """
    from .entrypoint import _EXTRA_COMMANDS, _PERSONAL_CONTEXT_COMMANDS

    names = set(_canonical_names_and_aliases())
    names |= set(_EXTRA_COMMANDS)
    names |= set(_PERSONAL_CONTEXT_COMMANDS)
    names |= {"report", "server-report"}
    return tuple(sorted(names))


def command_aliases(name):
    return _canonical_names_and_aliases().get(name, ())


def command_summary(name):
    text = _parser_command_help().get(name)
    if text:
        return text
    text = _EXTRA_SUMMARIES.get(name)
    if text:
        return text
    return name


def command_arguments(name):
    """Top-level positional argument names for a `build_parser` command.

    Empty for commands dispatched outside `build_parser` (extended
    commands build their own throwaway parser per invocation with no
    stable object to introspect ahead of time; some of them also inject
    routing-only marker flags such as `review --someday` that would be
    misleading to surface here as ordinary arguments).
    """
    action = _subparsers_action()
    if action is None:
        return ()
    subparser = action.choices.get(name)
    if subparser is None:
        return ()
    names = []
    for sub_action in subparser._actions:
        if sub_action.option_strings:
            continue
        if sub_action.__class__.__name__ == "_SubParsersAction":
            continue
        names.append(sub_action.dest)
    return tuple(names)


def command_options(name):
    """Long options for a `build_parser` command, including nested
    subcommands. Empty for extended/Personal-Context/report commands, for
    the same reason as :func:`command_arguments`."""
    if name not in _canonical_names_and_aliases():
        return ()
    from . import completion

    return completion._command_options(name)


#: Category order matters: this is the order rendered in `--help` and in
#: the JSON catalog, going from the smallest daily surface to the least
#: commonly needed one.
CATEGORIES = OrderedDict(
    (
        (
            "daily",
            {
                "title": "Getting Started / Daily",
                "description": "The commands most people use most days.",
                "commands": (
                    "tour",
                    "help",
                    "init",
                    "quick",
                    "today",
                    "next",
                    "agenda",
                    "show",
                    "edit",
                    "done",
                    "complete",
                    "review",
                    "assist",
                    "state",
                    "start",
                    "stop",
                    "assign",
                    "timer",
                    "notify",
                ),
            },
        ),
        (
            "query",
            {
                "title": "Query / Explore",
                "description": "Read-only ways to filter, search, and "
                "summarize your data.",
                "commands": (
                    "filter",
                    "search",
                    "find",
                    "query",
                    "view",
                    "summary",
                    "inbox",
                    "health",
                    "temporal",
                    "count",
                    "status",
                ),
            },
        ),
        (
            "collab",
            {
                "title": "Projects / People / Collaboration",
                "description": "Projects, people, groups, messages, "
                "proposals, and development tickets.",
                "commands": (
                    "project",
                    "portfolio",
                    "area",
                    "person",
                    "group",
                    "who",
                    "message",
                    "proposal",
                    "ticket",
                    "version",
                    "sprint",
                ),
            },
        ),
        (
            "structure",
            {
                "title": "Structure / Data Integrity",
                "description": "Inspect and validate the shape of your "
                "data: ids, links, and style.",
                "commands": (
                    "check",
                    "integrity",
                    "ids",
                    "links",
                    "backlinks",
                    "sources",
                    "tag",
                    "lint",
                    "deps",
                    "diff",
                    "snapshot",
                    "undo",
                    "cleanup",
                    "files",
                ),
            },
        ),
        (
            "import_export",
            {
                "title": "Import / Export / Reports",
                "description": "Move data in and out of life.txt, and "
                "generate reports.",
                "commands": (
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
                    "markdown",
                    "stats",
                    "plot",
                    "export-heatmap",
                    "standup",
                    "invoice",
                    "share",
                    "digest",
                    "report",
                ),
            },
        ),
        (
            "interfaces",
            {
                "title": "Interfaces / Integration",
                "description": "Other ways to use lifetxt: terminal UI, "
                "browser, AI clients.",
                "commands": (
                    "tui",
                    "fzf",
                    "web",
                    "serve",
                    "mcp",
                    "ai",
                    "completion",
                    "git-hook",
                    "watch",
                    "remote",
                ),
            },
        ),
        (
            "workspace_config",
            {
                "title": "Workspace / Configuration / Safety",
                "description": "Configuration, named workspaces, "
                "diagnostics, Format, and deployment administration.",
                "commands": (
                    "config",
                    "workspace",
                    "path",
                    "doctor",
                    "format",
                    "safety",
                    "capabilities",
                    "attachment",
                    "update",
                    "update-check",
                    "server-init",
                    "server-update",
                    "server-report",
                ),
            },
        ),
        (
            "personal_context",
            {
                "title": "Personal Context",
                "description": "Deterministic views over your own "
                "recorded preferences and decisions.",
                "commands": ("context", "memory", "decisions"),
            },
        ),
        (
            "advanced",
            {
                "title": "Advanced / Experimental",
                "description": "Less commonly needed tools, bulk "
                "operations, and the opt-in experimental VM.",
                "commands": (
                    "archive",
                    "batch",
                    "encrypt",
                    "decrypt",
                    "migrate",
                    "template",
                    "demo",
                    "vm",
                    "rrule",
                ),
            },
        ),
    )
)


def command_category(name):
    for category_id, category in CATEGORIES.items():
        if name in category["commands"]:
            return category_id
    return None


#: Best-effort classification of whether invoking a command can mutate
#: life.txt, configuration, or deployment state. Not a security boundary --
#: MCP's `--profile` (#502) is. `serve`/`web`/`mcp`/`tui`/`fzf`/`remote` are
#: listed here because they are interactive/write-capable surfaces by
#: default; their actual write capability depends on flags or profile.
WRITE_COMMANDS = frozenset(
    (
        "init",
        "quick",
        "edit",
        "done",
        "complete",
        "assist",
        "state",
        "start",
        "stop",
        "assign",
        "timer",
        "project",
        "message",
        "proposal",
        "ticket",
        "version",
        "sprint",
        "integrity",
        "tag",
        "undo",
        "import",
        "import-ics",
        "sync-ics",
        "from-json",
        "from-jsonl",
        "from-csv",
        "from-markdown",
        "from-todo",
        "tui",
        "fzf",
        "web",
        "serve",
        "mcp",
        "git-hook",
        "remote",
        "completion",
        "config",
        "format",
        "safety",
        "attachment",
        "update",
        "server-init",
        "server-update",
        "server-report",
        "memory",
        "archive",
        "batch",
        "encrypt",
        "decrypt",
        "migrate",
        "template",
        "demo",
    )
)

#: Higher blast-radius subset of WRITE_COMMANDS: rewrites file format,
#: mutates the running git install or a production deployment, applies
#: bulk changes across files, or would lose data if misused.
DESTRUCTIVE_COMMANDS = frozenset(
    (
        "archive",
        "migrate",
        "encrypt",
        "decrypt",
        "undo",
        "update",
        "server-update",
        "server-init",
        "format",
        "batch",
    )
)


def command_safety(name):
    is_write = name in WRITE_COMMANDS
    return OrderedDict(
        (
            ("read_only", not is_write),
            ("destructive", name in DESTRUCTIVE_COMMANDS),
        )
    )


#: Curated copyable examples for the commands most likely to be looked up
#: through `lifetxt help`. Commands without an entry here report an empty
#: `examples` list rather than a guessed one.
_EXAMPLES = {
    "tour": ("lifetxt tour",),
    "init": ("lifetxt init",),
    "quick": ('lifetxt add "Buy milk"',),
    "today": ("lifetxt today",),
    "next": ("lifetxt next",),
    "agenda": ("lifetxt agenda --window 1w",),
    "show": ("lifetxt show ID",),
    "edit": ("lifetxt edit ID",),
    "done": ("lifetxt done ID",),
    "complete": ("lifetxt complete ID",),
    "review": ("lifetxt review --last-week",),
    "search": ('lifetxt search "milk"',),
    "find": ('lifetxt find "milk"',),
    "query": ('lifetxt query "project:home status:open"',),
    "view": ("lifetxt view list",),
    "project": ("lifetxt project list",),
    "workspace": ("lifetxt workspace list",),
    "links": ("lifetxt links",),
    "check": ("lifetxt check life.txt",),
    "integrity": ("lifetxt integrity",),
    "ai": ("lifetxt ai setup generic",),
    "mcp": ("lifetxt mcp --profile read",),
    "context": ("lifetxt context health",),
    "safety": ("lifetxt safety release-gate",),
    "format": ("lifetxt format info life.txt",),
    "capabilities": ("lifetxt capabilities",),
    "doctor": ("lifetxt doctor",),
    "web": ("lifetxt web",),
    "tui": ("lifetxt tui",),
}

#: Curated related-command overrides for a few high-traffic commands, so
#: the beginner flow (`add` -> `today`/`show`/`done`) matches exactly. Every
#: other command falls back to up to four same-category siblings.
_RELATED_OVERRIDES = {
    "quick": ("today", "show", "done"),
    "today": ("next", "review", "quick"),
    "next": ("today", "done", "show"),
    "done": ("today", "complete", "undo"),
}


def related_commands(name):
    if name in _RELATED_OVERRIDES:
        return tuple(cmd for cmd in _RELATED_OVERRIDES[name] if cmd != name)
    category_id = command_category(name)
    if category_id is None:
        return ()
    siblings = [c for c in CATEGORIES[category_id]["commands"] if c != name]
    return tuple(siblings[:4])


#: The beginner-to-daily-to-advanced audience flows described in the issue.
#: Each entry is a fixed, small, curated sequence -- not the full category
#: listing -- so `lifetxt help <audience>` stays a short, readable path
#: rather than a second dump of every command.
AUDIENCES = OrderedDict(
    (
        (
            "beginner",
            {
                "title": "Beginner",
                "description": "Never used lifetxt before? Start here.",
                "flow": (
                    (
                        "tour",
                        "see what lifetxt can do, with zero setup",
                        "lifetxt tour",
                    ),
                    ("init", "create your life.txt", "lifetxt init"),
                    (
                        "quick",
                        "capture your first task",
                        'lifetxt add "Buy milk"',
                    ),
                    (
                        "today",
                        "see what needs attention today",
                        "lifetxt today",
                    ),
                    ("done", "mark a task finished", "lifetxt done ID"),
                ),
            },
        ),
        (
            "daily",
            {
                "title": "Daily user",
                "description": "The loop most days look like once you're set up.",
                "flow": (
                    (
                        "quick",
                        "capture something new",
                        'lifetxt add "Call the dentist"',
                    ),
                    ("today", "see what's due or overdue", "lifetxt today"),
                    (
                        "next",
                        "pick the next actionable task",
                        "lifetxt next",
                    ),
                    ("show", "look at one item's full detail", "lifetxt show ID"),
                    ("edit", "change it in your editor", "lifetxt edit ID"),
                    (
                        "review",
                        "look back at the week",
                        "lifetxt review --last-week",
                    ),
                ),
            },
        ),
        (
            "power",
            {
                "title": "Power user",
                "description": "Query, saved views, projects, workspaces, "
                "and the reference graph.",
                "flow": (
                    (
                        "query",
                        "filter with the shared query language",
                        'lifetxt query "project:home status:open"',
                    ),
                    ("view", "save and re-run a query", "lifetxt view list"),
                    (
                        "project",
                        "manage work by project",
                        "lifetxt project list",
                    ),
                    (
                        "workspace",
                        "inspect a named multi-file workspace",
                        "lifetxt workspace list",
                    ),
                    (
                        "links",
                        "follow id-based references",
                        "lifetxt links",
                    ),
                ),
            },
        ),
        (
            "ai",
            {
                "title": "AI user",
                "description": "Connect an AI client to your workspace safely.",
                "flow": (
                    (
                        "mcp",
                        "run the MCP server for an AI client",
                        "lifetxt mcp --profile read",
                    ),
                    (
                        "ai",
                        "generate the client configuration",
                        "lifetxt ai setup generic",
                    ),
                    (
                        "context",
                        "let it query your Personal Context",
                        "lifetxt context health",
                    ),
                ),
            },
        ),
        (
            "admin",
            {
                "title": "Administration / development",
                "description": "Diagnostics, recovery, Format, and "
                "cross-surface capability checks.",
                "flow": (
                    (
                        "integrity",
                        "run a read-only data-integrity report",
                        "lifetxt integrity",
                    ),
                    (
                        "safety",
                        "inspect recovery and release-safety state",
                        "lifetxt safety release-gate",
                    ),
                    (
                        "format",
                        "check or migrate the life.txt Format version",
                        "lifetxt format info life.txt",
                    ),
                    (
                        "capabilities",
                        "see what this build supports",
                        "lifetxt capabilities",
                    ),
                ),
            },
        ),
    )
)


def command_record(name, detailed=False):
    """One command's metadata, shaped for both text rendering and JSON.

    `detailed=True` (used for `lifetxt help <command>`) adds
    `arguments`/`options`/`examples`; the lean form (used inside the full
    catalog) omits them to keep `lifetxt help --json` a reasonable size.
    """
    safety = command_safety(name)
    record = OrderedDict(
        (
            ("command", name),
            ("aliases", list(command_aliases(name))),
            ("category", command_category(name)),
            ("summary", command_summary(name)),
            ("related_commands", list(related_commands(name))),
            ("read_only", safety["read_only"]),
            ("destructive", safety["destructive"]),
        )
    )
    if detailed:
        record["arguments"] = list(command_arguments(name))
        record["options"] = list(command_options(name))
        record["examples"] = list(_EXAMPLES.get(name, ()))
    return record


def catalog_payload():
    categories = [
        OrderedDict(
            (
                ("id", category_id),
                ("title", category["title"]),
                ("description", category["description"]),
                ("commands", list(category["commands"])),
            )
        )
        for category_id, category in CATEGORIES.items()
    ]
    commands = [command_record(name) for name in all_commands()]
    return OrderedDict(
        (
            ("schema", "lifetxt-help-catalog-v1"),
            ("categories", categories),
            ("audiences", list(AUDIENCES.keys())),
            ("commands", commands),
        )
    )


def audience_payload(audience_id):
    audience = AUDIENCES[audience_id]
    flow = [
        OrderedDict(
            (
                ("step", index + 1),
                ("command", command),
                ("goal", goal),
                ("example", example),
            )
        )
        for index, (command, goal, example) in enumerate(audience["flow"])
    ]
    return OrderedDict(
        (
            ("schema", "lifetxt-help-audience-v1"),
            ("audience", audience_id),
            ("title", audience["title"]),
            ("description", audience["description"]),
            ("flow", flow),
        )
    )


def _dumps(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def render_catalog_json():
    return _dumps(catalog_payload())


def render_command_json(name):
    return _dumps(command_record(name, detailed=True))


def render_audience_json(audience_id):
    return _dumps(audience_payload(audience_id))


def render_category_overview_lines():
    """Compact per-category command listing, one line per category.

    Shared by both `lifetxt --help`'s prefix block and `lifetxt help`'s
    plain-text overview, so the two can't independently drift.
    """
    lines = []
    for category in CATEGORIES.values():
        commands = ", ".join(category["commands"])
        lines.append("  %s:" % category["title"])
        lines.append("    %s" % commands)
    return lines


def render_top_level_help_prefix():
    """The "Start here" + category index block prepended to `lifetxt --help`.

    Purely additive: the full flat argparse help that follows is unchanged,
    so every existing `--help` consumer keeps seeing everything it already
    saw, just with this discoverability block ahead of it.
    """
    lines = [
        "Start here:",
        "  lifetxt tour              explore a working example, no setup required",
        "  lifetxt init              create life.txt and .lifetxt.json",
        '  lifetxt add "..."         capture your first task',
        "  lifetxt today             see what needs attention today",
        "  lifetxt done ID           mark it done",
        "",
        "New here? Try: lifetxt help beginner",
        "Command categories (full flag reference follows below):",
    ]
    lines.extend(render_category_overview_lines())
    lines.append("")
    lines.append("Guided paths: lifetxt help [beginner|daily|power|ai|admin]")
    lines.append("Machine-readable: lifetxt help --json, lifetxt help <command> --json")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_help_overview_text():
    lines = [
        "lifetxt help",
        "",
        "Start here:",
        "  lifetxt tour              explore a working example, no setup required",
        "  lifetxt init              create life.txt and .lifetxt.json",
        '  lifetxt add "..."         capture your first task',
        "  lifetxt today             see what needs attention today",
        "  lifetxt done ID           mark it done",
        "",
        "Guided paths:",
    ]
    for audience_id, audience in AUDIENCES.items():
        lines.append("  lifetxt help %-9s %s" % (audience_id, audience["description"]))
    lines.append("")
    lines.append("Command categories:")
    lines.extend(render_category_overview_lines())
    lines.append("")
    lines.append("Look up one command: lifetxt help <command>")
    lines.append(
        "Machine-readable: lifetxt help --json, lifetxt help <command> --json, "
        "lifetxt help <audience> --json"
    )
    lines.append("Full flag reference: lifetxt --help, lifetxt <command> --help")
    return "\n".join(lines) + "\n"


def render_audience_text(audience_id):
    audience = AUDIENCES[audience_id]
    lines = [
        "lifetxt help %s -- %s" % (audience_id, audience["title"]),
        "",
        audience["description"],
        "",
    ]
    for index, (command, goal, example) in enumerate(audience["flow"]):
        lines.append("  %d. %-28s %s" % (index + 1, example, goal))
    lines.append("")
    lines.append("Look up any of these commands: lifetxt help <command>")
    lines.append("Full flag reference: lifetxt <command> --help")
    return "\n".join(lines) + "\n"


def render_command_text(name):
    record = command_record(name, detailed=True)
    category_id = record["category"]
    category_title = (
        CATEGORIES[category_id]["title"] if category_id else "(uncategorized)"
    )
    lines = [
        "lifetxt help %s" % name,
        "",
        record["summary"],
        "",
        "Category: %s" % category_title,
        "Aliases: %s" % (", ".join(record["aliases"]) or "none"),
        "Read-only: %s   Destructive: %s"
        % (
            "yes" if record["read_only"] else "no",
            "yes" if record["destructive"] else "no",
        ),
    ]
    if record["examples"]:
        lines.append("Example:")
        for example in record["examples"]:
            lines.append("  %s" % example)
    if record["related_commands"]:
        lines.append("Related: %s" % ", ".join(record["related_commands"]))
    lines.append("")
    lines.append("Full reference: lifetxt %s --help" % name)
    return "\n".join(lines) + "\n"


def resolve_topic(topic):
    """Canonicalize a `lifetxt help TOPIC` argument.

    Returns `("audience", audience_id)`, `("command", canonical_name)`, or
    raises `ValueError` naming the valid audiences/commands when `topic`
    matches neither. Aliases (`add`, `q`, `d`, ...) resolve to their
    canonical command.
    """
    if topic in AUDIENCES:
        return "audience", topic
    if topic in all_commands():
        # `all_commands()` is keyed by canonical name only (see above).
        return "command", topic
    for canonical, alias_tuple in _canonical_names_and_aliases().items():
        if topic in alias_tuple:
            return "command", canonical
    raise ValueError(
        "Unknown help topic: %r. Known audiences: %s. "
        "Run `lifetxt help` for the full list of commands."
        % (topic, ", ".join(AUDIENCES.keys()))
    )


def command_help(args, config_data):
    """CLI entry point dispatched from `lifetxt/extra_cli.py`."""
    from .extra_common import _write_output

    topic = getattr(args, "topic", None)
    as_json = (
        bool(getattr(args, "json", False)) or getattr(args, "format", "text") == "json"
    )

    if topic is None:
        text = render_catalog_json() if as_json else render_help_overview_text()
        _write_output(text, getattr(args, "output", None))
        return 0

    kind, resolved = resolve_topic(topic)
    if kind == "audience":
        text = (
            render_audience_json(resolved)
            if as_json
            else render_audience_text(resolved)
        )
    else:
        text = (
            render_command_json(resolved) if as_json else render_command_text(resolved)
        )
    _write_output(text, getattr(args, "output", None))
    return 0
