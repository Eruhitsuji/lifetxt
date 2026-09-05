"""Bounded, read-only "Did you mean?" suggestions for `check` diagnostics
(#640).

This module never mutates anything and never changes a diagnostic's
severity, code, exit-code semantics, or whether the parser/validator
considers a token invalid in the first place -- it only derives candidate
replacements *after* the fact, for a diagnostic the validator or parser has
already raised, and only for a small, explicitly supported set of codes.

Candidates always come from vocabulary that is already the single source
of truth elsewhere in this codebase (`lifetxt/model.py`'s
`VALID_STATUSES`/`STATUS_ALIASES`, `VALID_TYPES`/`TYPE_ALIASES`,
`KNOWN_KEYS`/`RECOMMENDED_KEYS_BY_TYPE`, and `STATUS_STATE_VALUES`) -- never
a second, hand-maintained typo registry. A diagnostic code with no
supported extractor, or a message that does not match the expected shape
(for example because a future change alters wording), safely yields no
suggestions rather than guessing.

Status and type tokens are short, closed enumerations where every member
differs from every other member by a single character inside a fixed
`[X]`/`X` shape; plain edit-distance scoring cannot tell those apart (see
this module's own tests), so those two families use canonical alias lookup
and case-insensitive exact matching instead of fuzzy matching. Detail keys
are a much larger, natural-language vocabulary, where bounded edit-distance
matching against the canonical known/recommended key set is the safer tool.
"""

from __future__ import unicode_literals

import difflib
import re

from .model import (
    KNOWN_KEYS,
    RECOMMENDED_KEYS_BY_TYPE,
    STATUS_ALIASES,
    STATUS_STATE_VALUES,
    TYPE_ALIASES,
    VALID_STATUSES,
    VALID_TYPES,
)

_KEY_CLOSE_MATCH_CUTOFF = 0.65
_STATE_CLOSE_MATCH_CUTOFF = 0.65
_MAX_SUGGESTIONS = 3

_INVALID_STATUS_RE = re.compile(r"^Invalid status '(.*)'\.$")
_INVALID_TYPE_RE = re.compile(r"^Invalid type '(.*)'\.")
_CUSTOM_KEY_RE = re.compile(
    r"^Detail key '(.*)' is custom for type (\S+); it will be preserved\.$"
)
_STATE_VALUE_RE = re.compile(r"^state: '(.*)' should usually be one of: .*\.$")


def _status_suggestions(raw):
    if len(raw) >= 2 and raw[0] == "[" and raw[-1] == "]":
        inner = raw[1:-1]
    else:
        inner = raw
    alias_hit = STATUS_ALIASES.get(inner.lower())
    if alias_hit and alias_hit != raw:
        return [alias_hit]
    matches = []
    for candidate in VALID_STATUSES:
        if candidate == raw:
            continue
        candidate_inner = candidate[1:-1] if len(candidate) >= 2 else candidate
        if candidate_inner.lower() == inner.lower():
            matches.append(candidate)
    return matches


def _type_suggestions(raw):
    alias_hit = TYPE_ALIASES.get(raw.lower())
    if alias_hit and alias_hit != raw:
        return [alias_hit]
    matches = [
        candidate
        for candidate in VALID_TYPES
        if candidate != raw and candidate.lower() == raw.lower()
    ]
    return matches


def _detail_key_suggestions(key, kind):
    candidates = set(KNOWN_KEYS) | set(RECOMMENDED_KEYS_BY_TYPE.get(kind, ()))
    candidates.discard(key)
    universe = sorted(candidates)
    return difflib.get_close_matches(
        key, universe, n=_MAX_SUGGESTIONS, cutoff=_KEY_CLOSE_MATCH_CUTOFF
    )


def _state_suggestions(value):
    for candidate in STATUS_STATE_VALUES:
        if candidate != value and candidate.lower() == value.lower():
            return [candidate]
    universe = sorted(c for c in STATUS_STATE_VALUES if c != value)
    return difflib.get_close_matches(
        value, universe, n=_MAX_SUGGESTIONS, cutoff=_STATE_CLOSE_MATCH_CUTOFF
    )


def suggestions_for_diagnostic(diagnostic):
    """Return a bounded, deterministic list of candidate replacement tokens
    for ``diagnostic``, or ``[]`` when no safe suggestion applies.

    The list is never forced down to exactly one candidate: an empty list
    means "no safe suggestion", a single-item list means "one confident
    candidate", and a multi-item list means "several plausible candidates,
    none preferred over the others".
    """
    code = str(getattr(diagnostic, "code", "") or "")
    message = str(getattr(diagnostic, "message", "") or "")

    if code in ("E003", "E101"):
        match = _INVALID_STATUS_RE.match(message)
        if match:
            return _status_suggestions(match.group(1))
    elif code in ("E005", "E102"):
        match = _INVALID_TYPE_RE.match(message)
        if match:
            return _type_suggestions(match.group(1))
    elif code == "W106":
        match = _CUSTOM_KEY_RE.match(message)
        if match:
            return _detail_key_suggestions(match.group(1), match.group(2))
    elif code == "W207":
        match = _STATE_VALUE_RE.match(message)
        if match:
            return _state_suggestions(match.group(1))

    return []
