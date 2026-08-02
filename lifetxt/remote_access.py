"""Authenticated, deny-by-default Remote Safe Mode contracts."""

from __future__ import unicode_literals

import hashlib
import hmac
import ipaddress
import json
import os
import re
import threading
import time
import uuid
from collections import OrderedDict, defaultdict, deque

REMOTE_PROTOCOL_MIN = 1
REMOTE_PROTOCOL_CURRENT = 2
REMOTE_VERSION_HEADER = "X-Lifetxt-Remote-Version"
REMOTE_MIN_VERSION_HEADER = "X-Lifetxt-Remote-Min-Version"
REMOTE_CAPABILITY_REVISION_HEADER = "X-Lifetxt-Remote-Capability-Revision"

ROLES = {
    "owner": frozenset(("read", "write", "admin", "audit")),
    "editor": frozenset(("read", "write")),
    "reader": frozenset(("read",)),
    "auditor": frozenset(("read", "audit")),
}
VISIBILITIES = frozenset(("public", "shared", "team", "private", "secret"))


class RemoteAccessError(ValueError):
    def __init__(self, code, message, status=403, detail=None):
        super(RemoteAccessError, self).__init__(message)
        self.code = str(code)
        self.status = int(status)
        self.detail = dict(detail or {})


def _section(config):
    value = (config or {}).get("remote")
    return value if isinstance(value, dict) else {}


def enabled(config):
    return bool(_section(config).get("enabled", False))


def _principal_rows(config):
    value = _section(config).get("principals") or []
    if isinstance(value, dict):
        rows = []
        for key, row in value.items():
            item = dict(row or {})
            item.setdefault("id", str(key))
            rows.append(item)
        return rows
    return [dict(row) for row in value if isinstance(row, dict)]


def principal_registry(config):
    result = OrderedDict()
    for row in _principal_rows(config):
        principal_id = str(row.get("id") or "").strip()
        if not principal_id or principal_id in result:
            continue
        role = str(row.get("role") or "reader").lower()
        if role not in ROLES:
            role = "reader"
        scopes = set(ROLES[role])
        scopes.update(str(value) for value in row.get("scopes") or [])
        visibilities = []
        for value in row.get("visibilities") or ["public", "shared"]:
            value = str(value).lower()
            if value in VISIBILITIES and value not in visibilities:
                visibilities.append(value)
        result[principal_id] = OrderedDict(
            (
                ("id", principal_id),
                ("display_name", str(row.get("display_name") or principal_id)),
                ("role", role),
                ("scopes", sorted(scopes)),
                ("projects", sorted(str(value) for value in row.get("projects") or [])),
                ("groups", sorted(str(value) for value in row.get("groups") or [])),
                ("visibilities", sorted(visibilities)),
                ("disabled", bool(row.get("disabled"))),
                ("token_env", row.get("token_env")),
            )
        )
    return result


def public_principal(principal):
    principal = principal or {}
    return OrderedDict(
        (
            ("id", principal.get("id")),
            ("display_name", principal.get("display_name") or principal.get("id")),
            ("role", principal.get("role")),
            ("scopes", list(principal.get("scopes") or [])),
            ("projects", list(principal.get("projects") or [])),
            ("groups", list(principal.get("groups") or [])),
            ("visibilities", list(principal.get("visibilities") or [])),
            ("disabled", bool(principal.get("disabled"))),
        )
    )


def _token_for(row):
    name = row.get("token_env")
    return os.environ.get(str(name)) if name else None


def authenticate_token(token, config):
    supplied = str(token or "")
    if not supplied:
        raise RemoteAccessError("UNAUTHORIZED", "A bearer token is required.", 401)
    matches = []
    for row in principal_registry(config).values():
        expected = _token_for(row)
        if expected and not row["disabled"] and hmac.compare_digest(supplied, expected):
            matches.append(row)
    if len(matches) == 1:
        return matches[0], "bearer"
    if len(matches) > 1:
        raise RemoteAccessError(
            "AMBIGUOUS_CREDENTIAL",
            "The bearer credential matches multiple configured principals.",
            500,
        )
    raise RemoteAccessError("UNAUTHORIZED", "The bearer token is invalid.", 401)


def _trusted_peer(remote, address):
    if not address:
        return False
    try:
        ip = ipaddress.ip_address(str(address))
    except ValueError:
        return False
    for raw in remote.get("trusted_proxies") or []:
        try:
            if ip in ipaddress.ip_network(str(raw), strict=False):
                return True
        except ValueError:
            continue
    return False


def trusted_peer(config, address):
    return _trusted_peer(_section(config), address)


def authenticate(headers, client_host, config):
    if not enabled(config):
        raise RemoteAccessError("REMOTE_DISABLED", "Remote Safe Mode is disabled.", 404)
    remote = _section(config)
    registry = principal_registry(config)
    headers = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
    proxy_header = str(
        remote.get("proxy_principal_header") or "X-Lifetxt-Principal"
    ).lower()
    asserted = headers.get(proxy_header)
    if asserted and _trusted_peer(remote, client_host):
        row = registry.get(asserted)
        if row and not row["disabled"]:
            return row, "trusted-proxy"
        raise RemoteAccessError(
            "UNKNOWN_PRINCIPAL", "Trusted proxy asserted an unknown principal.", 401
        )
    authorization = headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise RemoteAccessError(
            "UNAUTHORIZED", "Authorization: Bearer TOKEN is required.", 401
        )
    return authenticate_token(authorization[7:], config)


def require_scope(principal, scope):
    if scope not in set((principal or {}).get("scopes") or []):
        raise RemoteAccessError("FORBIDDEN", "Principal lacks %s scope." % scope, 403)


def can_access(principal, project=None, visibility="shared", owner=None, groups=None):
    principal = principal or {}
    visibility = str(visibility or "shared").lower()
    if visibility not in VISIBILITIES:
        visibility = "private"
    if principal.get("role") == "owner":
        return True
    projects = principal.get("projects") or []
    if project and projects and str(project) not in projects:
        return False
    if visibility == "public":
        return True
    if visibility == "shared":
        return visibility in principal.get("visibilities", [])
    if visibility == "team":
        return bool(set(groups or []) & set(principal.get("groups") or []))
    if visibility in ("private", "secret"):
        return bool(owner and str(owner) == principal.get("id"))
    return False


def _looks_path_key(key):
    lowered = str(key or "").lower()
    return any(
        token in lowered for token in ("path", "source", "file", "directory", "root")
    )


def redact_remote_value(value, key=None):
    """Recursively redact local paths and token-related fields."""
    if isinstance(value, dict):
        result = OrderedDict()
        for child_key, child_value in value.items():
            lowered = str(child_key).lower()
            if lowered in (
                "token",
                "secret",
                "password",
                "authorization",
                "cookie",
                "set-cookie",
            ):
                result[child_key] = "<redacted>"
            else:
                result[child_key] = redact_remote_value(child_value, child_key)
        return result
    if isinstance(value, (list, tuple)):
        return [redact_remote_value(child, key) for child in value]
    if isinstance(value, str):
        expanded = os.path.expanduser(value)
        if os.path.isabs(expanded) or value.startswith(("file://", "\\\\")):
            return "<redacted>"
        if re.search(
            r"(?:^|[\s:=])(?:[A-Za-z]:[\\/]|/(?:home|tmp|var|etc|opt|srv|Users|mnt|media)/|\\\\)",
            value,
        ):
            return "<redacted>"
        if _looks_path_key(key) and ("/" in value or "\\" in value):
            return "<redacted>"
    return value


def filter_records(records, principal):
    output = []
    for row in records or []:
        if can_access(
            principal,
            row.get("project"),
            row.get("visibility"),
            row.get("owner"),
            row.get("groups"),
        ):
            output.append(redact_remote_value(dict(row)))
    return output


def require_exact_revision(headers, current):
    value = (headers or {}).get("if-match") or (headers or {}).get("If-Match")
    if not value:
        raise RemoteAccessError(
            "REVISION_REQUIRED", "If-Match exact revision is required.", 428
        )
    value = str(value).strip().strip('"')
    if value != str(current):
        raise RemoteAccessError(
            "REVISION_CONFLICT",
            "The authoritative revision changed.",
            409,
            {"current_revision": str(current)},
        )
    return value


def require_https(headers, client_host, config, request_scheme=None):
    remote = _section(config)
    forwarded = (headers or {}).get("x-forwarded-proto") or (headers or {}).get(
        "X-Forwarded-Proto"
    )
    if forwarded and _trusted_peer(remote, client_host):
        proto = str(forwarded).split(",")[0].strip().lower()
    else:
        proto = str(request_scheme or "http").strip().lower()
    loopback = str(client_host or "") in ("127.0.0.1", "::1", "localhost", "testclient")
    if proto != "https" and not (loopback and remote.get("allow_loopback_http", True)):
        raise RemoteAccessError("HTTPS_REQUIRED", "Remote access requires HTTPS.", 400)


def negotiate_protocol(headers, default=REMOTE_PROTOCOL_MIN):
    raw = None
    for key, value in (headers or {}).items():
        if str(key).lower() == REMOTE_VERSION_HEADER.lower():
            raw = value
            break
    if raw in (None, ""):
        requested = int(default)
    else:
        try:
            requested = int(str(raw).strip())
        except (TypeError, ValueError):
            raise RemoteAccessError(
                "REMOTE_VERSION_INVALID",
                "%s must be an integer." % REMOTE_VERSION_HEADER,
                400,
            )
    if requested < REMOTE_PROTOCOL_MIN or requested > REMOTE_PROTOCOL_CURRENT:
        raise RemoteAccessError(
            "REMOTE_VERSION_UNSUPPORTED",
            "Remote protocol version %s is not supported." % requested,
            426,
            {"minimum": REMOTE_PROTOCOL_MIN, "current": REMOTE_PROTOCOL_CURRENT},
        )
    return requested


class RateLimiter(object):
    def __init__(self, clock=None):
        self._lock = threading.Lock()
        self._events = defaultdict(deque)
        self._clock = clock or time.monotonic

    def check(self, key, limit, window=60):
        now = float(self._clock())
        with self._lock:
            queue = self._events[str(key)]
            while queue and queue[0] <= now - window:
                queue.popleft()
            if len(queue) >= int(limit):
                raise RemoteAccessError(
                    "RATE_LIMITED", "Remote request rate limit exceeded.", 429
                )
            queue.append(now)


def request_id(headers=None):
    value = (headers or {}).get("x-request-id") or (headers or {}).get("X-Request-ID")
    return str(value or uuid.uuid4())[:128]


def audit_event(
    principal, action, outcome, request_id_value, client_host=None, detail=None
):
    from .timezone_policy import utcnow

    public = public_principal(principal) if principal else None
    return OrderedDict(
        (
            ("schema", "remote-audit-event-v1.schema.json"),
            ("version", "1"),
            ("at", utcnow().isoformat()),
            ("request_id", request_id_value),
            ("principal", public.get("id") if public else None),
            ("role", public.get("role") if public else None),
            ("action", str(action)),
            ("outcome", outcome),
            ("client", str(client_host or "")),
            ("detail", redact_remote_value(dict(detail or {}))),
        )
    )


def validate_remote_storage(config, paths=None, writable_path=None):
    """Fail startup when the audit sink aliases an authoritative input."""
    audit_path = _section(config).get("audit_log")
    if not audit_path:
        return True
    audit_real = os.path.realpath(os.path.abspath(os.path.expanduser(str(audit_path))))
    protected = []
    for raw in list(paths or []) + ([writable_path] if writable_path else []):
        if raw:
            protected.append(
                os.path.realpath(os.path.abspath(os.path.expanduser(str(raw))))
            )
    if audit_real in protected:
        raise RemoteAccessError(
            "REMOTE_AUDIT_PATH_CONFLICT",
            "remote.audit_log must not be an authoritative input or writable life.txt path.",
            500,
        )
    return True


def append_audit(config, event):
    remote = _section(config)
    path = remote.get("audit_log")
    if not path:
        return
    path = os.path.abspath(os.path.expanduser(str(path)))
    line = (
        json.dumps(
            redact_remote_value(event), ensure_ascii=False, separators=(",", ":")
        )
        + "\n"
    )
    limit = int(remote.get("audit_max_bytes") or 5 * 1024 * 1024)
    from .mutation import write_text

    def transform(current):
        value = current + line
        if len(value.encode("utf-8")) > limit:
            value = value[-max(1, limit // 2) :]
            cut = value.find("\n")
            if cut >= 0:
                value = value[cut + 1 :]
        return value

    write_text(
        path,
        transform=transform,
        operation="remote audit append",
        create=True,
        default_text="",
    )


def _capability_v1(config):
    remote = _section(config)
    return OrderedDict(
        (
            ("schema", "remote-access-policy-v1.schema.json"),
            ("contract_version", "1"),
            ("enabled", enabled(config)),
            ("browser_ui", bool(remote.get("browser_ui", False))),
            ("authentication", ["bearer", "trusted-proxy"]),
            ("roles", {key: sorted(value) for key, value in ROLES.items()}),
            ("exact_revision_required", True),
            ("https_required", True),
            (
                "write_operations",
                [
                    "ticket.transition",
                    "ticket.comment",
                    "ticket.change",
                    "ticket.assign",
                    "ticket.plan",
                ],
            ),
            (
                "read_operations",
                ["capabilities", "session", "snapshot", "tickets", "projects", "audit"],
            ),
            ("remote_opener_execution", False),
            ("local_paths_redacted", True),
            ("protocol_min", REMOTE_PROTOCOL_MIN),
            ("protocol_current", REMOTE_PROTOCOL_CURRENT),
        )
    )


def _capability_v2(config):
    from .remote_backend import resource_catalog

    remote = _section(config)
    payload = OrderedDict(
        (
            ("schema", "remote-capability-v2.schema.json"),
            ("contract_version", "2"),
            ("enabled", enabled(config)),
            (
                "protocol",
                {
                    "minimum": REMOTE_PROTOCOL_MIN,
                    "current": REMOTE_PROTOCOL_CURRENT,
                    "default_without_header": REMOTE_PROTOCOL_MIN,
                    "request_header": REMOTE_VERSION_HEADER,
                },
            ),
            ("authentication", ["bearer", "trusted-proxy", "browser-session"]),
            ("roles", {key: sorted(value) for key, value in ROLES.items()}),
            (
                "features",
                [
                    "browser-session",
                    "csrf",
                    "origin-check",
                    "resource-catalog",
                    "capability-negotiation",
                    "remote-diagnostics",
                    "recursive-redaction",
                ],
            ),
            ("resources", resource_catalog()),
            (
                "browser_session",
                {
                    "enabled": bool(remote.get("browser_ui", False)),
                    "opaque_cookie": True,
                    "http_only": True,
                    "same_site": "strict",
                    "restart_invalidates_session": True,
                    "csrf_header": str(remote.get("csrf_header") or "X-CSRF-Token"),
                },
            ),
            (
                "mutation_policy",
                {
                    "admission_only": True,
                    "exact_revision_required": True,
                    "authoritative_remote_writes_enabled": False,
                },
            ),
            ("https_required", True),
            ("local_paths_redacted", True),
            ("remote_opener_execution", False),
        )
    )
    payload["capability_revision"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload


def capability(config, protocol_version=None):
    version = REMOTE_PROTOCOL_MIN if protocol_version is None else int(protocol_version)
    return _capability_v1(config) if version <= 1 else _capability_v2(config)


def capability_revision(config):
    return _capability_v2(config)["capability_revision"]


def protocol_response_headers(config, protocol_version):
    return {
        REMOTE_VERSION_HEADER: str(protocol_version),
        REMOTE_MIN_VERSION_HEADER: str(REMOTE_PROTOCOL_MIN),
        REMOTE_CAPABILITY_REVISION_HEADER: capability_revision(config),
    }


def error_payload(exc, request_id_value=None):
    payload = OrderedDict(
        (
            ("error", exc.code),
            ("message", str(exc)),
        )
    )
    if exc.detail:
        payload["detail"] = redact_remote_value(exc.detail)
    if request_id_value:
        payload["request_id"] = request_id_value
    return payload
