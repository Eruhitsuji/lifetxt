"""Read-only Remote Safe Mode surface for bounded Git historical evidence.

Implements #728: exposing #725/#726's Git historical reader through the
server, gated by the #727 disclosure-policy investigation. This module
introduces no second repository/revision/as-of resolution policy and no
parallel authorization engine:

- ``read_historical_snapshot`` (``lifetxt.historical_temporal``) is the sole
  Git input path.
- Role/scope enforcement, visibility/ownership access checks, redaction, and
  audit-log append reuse ``lifetxt.remote_access`` unmodified.
- ``paths`` is always the caller's already-authorized, server-configured
  workspace source list; nothing here accepts a caller-supplied path or Git
  object ID.

Only two selectors are exposed, matching #727 Section 2: an exact revision
(``revision``) or a bounded committer-time as-of cutoff (``as_of``, with an
optional ``ref``). There is no revision-listing/history-browsing endpoint.

Authorization is conjunctive per #727 Section 1 and Section 7: a historical
record is visible only when both (a) its own historical
project/visibility/owner/groups metadata grants access under the current
principal, and (b) if a record with the same id currently exists in the live
workspace, that current record's own access tuple also grants access. The
more restrictive of the two wins by construction, since both must be true.
"""

from __future__ import unicode_literals

from collections import OrderedDict

from .historical_temporal import read_historical_snapshot
from .remote_access import (
    RemoteAccessError,
    append_audit,
    can_access,
    redact_remote_value,
    require_scope,
)
from .remote_backend import _access_for_item, source_revision

DEFAULT_HISTORICAL_LIMIT = 200
MAX_HISTORICAL_LIMIT = 1000
HISTORICAL_SCOPE = "historical"


def _remote(config):
    value = (config or {}).get("remote")
    return value if isinstance(value, dict) else {}


def historical_reads_enabled(config):
    return bool(_remote(config).get("historical_reads_enabled", False))


def _int_param(params, name, default, maximum):
    raw = (params or {}).get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise RemoteAccessError(
            "REMOTE_HISTORICAL_INVALID_PARAM", "%s must be an integer." % name, 400
        )
    if value <= 0:
        raise RemoteAccessError(
            "REMOTE_HISTORICAL_INVALID_PARAM",
            "%s must be a positive integer." % name,
            400,
        )
    return min(value, maximum)


def _row(item):
    details = OrderedDict()
    for key, values in sorted((getattr(item, "details", {}) or {}).items()):
        details[key] = list(values)
    return OrderedDict(
        (
            ("kind", getattr(item, "kind", None)),
            ("status", getattr(item, "status", None)),
            ("title", getattr(item, "title", None)),
            ("details", details),
        )
    )


def _item_id(item, key):
    for value in (getattr(item, "details", {}) or {}).get(key, []):
        return str(value)
    return None


def _current_access_index(paths, config, key):
    """Return {id: access_tuple} for the current live workspace, best effort.

    Used only for the conjunctive current-record check (#727 Section 1/7); a
    failure to read the live workspace never blocks or widens a historical
    read, it simply means no current record is checked against for that id.
    """
    from .links import build_id_index
    from .webapp import read_life_inputs

    try:
        current_items, _diagnostics = read_life_inputs(paths, config)
    except Exception:
        return {}
    index = build_id_index(current_items, key=key)
    access = {}
    for item_id, matches in index.items():
        if len(matches) == 1:
            access[item_id] = _access_for_item(matches[0], index)
    return access


def _audit(config, principal, params, classification, denial_reason=None, **extra):
    event = OrderedDict(
        (
            ("event", "remote_historical_read"),
            ("principal_id", (principal or {}).get("id")),
            ("principal_role", (principal or {}).get("role")),
            (
                "selector",
                "revision" if (params or {}).get("revision") else "as_of",
            ),
            ("classification", classification),
        )
    )
    if denial_reason:
        event["denial_reason"] = str(denial_reason)
    for name, value in extra.items():
        event[name] = value
    append_audit(config, event)


def read_historical_resource(paths, config, principal, params=None):
    """Bounded, permission-filtered Git historical read (#728).

    ``paths`` must already be the server's own configured source paths.
    Exactly one of ``revision``/``as_of`` is required (``ref`` only with
    ``as_of``), matching ``read_historical_snapshot``'s own contract. Fails
    closed -- raising ``RemoteAccessError`` -- on a Git-free workspace, an
    invalid/unknown revision, or missing historical sources; it never falls
    back to current state.
    """
    require_scope(principal, "read")
    require_scope(principal, HISTORICAL_SCOPE)
    params = dict(params or {})
    if not historical_reads_enabled(config):
        _audit(config, principal, params, "denied", "historical_reads_disabled")
        raise RemoteAccessError(
            "REMOTE_HISTORICAL_DISABLED",
            "Historical Git evidence reads are disabled for this deployment.",
            403,
        )

    from .ids import id_key_from_config
    from .links import build_id_index

    key = id_key_from_config(config or {})
    limit = _int_param(params, "limit", DEFAULT_HISTORICAL_LIMIT, MAX_HISTORICAL_LIMIT)

    try:
        snapshot = read_historical_snapshot(
            paths,
            key=key,
            revision=params.get("revision"),
            as_of=params.get("as_of"),
            ref=params.get("ref"),
        )
    except ValueError as exc:
        _audit(config, principal, params, "denied", "historical_unavailable:%s" % exc)
        raise RemoteAccessError("REMOTE_HISTORICAL_UNAVAILABLE", str(exc), 422)

    historical_meta = snapshot["historical"]
    historical_index = build_id_index(snapshot["items"], key=key)
    current_access = _current_access_index(paths, config, key)

    visible_rows = []
    denied_count = 0
    considered = 0
    for item in snapshot["items"]:
        considered += 1
        historical_access = _access_for_item(item, historical_index)
        if not can_access(principal, **historical_access):
            denied_count += 1
            continue
        item_id = _item_id(item, key)
        if item_id is not None and item_id in current_access:
            if not can_access(principal, **current_access[item_id]):
                denied_count += 1
                continue
        if len(visible_rows) < limit:
            visible_rows.append(item)

    truncated = (considered - denied_count) > len(visible_rows)

    result = OrderedDict(
        (
            ("schema", "remote-historical-read-v1.schema.json"),
            ("resource", "historical"),
            ("revision", source_revision(paths)),
            ("historical", historical_meta),
            ("count", len(visible_rows)),
            ("truncated", bool(truncated)),
            ("items", [_row(item) for item in visible_rows]),
        )
    )
    result = redact_remote_value(result)
    _audit(
        config,
        principal,
        params,
        "served",
        resolved_commit=historical_meta.get("resolved_commit"),
        loaded_path_count=len(historical_meta.get("loaded_paths") or []),
        missing_path_count=len(historical_meta.get("missing_paths") or []),
        returned_count=len(visible_rows),
        denied_count=denied_count,
    )
    return result
