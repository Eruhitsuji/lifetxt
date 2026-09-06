"""Dependency-free HTTP client for the Web API-backed Remote TUI (#679).

Talks to an ordinary ``lifetxt serve`` deployment -- not Remote Safe Mode --
reusing the existing item read/mutation REST routes and the existing
whole-file revision-precondition contract (``GET /api/revision`` /
``If-Match`` / 409 ``CONFLICT``) that :mod:`lifetxt.surface_runtime` already
installs on every ``lifetxt serve`` app. No server-side change was needed
for this: the routes this backend calls already refuse a stale write with a
structured conflict response.

Uses only the standard library (``urllib``), matching this project's
dependency-light design. HTTP Basic Auth credentials are added when a
username is configured; the password is read from an environment variable
supplied by the caller, never taken as a literal CLI argument value. Plain
HTTP to a non-loopback host is refused unless the caller explicitly opts in
(the documented WireGuard/private-network deployment case), matching
:mod:`lifetxt.remote_client`'s existing HTTPS-outside-loopback posture for
Remote Safe Mode -- this module does not touch or relax that.
"""

from __future__ import unicode_literals

import base64
import json
import socket
import urllib.error
import urllib.parse
import urllib.request

_LOOPBACK_HOSTS = frozenset(("127.0.0.1", "localhost", "::1", "[::1]"))


class RemoteTuiError(Exception):
    """Base class for every error this module raises."""


class RemoteInsecureHttpRequired(RemoteTuiError):
    """Plain HTTP was requested to a non-loopback host with no opt-in."""


class RemoteConnectionError(RemoteTuiError):
    """The server could not be reached, or returned an unstructured error."""


class RemoteAuthError(RemoteTuiError):
    """The server rejected the request as unauthenticated/unauthorized."""


class RemoteMutationConflict(RemoteTuiError):
    """The server refused a write because the file changed underneath it.

    Mirrors ``lifetxt.remote_client_writes.RemoteMutationConflict``'s
    non-retrying posture: the caller must refresh and let the user decide,
    never automatically rebase and retry.
    """

    def __init__(self, message, current_revision=None, current_item=None):
        self.current_revision = current_revision
        self.current_item = current_item
        RemoteTuiError.__init__(self, message)


def _is_loopback(host):
    return (host or "").strip("[]").lower() in (
        "127.0.0.1",
        "localhost",
        "::1",
    )


class RemoteTuiConnection(object):
    """One configured connection to a ``lifetxt serve`` deployment."""

    def __init__(
        self,
        base_url,
        username=None,
        password=None,
        allow_insecure_http=False,
        timeout=5.0,
    ):
        if not base_url:
            raise ValueError("A remote base URL is required.")
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Remote URL must start with http:// or https://.")
        host = parsed.hostname or ""
        if (
            parsed.scheme == "http"
            and not _is_loopback(host)
            and not allow_insecure_http
        ):
            raise RemoteInsecureHttpRequired(
                "Refusing plain HTTP to a non-loopback host (%s) without "
                "--allow-insecure-remote-http. Plain HTTP is only appropriate "
                "over an already-secured private network (for example, a "
                "WireGuard tunnel); HTTPS remains the safer general default." % host
            )
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.host = host
        #: Last file revision this connection observed, from either a read
        #: or a write response. Callers use this as the ``If-Match`` value
        #: for the next write.
        self.file_revision = None

    def describe(self):
        """Credential-safe status string for the TUI header (#677)."""
        who = (" as %s" % self.username) if self.username else ""
        return "%s%s" % (self.base_url, who)

    def _headers(self):
        headers = {"Accept": "application/json"}
        if self.username:
            token = base64.b64encode(
                ("%s:%s" % (self.username, self.password or "")).encode("utf-8")
            ).decode("ascii")
            headers["Authorization"] = "Basic %s" % token
        return headers

    def request(self, method, path, json_body=None, if_match=None):
        url = self.base_url + path
        headers = self._headers()
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if if_match:
            headers["If-Match"] = if_match
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            response = urllib.request.urlopen(req, timeout=self.timeout)
            status = response.getcode()
            body = response.read()
            response_headers = response.headers
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read()
            response_headers = exc.headers
        except urllib.error.URLError as exc:
            raise RemoteConnectionError(
                "Could not reach %s: %s" % (self.base_url, exc.reason)
            )
        except (socket.timeout, OSError) as exc:
            raise RemoteConnectionError("Could not reach %s: %s" % (self.base_url, exc))

        revision = None
        if response_headers is not None:
            revision = response_headers.get("X-Lifetxt-Revision")
        if revision:
            self.file_revision = revision

        payload = None
        if body:
            try:
                payload = json.loads(body.decode("utf-8"))
            except ValueError:
                payload = None

        if status in (401, 403):
            raise RemoteAuthError(
                "Authentication failed (HTTP %d) for %s." % (status, self.base_url)
            )
        if status == 409:
            detail = payload if isinstance(payload, dict) else {}
            raise RemoteMutationConflict(
                detail.get("message") or "The item changed on the server.",
                current_revision=detail.get("current_revision"),
                current_item=detail.get("current_item"),
            )
        if status >= 400:
            message = None
            if isinstance(payload, dict):
                message = payload.get("message") or payload.get("detail")
            raise RemoteConnectionError(
                message or ("Remote request failed (HTTP %d)." % status)
            )
        return payload

    def get_revision(self):
        payload = self.request("GET", "/api/revision")
        if isinstance(payload, dict) and payload.get("revision"):
            self.file_revision = payload["revision"]
        return self.file_revision
