"""Authoritative deterministic timezone and remote-clock cases for stable surfaces."""

from __future__ import unicode_literals


TIMEZONE_PRECEDENCE_CASES = (
    {
        "name": "cli overrides file and config",
        "config": {"defaults": {"timezone": "UTC"}},
        "text": "#! timezone: Asia/Tokyo\n",
        "cli_timezone": "Europe/London",
        "expected": "Europe/London",
    },
    {
        "name": "file overrides config",
        "config": {"defaults": {"timezone": "UTC"}},
        "text": "#! timezone: Asia/Tokyo\n",
        "cli_timezone": None,
        "expected": "Asia/Tokyo",
    },
    {
        "name": "config applies without file or cli",
        "config": {"defaults": {"timezone": "UTC"}},
        "text": "",
        "cli_timezone": None,
        "expected": "UTC",
    },
)


DATETIME_NORMALIZATION_CASES = (
    {
        "name": "aware utc converts to configured zone",
        "value": "2026-07-23T00:00:00+00:00",
        "timezone": "Asia/Tokyo",
        "expected": "2026-07-23T09:00:00+09:00",
    },
    {
        "name": "naive non-hour offset preserves wall time",
        "value": "2026-07-23T12:00",
        "timezone": "Asia/Kathmandu",
        "expected": "2026-07-23T12:00:00+05:45",
    },
    {
        "name": "midnight boundary remains local midnight",
        "value": "2026-07-23T00:00",
        "timezone": "Asia/Tokyo",
        "expected": "2026-07-23T00:00:00+09:00",
    },
)


WALL_TIME_CASES = (
    {
        "name": "new-york fold",
        "value": "2026-11-01T01:30",
        "timezone": "America/New_York",
        "state": "ambiguous",
        "error": "Ambiguous local datetime",
        "resolved": {"earlier": "-04:00", "later": "-05:00"},
    },
    {
        "name": "new-york gap",
        "value": "2026-03-08T02:30",
        "timezone": "America/New_York",
        "state": "nonexistent",
        "error": "Nonexistent local datetime",
        "gap_next": "2026-03-08T03:00:00-04:00",
    },
    {
        "name": "historical new-york pre-2007 transition",
        "value": "2006-03-12T02:30",
        "timezone": "America/New_York",
        "state": "valid",
    },
)


TIME_ONLY_CASES = (
    {
        "name": "offset time anchors before conversion",
        "value": "09:15+00:00",
        "anchor_date": "2026-07-23",
        "timezone": "Asia/Tokyo",
        "expected": "2026-07-23T18:15:00+09:00",
    },
)


CLOCK_SKEW_CASES = (
    {
        "name": "positive within warning",
        "client_time": "2026-07-24T12:00:05Z",
        "state": "ok",
        "write_allowed": True,
    },
    {
        "name": "positive warning",
        "client_time": "2026-07-24T12:00:30Z",
        "state": "warning",
        "write_allowed": True,
    },
    {
        "name": "positive reject",
        "client_time": "2026-07-24T12:02:00Z",
        "state": "reject",
        "write_allowed": False,
    },
    {
        "name": "negative reject",
        "client_time": "2026-07-24T11:58:00Z",
        "state": "reject",
        "write_allowed": False,
    },
)


WINDOWS_TZDATA_POLICY = {
    "platform": "Windows",
    "provider": "zoneinfo",
    "dependency": "tzdata",
    "forbidden_fallbacks": ("dateutil", "pytz"),
}


STABLE_SURFACE_APPLICABILITY = {
    "CLI/TUI/Web/MCP": "Resolve timezone precedence and format/display through timezone_policy.",
    "notifications/import/export/projects/tickets/events/time entries/work sessions": "Consume timezone-aware values from shared parser/time utilities; they do not own a second timezone parser.",
    "remote writable requests": "Use CLOCK_SKEW_CASES at the shared clock_skew boundary; authenticated audit binding is #311.",
}
