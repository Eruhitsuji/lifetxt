"""Shared, surface-neutral semantic helper for the `progress:` detail key
(#646, first slice of the #645 parent contract): percentage (`75%`) and
fraction (`3/10`) parsing and validation.

This is the single source of truth every surface (validator, CLI, Query,
TUI, Web) must reuse rather than re-implementing its own `progress:`
parser -- see `.ai/project/RULES.md`'s design principle against
surface-specific duplicate parsers.

Two representations are accepted in this first slice:

    percentage:  ``0%`` .. ``100%``, integer or a finite decimal
                 (``33.3%``); out of range is rejected.
    fraction:    ``current/total`` with ``total > 0``, ``current >= 0``,
                 and ``current <= total``.

A bare, unitless number such as ``0.5`` is intentionally rejected: it is
ambiguous whether the author meant ``0.5%`` or ``50%``, and this project
does not guess. `status` and `progress` are deliberately independent --
this module never inspects or changes an item's status, and no automatic
`progress:100% -> [x]` (or the reverse) sync happens anywhere in lifetxt.

`raw` is always preserved verbatim on `ProgressValue` -- callers must
serialize `progress:` using the author's own original text (`3/5`, not a
derived `60%`), never silently converting between the two forms.
"""

from __future__ import unicode_literals

import re
from collections import namedtuple

_PERCENT_RE = re.compile(r"^(-?\d+(?:\.\d+)?)%$")
_FRACTION_RE = re.compile(r"^(-?\d+)/(-?\d+)$")


class ProgressValueError(ValueError):
    """Raised by `parse_progress` for an invalid `progress:` value.

    `reason` is a short, stable, English machine string (no trailing
    period) describing what is wrong; callers such as the validator
    build their own full diagnostic message and hint around it rather
    than parsing this exception's text.
    """

    def __init__(self, reason):
        super(ProgressValueError, self).__init__(reason)
        self.reason = reason


#: `raw` is the exact original text (never regenerated); `kind` is
#: `"percentage"` or `"fraction"`; `current`/`total` are `None` for a
#: percentage; `percent`/`ratio` are always populated as derived,
#: normalized values (`0.0`-`100.0` and `0.0`-`1.0` respectively).
ProgressValue = namedtuple(
    "ProgressValue", ("raw", "kind", "current", "total", "percent", "ratio")
)


def parse_progress(raw):
    """Parse `raw` (the exact text that followed `progress:`) into a
    `ProgressValue`.

    Raises `ProgressValueError` for anything that is not a valid
    percentage or fraction by this module's own rules -- including a
    bare unitless number, a negative or out-of-range percentage, a
    fraction with `total <= 0`, a negative `current`, or `current` above
    `total`. Never raises for any other reason (a malformed string that
    matches neither pattern also raises this same exception type).
    """
    text = str(raw).strip()

    percent_match = _PERCENT_RE.match(text)
    if percent_match:
        value = float(percent_match.group(1))
        if value < 0 or value > 100:
            raise ProgressValueError(
                "percentage %s%% is out of range (must be 0-100)"
                % percent_match.group(1)
            )
        return ProgressValue(text, "percentage", None, None, value, value / 100.0)

    fraction_match = _FRACTION_RE.match(text)
    if fraction_match:
        current = int(fraction_match.group(1))
        total = int(fraction_match.group(2))
        if total <= 0:
            raise ProgressValueError("fraction total %d must be greater than 0" % total)
        if current < 0:
            raise ProgressValueError(
                "fraction current %d must not be negative" % current
            )
        if current > total:
            raise ProgressValueError(
                "fraction current %d must not exceed total %d" % (current, total)
            )
        ratio = current / float(total)
        return ProgressValue(text, "fraction", current, total, ratio * 100.0, ratio)

    raise ProgressValueError(
        "%r is not a valid progress value; use a percentage such as 75%% "
        "or a fraction such as 3/5" % text
    )


def is_valid_progress(raw):
    """`True` when `raw` parses cleanly, without raising."""
    try:
        parse_progress(raw)
    except ProgressValueError:
        return False
    return True
