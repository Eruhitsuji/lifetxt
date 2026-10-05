"""Effective browser origin at the explicitly configured proxy trust boundary.

The immediate ASGI peer must be preserved: serve/web disable Uvicorn's own
proxy header middleware. This module does not infer encryption from a peer IP.
"""

from urllib.parse import urlsplit

from .remote_access import trusted_peer


def origin_parts(value):
    """Validate a serialized HTTP origin; return scheme, hostname, effective port."""
    if not value or any(c.isspace() or ord(c) < 32 for c in value):
        return None
    if any(c in value for c in ("\\", ",", "?", "#")):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.netloc.endswith(":")
        ):
            return None
        port = parsed.port
        if port == 0:
            return None
        return (
            parsed.scheme,
            parsed.hostname,
            port or (443 if parsed.scheme == "https" else 80),
        )
    except ValueError:
        return None


def expected_origin(request, config=None):
    """Ignore untrusted forwarding; fail closed on ambiguous trusted headers."""
    headers = request.headers
    if len(headers.getlist("host")) > 1:
        return None
    host = headers.get("host") or request.url.netloc
    scheme = request.url.scheme
    peer = request.client.host if request.client else None
    if trusted_peer(config, peer):
        for key in ("x-forwarded-proto", "x-forwarded-host"):
            values = headers.getlist(key)
            if len(values) > 1 or (values and (not values[0] or "," in values[0])):
                return None
        scheme = headers.get("x-forwarded-proto", scheme)
        host = headers.get("x-forwarded-host", host)
    value = "%s://%s" % (scheme, host)
    return value if origin_parts(value) else None
