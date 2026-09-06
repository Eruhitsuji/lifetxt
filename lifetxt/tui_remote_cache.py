"""Read-only offline cache for the Remote TUI (#681).

A follow-up to #677-#680's synchronous, server-authoritative Remote TUI:
after a successful authenticated read, persist a bounded last-known
snapshot so a disconnected session can show the user a clearly-labeled
stale view instead of only a connection error.

Core rule, unchanged from the issue: cached data is a derived read
artifact. It is never treated as authoritative, never becomes a local
write target, and never stores credentials, tokens, or Authorization
headers. Opt-in via ``--remote-cache`` (off by default, per the issue's
own security/privacy guidance that a cache copies server-visible personal
data onto the client device).
"""

from __future__ import unicode_literals

import hashlib
import json
import os
import stat
import time
from collections import OrderedDict

#: Bumped if the on-disk shape ever changes incompatibly; an unreadable or
#: mismatched-version file is treated as "no cache" rather than crashing.
CACHE_VERSION = 1

#: Bound cache size (#681's "bound cache size/retention" requirement). A
#: workspace larger than this is truncated in the cache only -- the live
#: connection is always authoritative and unaffected.
MAX_CACHED_ITEMS = 2000


def cache_dir(directory=None):
    return os.path.abspath(
        os.path.expanduser(
            directory
            or os.environ.get("LIFETXT_REMOTE_TUI_CACHE_DIR")
            or "~/.cache/lifetxt/remote-tui"
        )
    )


def connection_cache_key(base_url, username=None):
    """Deterministic, filesystem-safe identity binding one cache file to
    one connection (URL + optional username), so data from different
    servers -- or different users on the same server -- is never mixed."""
    identity = "%s|%s" % ((base_url or "").rstrip("/"), username or "")
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]


def cache_file_path(base_url, username=None, directory=None):
    return os.path.join(
        cache_dir(directory), connection_cache_key(base_url, username) + ".json"
    )


def save_snapshot(
    base_url, items_payload, revision, username=None, directory=None, now=None
):
    """Persist a bounded last-known snapshot after a successful read.

    ``items_payload`` is the raw list of item dicts exactly as returned by
    ``GET /api/items`` (already free of credentials by construction: that
    response never contains Authorization headers or passwords).
    """
    target = cache_file_path(base_url, username=username, directory=directory)
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    items = list(items_payload or [])[:MAX_CACHED_ITEMS]
    payload = OrderedDict(
        (
            ("cache_version", CACHE_VERSION),
            ("base_url", (base_url or "").rstrip("/")),
            ("username", username or None),
            ("revision", revision),
            ("saved_at", now if now is not None else time.time()),
            ("item_count", len(items)),
            ("items", items),
        )
    )
    from .atomic import atomic_write_text

    atomic_write_text(
        target,
        json.dumps(payload, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    try:
        # Owner-only permissions where the OS supports it (#681): the
        # cache holds server-visible record content, not credentials, but
        # is still personal data that should not be world-readable.
        os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return target


def load_snapshot(base_url, username=None, directory=None):
    """Return the cached snapshot dict, or ``None`` if there is no usable
    cache. Never raises: a missing, unreadable, or corrupt cache file is
    treated identically to "no cache", since a broken cache must never
    block the ordinary connection-error path."""
    target = cache_file_path(base_url, username=username, directory=directory)
    if not os.path.exists(target):
        return None
    try:
        with open(target, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("cache_version") != CACHE_VERSION:
        return None
    return data


def clear_snapshot(base_url, username=None, directory=None):
    """Explicit cache-clear operation (#681's documented removal path)."""
    target = cache_file_path(base_url, username=username, directory=directory)
    try:
        os.remove(target)
        return True
    except OSError:
        return False
