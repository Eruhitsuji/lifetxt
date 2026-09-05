"""Locale resolution and message catalog for CLI presentation (#631).

This module owns *only* human-readable presentation text. It must never
gain a language-specific branch that changes domain, parser, serializer,
mutation, or machine-readable (JSON/JSONL/CSV/API/MCP/schema) behavior --
those stay locale-independent by design; see docs/en/cli.md's Localization
section for the boundary this project maintains.

Locale precedence, resolved once per process by :func:`resolve_locale`:

1. an explicit override (the CLI's ``--lang``)
2. the ``LIFETXT_LANG`` environment variable
3. the OS/process locale, normalized to a supported value
4. English (``en``), the mandatory fallback

The message catalog is a flat ``{message_id: {locale: text}}`` mapping so
callers own their own message IDs -- this module never duplicates a second
copy of command names, categories, or any other authoritative metadata
(see ``lifetxt/cli_taxonomy.py``, which registers its own display strings
here rather than the reverse). A missing translation, or an unknown
message ID entirely, always degrades to the English text or the raw ID
rather than raising or producing blank output.
"""

from __future__ import unicode_literals

import contextlib
import contextvars
import os


#: Locales this catalog can render text in. Every other value normalizes to
#: one of these or falls back to :data:`DEFAULT_LOCALE`.
SUPPORTED_LOCALES = ("en", "ja")
DEFAULT_LOCALE = "en"

_LOCALE_CONTEXT = contextvars.ContextVar("lifetxt_locale", default=None)

#: Message id -> {locale: text}. Populated by ``register_messages`` calls
#: from the modules that own each string (cli_taxonomy, tour, cli, doctor,
#: ...), never hardcoded here.
_CATALOG = {}


def normalize_locale(value):
    """Normalize a raw locale-ish string to a supported locale, or ``None``.

    Accepts POSIX (``ja_JP``), BCP-47 (``ja-JP``), and bare (``ja``) forms,
    case-insensitively. Returns ``None`` (not a fallback) when ``value``
    does not identify any supported locale, so callers can distinguish
    "no opinion" from "explicitly English" while walking the precedence
    chain.
    """
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    # A POSIX locale can carry an encoding/modifier suffix, e.g. "ja_JP.UTF-8".
    text = text.split(".", 1)[0]
    lowered = text.strip().lower().replace("_", "-")
    if not lowered or lowered in ("c", "posix"):
        return None
    primary = lowered.split("-", 1)[0]
    if primary == "ja":
        return "ja"
    if primary == "en":
        return "en"
    return None


def resolve_locale(explicit=None, env=None):
    """Resolve the effective locale using the documented precedence.

    ``env`` defaults to :data:`os.environ` and is only ever overridden by
    tests. Never raises: an unresolvable or unsupported locale at every
    step falls through to :data:`DEFAULT_LOCALE`.
    """
    env = os.environ if env is None else env

    normalized = normalize_locale(explicit)
    if normalized:
        return normalized

    normalized = normalize_locale(env.get("LIFETXT_LANG"))
    if normalized:
        return normalized

    try:
        import locale as locale_module

        os_locale = locale_module.getlocale()[0]
        if not os_locale:
            os_locale = locale_module.getdefaultlocale()[0]
    except (ValueError, TypeError, AttributeError):
        os_locale = None
    normalized = normalize_locale(os_locale)
    if normalized:
        return normalized

    return DEFAULT_LOCALE


@contextlib.contextmanager
def locale_context(value):
    """Temporarily make ``value`` the active locale for renderer lookups."""
    token = _LOCALE_CONTEXT.set(value)
    try:
        yield value
    finally:
        _LOCALE_CONTEXT.reset(token)


def current_locale():
    return _LOCALE_CONTEXT.get() or DEFAULT_LOCALE


def register_messages(entries):
    """Merge ``{message_id: {locale: text}}`` into the shared catalog.

    Safe to call repeatedly (e.g. at each affected module's import time);
    later registrations for the same ``message_id`` add or overwrite
    individual locales without clobbering ones already registered by
    another module.
    """
    for message_id, translations in entries.items():
        _CATALOG.setdefault(message_id, {}).update(translations)


def translate(message_id, locale=None, **kwargs):
    """Render ``message_id`` in ``locale`` (default: the active locale).

    Falls back to English, then to ``message_id`` itself, so a missing
    catalog entry never raises or produces blank output. ``kwargs`` are
    applied with ``str.format``; a formatting mismatch returns the
    unformatted text rather than raising.
    """
    locale = locale or current_locale()
    translations = _CATALOG.get(message_id)
    if not translations:
        return message_id
    text = translations.get(locale)
    if text is None:
        text = translations.get(DEFAULT_LOCALE)
    if text is None:
        return message_id
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


#: Short alias matching the convention used by lifetxt's Web UI translator.
t = translate
