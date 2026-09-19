"""Host-independent logical record link: ``lifetxt://item/<id>`` (#840).

A ``lifetxt://item/<id>`` URI is a portable *identity* reference: it names
a record by its canonical ``id:`` value, the same identity
``lifetxt.ids.resolve_item_by_id``, ``GET /api/items/{id}`` (#837), and the
Web UI ``?id=`` deep link (#838) already use, without embedding a
particular deployment's host, port, or path. Parsing/formatting this URI is
deliberately the only thing this module does -- it never checks whether the
id exists or who may see it. Existence and authorization stay exactly where
they already live: the caller's own item lookup and workspace/permission
boundary.

This is the single shared parser/resolver seam the #840 acceptance criteria
ask for, so a CLI script, the MCP server, or the Web UI never has to
hand-parse the URI form independently.
"""

from __future__ import annotations

from urllib.parse import quote, unquote

__all__ = [
    "SCHEME",
    "ItemUriError",
    "format_item_uri",
    "parse_item_uri",
    "is_item_uri",
    "web_deep_link",
]

SCHEME = "lifetxt"
_PREFIX = "lifetxt://item/"


class ItemUriError(ValueError):
    """A string is not a well-formed ``lifetxt://item/<id>`` URI."""


def format_item_uri(item_id):
    """Return the canonical ``lifetxt://item/<id>`` URI for ``item_id``.

    ``item_id`` is percent-encoded so any character that would otherwise
    be read as part of the URI's own structure (``/``, ``?``, ``#``, a
    literal space, ...) round-trips through :func:`parse_item_uri`.
    """
    text = "" if item_id is None else str(item_id)
    if not text:
        raise ItemUriError("An item id must not be empty.")
    return _PREFIX + quote(text, safe="")


def is_item_uri(text):
    """Return whether ``text`` looks like a ``lifetxt://item/`` URI at all.

    Used to distinguish "not a lifetxt item URI" from "a malformed one" --
    callers that only accept this scheme can use this as a cheap guard
    before calling :func:`parse_item_uri`, which still does the real
    validation.
    """
    return isinstance(text, str) and text.strip().startswith(_PREFIX)


def parse_item_uri(uri):
    """Return the canonical item id encoded in ``uri``.

    Raises :class:`ItemUriError` for anything that is not a well-formed
    ``lifetxt://item/<id>`` URI: a different scheme entirely, a missing or
    empty id, or an id segment containing an unencoded path/query/fragment
    delimiter. This never raises for an id that is merely unknown --
    "malformed URI" and "URI names a record that does not exist" are
    deliberately distinguishable failure modes, so a caller can report
    each one accurately instead of collapsing both into one error.
    """
    if not isinstance(uri, str):
        raise ItemUriError("A lifetxt item URI must be a string, got %r." % (uri,))
    text = uri.strip()
    if not text.startswith(_PREFIX):
        raise ItemUriError("Not a lifetxt item URI: %r" % uri)
    raw_id = text[len(_PREFIX) :]
    if not raw_id or "/" in raw_id or "?" in raw_id or "#" in raw_id:
        raise ItemUriError("Malformed lifetxt item URI: %r" % uri)
    item_id = unquote(raw_id)
    if not item_id:
        raise ItemUriError("Malformed lifetxt item URI: %r" % uri)
    return item_id


def web_deep_link(item_id, base_url=""):
    """Translate a canonical id into the #838 Web deep-link form.

    ``base_url`` is the deployment's own origin (for example
    ``https://lifetxt.example.invalid``); when omitted, a root-relative
    link (``/?id=...``) is returned. This never changes the underlying
    record id and performs no existence/authorization check -- translating
    an id to a URL is not the same as confirming the record is reachable.
    """
    text = "" if item_id is None else str(item_id)
    if not text:
        raise ItemUriError("An item id must not be empty.")
    base = base_url.rstrip("/") if base_url else ""
    return "%s/?id=%s" % (base, quote(text, safe=""))
