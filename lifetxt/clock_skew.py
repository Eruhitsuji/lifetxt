"""Server-authoritative clock-skew reporting for remote clients."""

from __future__ import unicode_literals

import datetime
from collections import OrderedDict

from .timeutil import parse_iso_datetime


class ClockSkewError(ValueError):
    pass


def parse_timestamp(value):
    if isinstance(value, datetime.datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            raise ClockSkewError("A client timestamp is required.")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = parse_iso_datetime(text)
        if parsed is None:
            raise ClockSkewError("Invalid client timestamp.")
    if parsed.tzinfo is None:
        raise ClockSkewError("Client timestamps must include a UTC offset.")
    return parsed.astimezone(datetime.timezone.utc)


def server_now(now=None):
    if now is None:
        from .timezone_policy import utcnow
        value = utcnow()
    else:
        value = now
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def clock_skew_report(client_time=None, config=None, now=None):
    config = config or {}
    raw = config.get("clock") if isinstance(config.get("clock"), dict) else {}
    warning = max(0.0, float(raw.get("skew_warning_seconds", 30.0)))
    reject = max(warning, float(raw.get("skew_reject_seconds", 300.0)))
    authoritative = server_now(now)
    report = OrderedDict(
        (
            ("server_time_utc", authoritative.replace(microsecond=0).isoformat().replace("+00:00", "Z")),
            ("server_authoritative", True),
            ("warning_seconds", warning),
            ("reject_seconds", reject),
            ("client_time_utc", None),
            ("skew_seconds", None),
            ("absolute_skew_seconds", None),
            ("state", "not_measured"),
            ("write_allowed", True),
        )
    )
    if client_time in (None, ""):
        return report
    client = parse_timestamp(client_time)
    skew = (client - authoritative).total_seconds()
    absolute = abs(skew)
    if absolute > reject:
        state = "reject"
        allowed = False
    elif absolute > warning:
        state = "warning"
        allowed = True
    else:
        state = "ok"
        allowed = True
    report.update(
        (
            ("client_time_utc", client.replace(microsecond=0).isoformat().replace("+00:00", "Z")),
            ("skew_seconds", skew),
            ("absolute_skew_seconds", absolute),
            ("state", state),
            ("write_allowed", allowed),
        )
    )
    return report


def require_acceptable_clock(client_time, config=None, now=None):
    report = clock_skew_report(client_time, config=config, now=now)
    if not report["write_allowed"]:
        raise ClockSkewError(
            "Client clock skew %.3fs exceeds the %.3fs write limit; use the server timestamp."
            % (report["absolute_skew_seconds"], report["reject_seconds"])
        )
    return report
