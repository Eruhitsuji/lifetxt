"""TTY-only actionable guidance for a bounded set of common CLI-level
errors (#643): an unknown top-level command, a missing global option
value (`--config`/`--workspace`/`--lang`), an unknown workspace, an
unreadable or malformed configuration file, and a missing/unreadable
input path.

Every render function here always returns the exact, unchanged
"ERROR: <message>\n" line every one of these errors already produced --
scripts and redirected output see byte-identical behavior to before this
module existed. Additional "Did you mean?"/"Available:"/"Try:" guidance
is appended only when stderr is a real interactive terminal
(`sys.stderr.isatty()`), matching this project's other TTY-gated
features (#636, #638). Nothing here changes an exit code, and nothing
here invents a candidate that is not already a real, currently valid
command/workspace name -- an unknown command's candidates come from
`lifetxt.cli_taxonomy.all_commands()` (the same runtime-derived registry
#629 already established, never a second hand-copied list), and an
unknown workspace's candidates come from the exact "Available: ..." list
`lifetxt.workspace.resolve_workspace()` already computed and raised.
"""

from __future__ import unicode_literals

import difflib
import re
import sys

_MAX_SUGGESTIONS = 3
_CLOSE_MATCH_CUTOFF = 0.6

_UNKNOWN_WORKSPACE_RE = re.compile(r"^Unknown workspace '(.*)'\. Available: (.*)$")
_MISSING_OPTION_VALUE_RE = re.compile(r"^(--\S+) requires a (.+)\.$")


def _is_tty():
    try:
        return bool(sys.stderr.isatty())
    except (AttributeError, ValueError):
        return False


def _close_matches(value, candidates):
    if not value:
        return []
    universe = sorted(c for c in candidates if c and c != value)
    return difflib.get_close_matches(
        value, universe, n=_MAX_SUGGESTIONS, cutoff=_CLOSE_MATCH_CUTOFF
    )


def _did_you_mean_lines(candidates):
    if not candidates:
        return []
    if len(candidates) == 1:
        return ["Did you mean %r?" % candidates[0]]
    lines = ["Did you mean one of:"]
    lines.extend("  %s" % candidate for candidate in candidates)
    return lines


def unknown_command_text(command):
    """Render the full stderr text for a top-level command lookup
    failure (`command` matched no real command or alias)."""
    lines = ["ERROR: Unknown command: %r" % command]
    if _is_tty():
        from . import cli_taxonomy

        candidates = _close_matches(command, cli_taxonomy.all_commands())
        lines.append("")
        lines.extend(_did_you_mean_lines(candidates))
        if candidates:
            lines.append("")
        lines.append("See:")
        lines.append("  lifetxt help beginner")
    return "\n".join(lines) + "\n"


def render_value_error_text(exc):
    """Render the full stderr text for a `ValueError` raised by CLI
    argument/config/workspace resolution."""
    message = str(exc)
    lines = ["ERROR: %s" % message]
    if not _is_tty():
        return "\n".join(lines) + "\n"

    workspace_match = _UNKNOWN_WORKSPACE_RE.match(message)
    if workspace_match:
        name, available_text = workspace_match.group(1), workspace_match.group(2)
        available = [
            item.strip()
            for item in available_text.split(",")
            if item.strip() and item.strip() != "(none)"
        ]
        lines.append("")
        lines.extend(_did_you_mean_lines(_close_matches(name, available)))
        lines.append("")
        if available:
            lines.append("Available:")
            lines.extend("  %s" % item for item in available)
        else:
            lines.append("No workspaces are configured yet.")
        return "\n".join(lines) + "\n"

    if message.startswith("Could not read config:"):
        lines.append("")
        lines.append("Try:")
        lines.append("  lifetxt doctor")
        return "\n".join(lines) + "\n"

    option_match = _MISSING_OPTION_VALUE_RE.match(message)
    if option_match:
        option, value_kind = option_match.group(1), option_match.group(2)
        lines.append("")
        lines.append("Usage: %s %s" % (option, value_kind.upper()))
        return "\n".join(lines) + "\n"

    return "\n".join(lines) + "\n"


def render_os_error_text(exc):
    """Render the full stderr text for an `OSError` raised while
    resolving or reading a CLI input path."""
    lines = ["ERROR: %s" % exc]
    if not _is_tty():
        return "\n".join(lines) + "\n"
    filename = getattr(exc, "filename", None)
    if filename:
        lines.append("")
        lines.append("Could not read: %s" % filename)
        lines.append("Try:")
        lines.append("  Check that the path is correct.")
        lines.append("  Run `lifetxt path` to see the paths lifetxt would use.")
    return "\n".join(lines) + "\n"
