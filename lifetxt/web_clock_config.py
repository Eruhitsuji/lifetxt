"""Validated presentation-only configuration for the Web header clock."""

import re

from .config_registry import CONFIG_REGISTRY


CLOCK_KEYS = (
    "enabled",
    "format",
    "show_date",
    "date_separator",
    "timezone",
    "show_timezone",
)
CLOCK_FORMAT_TOKENS = (
    "YYYY",
    "YY",
    "MMMM",
    "MMM",
    "MM",
    "M",
    "DD",
    "D",
    "dddd",
    "ddd",
    "dd",
    "d",
    "E",
    "HH",
    "H",
    "hh",
    "h",
    "mm",
    "m",
    "ss",
    "s",
    "A",
    "a",
    "GGGG",
    "WW",
    "W",
    "ZZ",
    "Z",
    "z",
)
CLOCK_FORMAT_PATTERN = (
    r"^(?:\[[^\[\]\x00-\x1f\x7f]*\]|"
    + "|".join(sorted(CLOCK_FORMAT_TOKENS, key=len, reverse=True))
    + r"|[^A-Za-z\[\]\x00-\x1f\x7f])+$"
)
_FORMAT_RE = re.compile(CLOCK_FORMAT_PATTERN)
_ZONE_RE = re.compile(r"(?:[A-Za-z0-9_+.-]+/)*[A-Za-z0-9_+.-]+")


def valid_clock_format(value):
    return (
        isinstance(value, str)
        and 0 < len(value) <= 128
        and bool(_FORMAT_RE.fullmatch(value))
    )


def valid_clock_timezone(value):
    if not isinstance(value, str) or not 0 < len(value) <= 128:
        return False
    if value in ("main", "browser-local"):
        return True
    if value.lower() in ("local", "host") or not _ZONE_RE.fullmatch(value):
        return False
    from .safety_foundation import validate_timezone

    return validate_timezone(value)[0]


def _raw_clock(config):
    web = config.get("web") if isinstance(config, dict) else None
    web = web if isinstance(web, dict) else {}
    nested = web.get("top_clock")
    raw = dict(nested) if isinstance(nested, dict) else {}
    for key in CLOCK_KEYS:
        if "top_clock." + key in web:
            raw[key] = web["top_clock." + key]
    return raw


def valid_clock_value(key, value):
    if key == "format":
        return valid_clock_format(value)
    if key == "timezone":
        return valid_clock_timezone(value)
    entry = CONFIG_REGISTRY["web.top_clock." + key]
    if entry["type"] == "boolean":
        return isinstance(value, bool)
    return isinstance(value, str) and value in entry["allowed_values"]


def invalid_clock_paths(config):
    web = config.get("web") if isinstance(config, dict) else None
    if (
        isinstance(web, dict)
        and "top_clock" in web
        and not isinstance(web["top_clock"], dict)
    ):
        return ["web.top_clock"]
    return [
        "web.top_clock." + key
        for key, value in _raw_clock(config).items()
        if key in CLOCK_KEYS and not valid_clock_value(key, value)
    ]


def public_clock_config(config, main_config=None):
    """Expose only validated clock fields and the active main timezone basis."""
    from .timezone_policy import now as timezone_now, resolve_timezone_name

    raw = _raw_clock(config)
    result = {}
    for key in CLOCK_KEYS:
        default = CONFIG_REGISTRY["web.top_clock." + key]["default"]
        value = raw.get(key, default)
        result[key] = value if valid_clock_value(key, value) else default
    main = config if main_config is None else main_config
    main_zone = resolve_timezone_name(main)
    result["main_timezone"] = main_zone
    result["resolved_timezone"] = (
        main_zone if result["timezone"] == "main" else result["timezone"]
    )
    if main_zone.lower() in ("local", "host"):
        # The shared policy can fall back to a host-local tzinfo without an IANA
        # name. Publish its offset, never substitute the viewer's local zone.
        offset = timezone_now(main_zone).utcoffset()
        result["main_utc_offset_minutes"] = (
            int(offset.total_seconds() / 60) if offset else 0
        )
    return result
