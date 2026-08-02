"""Server-side browser sessions for Remote Safe Mode.

Sessions are opaque, process-local, bounded, and intentionally restart-invalidated.
Bearer tokens are accepted only by the login endpoint and are never placed in a
cookie, response, profile, or audit detail.
"""

from __future__ import unicode_literals

import hmac
import re
import secrets
import threading
import time
from collections import OrderedDict
from urllib.parse import urlsplit

from .remote_access import RemoteAccessError, public_principal

DEFAULT_COOKIE = "lifetxt_remote_session"
DEFAULT_CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset(("GET", "HEAD", "OPTIONS"))
_HTTP_TOKEN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


def _remote(config):
    value = (config or {}).get("remote")
    return value if isinstance(value, dict) else {}


def _http_token(value, setting):
    value = str(value or "")
    if not value or not _HTTP_TOKEN.match(value):
        raise RemoteAccessError(
            "REMOTE_SESSION_CONFIG_INVALID",
            "%s must be a valid HTTP token." % setting,
            500,
        )
    return value


def cookie_name(config):
    return _http_token(
        _remote(config).get("session_cookie_name") or DEFAULT_COOKIE,
        "remote.session_cookie_name",
    )


def csrf_header(config):
    return _http_token(
        _remote(config).get("csrf_header") or DEFAULT_CSRF_HEADER, "remote.csrf_header"
    )


def browser_enabled(config):
    return bool(_remote(config).get("enabled") and _remote(config).get("browser_ui"))


def validate_session_configuration(config):
    cookie_name(config)
    csrf_header(config)
    session_limits(config)
    for raw in _remote(config).get("allowed_origins") or []:
        value = str(raw or "").rstrip("/")
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise RemoteAccessError(
                "REMOTE_SESSION_CONFIG_INVALID",
                "remote.allowed_origins entries must be bare HTTP(S) origins.",
                500,
            )
    return True


def session_limits(config):
    remote = _remote(config)
    ttl = max(60, int(remote.get("browser_session_ttl_seconds") or 8 * 60 * 60))
    idle = max(30, int(remote.get("browser_session_idle_seconds") or 30 * 60))
    idle = min(idle, ttl)
    maximum = max(1, int(remote.get("browser_session_max") or 256))
    return ttl, idle, maximum


class BrowserSessionStore(object):
    """Thread-safe bounded opaque-session store.

    ``clock`` and ``token_factory`` are injectable to keep expiry and rotation
    tests deterministic. The store deliberately contains no persistence hook:
    a server restart invalidates every browser session.
    """

    def __init__(self, clock=None, token_factory=None):
        self._clock = clock or time.monotonic
        self._token_factory = token_factory or (
            lambda size=32: secrets.token_urlsafe(size)
        )
        self._lock = threading.RLock()
        self._sessions = OrderedDict()

    def _now(self):
        return float(self._clock())

    def _cleanup_locked(self, now):
        expired = []
        for session_id, row in list(self._sessions.items()):
            if row["expires_monotonic"] <= now or row["idle_expires_monotonic"] <= now:
                expired.append(session_id)
        for session_id in expired:
            self._sessions.pop(session_id, None)
        return len(expired)

    def cleanup(self):
        with self._lock:
            return self._cleanup_locked(self._now())

    def create(
        self, principal, authentication, config, client_host=None, user_agent=None
    ):
        ttl, idle, maximum = session_limits(config)
        now = self._now()
        with self._lock:
            self._cleanup_locked(now)
            while len(self._sessions) >= maximum:
                self._sessions.popitem(last=False)
            session_id = self._token_factory(32)
            csrf_token = self._token_factory(32)
            while session_id in self._sessions:
                session_id = self._token_factory(32)
            row = OrderedDict(
                (
                    ("session_id", session_id),
                    ("csrf_token", csrf_token),
                    ("principal", dict(principal)),
                    ("authentication", str(authentication)),
                    ("created_monotonic", now),
                    ("last_seen_monotonic", now),
                    ("expires_monotonic", now + ttl),
                    ("idle_expires_monotonic", now + idle),
                    ("ttl_seconds", ttl),
                    ("idle_seconds", idle),
                    ("client_host", str(client_host or "")),
                    ("user_agent", str(user_agent or "")[:512]),
                )
            )
            self._sessions[session_id] = row
            return dict(row)

    def resolve(self, session_id, config, touch=True):
        if not session_id:
            raise RemoteAccessError(
                "UNAUTHORIZED", "A valid browser session is required.", 401
            )
        _ttl, idle, _maximum = session_limits(config)
        now = self._now()
        with self._lock:
            self._cleanup_locked(now)
            row = self._sessions.get(str(session_id))
            if row is None:
                raise RemoteAccessError(
                    "SESSION_EXPIRED",
                    "The browser session expired or was revoked.",
                    401,
                )
            if row.get("principal", {}).get("disabled"):
                self._sessions.pop(str(session_id), None)
                raise RemoteAccessError(
                    "SESSION_REVOKED", "The browser session principal is disabled.", 401
                )
            if touch:
                row["last_seen_monotonic"] = now
                row["idle_expires_monotonic"] = min(
                    row["expires_monotonic"], now + idle
                )
                self._sessions.move_to_end(str(session_id))
            return dict(row)

    def revoke(self, session_id):
        with self._lock:
            return self._sessions.pop(str(session_id or ""), None) is not None

    def revoke_principal(self, principal_id):
        removed = 0
        with self._lock:
            for session_id, row in list(self._sessions.items()):
                if row.get("principal", {}).get("id") == str(principal_id):
                    self._sessions.pop(session_id, None)
                    removed += 1
        return removed

    def count(self):
        with self._lock:
            self._cleanup_locked(self._now())
            return len(self._sessions)


def session_payload(row, include_csrf=True):
    now = float(row.get("last_seen_monotonic") or row.get("created_monotonic") or 0.0)
    expires_in = max(0, int(float(row.get("expires_monotonic") or now) - now))
    idle_in = max(0, int(float(row.get("idle_expires_monotonic") or now) - now))
    payload = OrderedDict(
        (
            ("schema", "remote-browser-session-v1.schema.json"),
            ("principal", public_principal(row.get("principal") or {})),
            ("authentication", row.get("authentication") or "browser-session"),
            ("expires_in_seconds", expires_in),
            ("idle_expires_in_seconds", idle_in),
            ("restart_invalidates_session", True),
        )
    )
    if include_csrf:
        payload["csrf_token"] = row.get("csrf_token")
    return payload


def require_csrf(session, headers, method, origin, expected_origin, config):
    if str(method).upper() in SAFE_METHODS:
        return
    header_name = csrf_header(config)
    supplied = None
    for key, value in (headers or {}).items():
        if str(key).lower() == header_name.lower():
            supplied = str(value)
            break
    expected = str((session or {}).get("csrf_token") or "")
    if not supplied or not expected or not hmac.compare_digest(supplied, expected):
        raise RemoteAccessError(
            "CSRF_REQUIRED",
            "%s must contain the browser-session CSRF token." % header_name,
            403,
        )
    require_origin(origin, expected_origin, config)


def require_origin(origin, expected_origin, config):
    remote = _remote(config)
    allowed = set(
        str(value).rstrip("/") for value in remote.get("allowed_origins") or [] if value
    )
    if expected_origin:
        allowed.add(str(expected_origin).rstrip("/"))
    candidate = str(origin or "").rstrip("/")
    if not candidate:
        raise RemoteAccessError(
            "ORIGIN_REQUIRED", "Browser session writes require an Origin header.", 403
        )
    if candidate not in allowed:
        raise RemoteAccessError(
            "ORIGIN_FORBIDDEN", "The browser request origin is not allowed.", 403
        )


def cookie_security(request, config):
    host = request.client.host if request.client else ""
    forwarded = request.headers.get("x-forwarded-proto")
    from .remote_access import trusted_peer

    if forwarded and trusted_peer(config, host):
        scheme = str(forwarded).split(",")[0].strip().lower()
    else:
        scheme = str(request.url.scheme or "http").strip().lower()
    loopback = str(host) in ("127.0.0.1", "::1", "localhost", "testclient")
    secure = scheme == "https" or not (
        loopback and _remote(config).get("allow_loopback_http", True)
    )
    ttl, _idle, _maximum = session_limits(config)
    return {
        "key": cookie_name(config),
        "httponly": True,
        "secure": bool(secure),
        "samesite": "strict",
        "path": "/api/remote/",
        "max_age": ttl,
    }
