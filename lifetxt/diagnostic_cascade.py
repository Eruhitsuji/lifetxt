"""Root-cause / secondary grouping for one narrow, evidenced cascading
diagnostic family (#642): repeated `E009`/`E010` "this does not look like a
detail" failures on the exact same source line.

This is presentation-only. It never mutates a `Diagnostic`, never changes
`check --format json`'s stable fields (grouping is derived entirely from
each diagnostic's existing `code`/`source`/`line`), never suppresses a
diagnostic from the filtered list, and never changes exit-code semantics.

Why `E009`/`E010` specifically, and why grouping by identical
`(source, line)` is safe evidence rather than a line-distance guess:
both codes are raised from exactly one place, `lifetxt/parser.py`'s
`_parse_detail()`, called only from `parse_line()`'s single per-line
detail-parsing loop. A line that already failed to parse one detail as
`key:value` keeps scanning the rest of that same line token by token in
the same degraded recovery state (see `_skip_token()`'s use in that
loop) -- so a second, third, ... `E009`/`E010` on the *exact same* line is
not a coincidence of proximity, it is the same loop invocation reporting
that it is still not looking at anything shaped like a detail. Two
diagnostics merely on nearby lines, of similar codes, or with similar
messages are deliberately never grouped by this module -- see the
project's own review notes on this issue for why those signals are
unsafe. A line carrying only one `E009`/`E010` (or none) forms no group;
neither does a line where two such diagnostics come from different
source files that happen to share a line number.
"""

from __future__ import unicode_literals

from collections import OrderedDict

#: The only diagnostic family this first slice groups. See the module
#: docstring for why these two codes specifically are safe to group by
#: shared (source, line) alone.
_CASCADE_CODES = frozenset(("E009", "E010"))


def classify_cascade_roles(diagnostics):
    """Classify each of `diagnostics` (already filtered, in display order)
    into a cascade role.

    Returns a dict keyed by `id(diagnostic)`:

    - a root diagnostic (the first `E009`/`E010` seen for its
      `(source, line)`, when at least one more follows it on the same
      line) maps to `("root", [secondary_diagnostic, ...])`
    - each later member of that same group maps to
      `("secondary", root_diagnostic)`
    - every other diagnostic (including a lone `E009`/`E010` with no
      partner on its line) is simply absent from the returned dict

    Never reorders or removes anything from `diagnostics`; the caller
    renders every diagnostic exactly as before and only additionally
    consults this mapping for a diagnostic's role.
    """
    groups = OrderedDict()
    for diagnostic in diagnostics:
        code = str(getattr(diagnostic, "code", "") or "").upper()
        if code not in _CASCADE_CODES:
            continue
        key = (getattr(diagnostic, "source", None), getattr(diagnostic, "line", None))
        groups.setdefault(key, []).append(diagnostic)

    roles = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        root = members[0]
        secondaries = members[1:]
        roles[id(root)] = ("root", secondaries)
        for secondary in secondaries:
            roles[id(secondary)] = ("secondary", root)
    return roles
