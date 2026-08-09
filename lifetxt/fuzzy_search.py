"""Shared, deterministic fuzzy text matching.

Opt-in approximate matching layered on top of the existing exact-substring
search paths (``search``, ``find``, ``/api/items``). An exact,
Unicode-normalized substring match always outranks any approximate-only
match; scoring is otherwise a bounded, token-level Levenshtein similarity
with no external dependency and no persistent index.
"""

from __future__ import unicode_literals

import re
import unicodedata


#: Similarity at or above this threshold counts as a fuzzy match.
DEFAULT_THRESHOLD = 0.6

#: Queries shorter than this (after normalization) only ever match via
#: exact substring; edit-distance scoring on very short strings is noisy
#: and low-signal (a one-character query is "close" to almost anything).
MIN_FUZZY_QUERY_LENGTH = 3

#: Per-string cap so one pathologically long field or query cannot make a
#: single comparison unbounded.
_MAX_COMPARE_LENGTH = 200

#: Cap on how many tokens of one field are scored, for the same reason.
_MAX_TOKENS_COMPARED = 50

_TOKEN_SPLIT = re.compile(r"[\s、。,.:;/\\|()\[\]{}\-]+")


def normalize_text(value):
    """NFKC-normalize and casefold ``value``.

    NFKC folds full-width/half-width Japanese variants (and other
    compatibility forms) to one representation; casefold makes Latin
    comparison case-insensitive, matching every other search path in this
    module.
    """
    text = value if isinstance(value, str) else str(value if value is not None else "")
    return unicodedata.normalize("NFKC", text).casefold()


def _tokenize(text):
    return [part for part in _TOKEN_SPLIT.split(text) if part]


def _levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            current[j] = min(
                previous[j] + 1,  # deletion
                current[j - 1] + 1,  # insertion
                previous[j - 1] + cost,  # substitution
            )
        previous = current
    return previous[-1]


def similarity(query, text):
    """Deterministic similarity of ``query`` against ``text`` in [0.0, 1.0].

    1.0 means the normalized strings are equal; a normalized-substring
    match returns 0.999, always ranked above any score this function can
    produce through the fuzzy fallback alone. Returns 0.0 for an empty
    (after normalization) query.
    """
    q = normalize_text(query)
    t = normalize_text(text)
    if not q:
        return 0.0
    if q == t:
        return 1.0
    if q in t:
        return 0.999
    if len(q) < MIN_FUZZY_QUERY_LENGTH:
        return 0.0
    q = q[:_MAX_COMPARE_LENGTH]
    candidates = _tokenize(t)[:_MAX_TOKENS_COMPARED]
    candidates.append(t[:_MAX_COMPARE_LENGTH])
    best = 0.0
    for candidate in candidates:
        candidate = candidate[:_MAX_COMPARE_LENGTH]
        longest = max(len(q), len(candidate))
        if not longest:
            continue
        distance = _levenshtein(q, candidate)
        score = 1.0 - (distance / longest)
        if score > best:
            best = score
    return max(0.0, best)


def fuzzy_contains(query, text, threshold=DEFAULT_THRESHOLD):
    """True if ``text`` exactly contains ``query`` or scores >= ``threshold``."""
    return similarity(query, text) >= threshold


def is_exact_match(query, text):
    """True if the normalized ``query`` is an exact substring of ``text``."""
    q = normalize_text(query)
    if not q:
        return False
    return q in normalize_text(text)
