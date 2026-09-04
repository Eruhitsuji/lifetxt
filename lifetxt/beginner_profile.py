"""Beginner / Minimal Profile vocabulary (#558), reused as presentation
metadata for progressive-disclosure authoring surfaces (#634).

This module owns no Format, parser, or serializer semantics: every value
below is already documented, valid Format 1.0 syntax (see
docs/en/getting-started.md's Level 1/2 sections). It exists purely so an
authoring surface (first: the Web quick/new-item editor; later: TUI/assist)
can hide non-beginner type/status/detail-key options without each surface
inventing its own copy of "what counts as beginner" vocabulary.

Full Format capability is never removed: an authoring surface using this
module is expected to let a user reveal every option again (see
``docs/en/web.md``'s "Show advanced options" description), and must never
discard or rewrite a field this module does not list when it was already
present on an existing record.
"""

from __future__ import unicode_literals


#: Beginner Profile record types (docs/en/getting-started.md Level 1).
TYPES = ("T", "E", "N")

#: Beginner Profile status tokens (docs/en/getting-started.md Level 1).
STATUSES = ("[ ]", "[x]", "[N]")

#: Beginner Profile detail keys most commonly needed day to day
#: (docs/en/getting-started.md Level 1/2). Not exhaustive -- an authoring
#: surface may still accept any key; this list only decides what is shown
#: by default in beginner mode.
DETAIL_KEYS = ("due", "on", "from", "to", "project", "tag", "priority")


def beginner_profile_payload():
    """JSON-serializable presentation metadata for the Beginner Profile."""
    return {
        "types": list(TYPES),
        "statuses": list(STATUSES),
        "detail_keys": list(DETAIL_KEYS),
    }
