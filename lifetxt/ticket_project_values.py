"""Value normalization helpers for ticket/project reports."""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, List, Mapping, Optional, Tuple

try:
    from .tickets import DEFAULT_STATUS_MAP, TERMINAL_STATUSES
except ImportError:  # pragma: no cover - isolated module tests
    DEFAULT_STATUS_MAP = {
        "new": "[ ]", "triaged": "[ ]", "assigned": "[ ]",
        "in_progress": "[/]", "review": "[/]", "testing": "[/]",
        "needs_info": "[?]", "blocked": "[?]", "deferred": "[>]",
        "resolved": "[x]", "closed": "[x]", "rejected": "[-]",
        "duplicate": "[-]", "wont_fix": "[-]",
    }
    TERMINAL_STATUSES = ("resolved", "closed", "rejected", "duplicate", "wont_fix")

REPORT_SCHEMA = "ticket-project-report-v1"
DEFAULT_STALE_DAYS = 14
DEFAULT_HIGH_SEVERITIES = frozenset(("blocker", "critical"))
DEFAULT_TERMINAL_STATUSES = frozenset(tuple(TERMINAL_STATUSES) + ("done", "cancelled", "canceled"))
STATUS_ORDER = ("new", "open") + tuple(key for key in DEFAULT_STATUS_MAP if key != "new") + ("done", "cancelled", "unknown")
PRIORITY_ORDER = {
    "immediate": 0, "urgent": 0, "highest": 0, "critical": 0, "high": 1,
    "normal": 2, "medium": 2, "low": 3, "lowest": 4,
}
_DURATION_TOKEN = re.compile(r"(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>w|d|h|m)", re.IGNORECASE)
_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def attr(item: Any, *names: str, **kwargs: Any) -> Any:
    default = kwargs.get("default")
    if isinstance(item, Mapping):
        for name in names:
            if name in item:
                return item[name]
        return default
    for name in names:
        if hasattr(item, name):
            return getattr(item, name)
    return default


def details(item: Any) -> Mapping[str, Any]:
    value = attr(item, "details", default={})
    return value if isinstance(value, Mapping) else {}


def detail_values(item: Any, key: str) -> List[str]:
    value = details(item).get(key, [])
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(entry).strip() for entry in value if str(entry).strip()]
    text = str(value).strip()
    return [text] if text else []


def detail_first(item: Any, key: str, default: str = "") -> str:
    values = detail_values(item, key)
    return values[0] if values else default


def item_type(item: Any) -> str:
    return str(attr(item, "kind", "item_type", "type_code", "type", default="")).strip()


def item_status(item: Any) -> str:
    return str(attr(item, "status", default="")).strip()


def item_title(item: Any) -> str:
    return str(attr(item, "title", default="")).strip()


def is_ticket(item: Any) -> bool:
    records = set(value.lower() for value in detail_values(item, "record"))
    return item_type(item).upper() == "T" and "ticket" in records


def ticket_id(item: Any) -> str:
    return detail_first(item, "id")


def ticket_project(item: Any) -> str:
    return detail_first(item, "project", "(unassigned-project)")


def normalize_status(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def ticket_status(item: Any) -> str:
    detailed = normalize_status(detail_first(item, "ticket_status"))
    if detailed:
        return detailed
    coarse = item_status(item).lower()
    if coarse in ("[x]", "[done]", "done", "x"):
        return "done"
    if coarse in ("[-]", "[c]", "cancelled", "canceled"):
        return "cancelled"
    if coarse in ("[/]", "[~]", "in_progress"):
        return "in_progress"
    if coarse in ("[!]", "blocked"):
        return "blocked"
    if coarse in ("[?]", "needs_info"):
        return "needs_info"
    if coarse in ("[>]", "deferred"):
        return "deferred"
    if coarse in ("[ ]", "open", ""):
        return "open"
    return "unknown"


def ticket_is_terminal(item: Any, terminal_statuses: Iterable[str] = DEFAULT_TERMINAL_STATUSES) -> bool:
    return ticket_status(item) in set(normalize_status(value) for value in terminal_statuses)


def parse_datetime(value: str) -> Optional[datetime]:
    """Parse a conservative ISO date/datetime and normalize it to UTC."""
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+0000"
    elif len(normalized) >= 6 and normalized[-6] in ("+", "-") and normalized[-3] == ":":
        normalized = normalized[:-3] + normalized[-2:]
    formats = (
        "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M%z",
        "%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M%z",
        "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    )
    parsed = None
    for format_string in formats:
        try:
            parsed = datetime.strptime(normalized, format_string)
            break
        except ValueError:
            continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_duration_hours(value: str) -> Optional[float]:
    """Parse plain hours or compact w/d/h/m values into hours."""
    text = str(value or "").strip().lower()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    position, total, matched = 0, 0.0, False
    factors = {"w": 40.0, "d": 8.0, "h": 1.0, "m": 1.0 / 60.0}
    for match in _DURATION_TOKEN.finditer(text):
        if text[position:match.start()].strip():
            return None
        matched = True
        total += float(match.group("number")) * factors[match.group("unit").lower()]
        position = match.end()
    if not matched or text[position:].strip():
        return None
    return total


def reference_time(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def last_activity(item: Any) -> Optional[datetime]:
    for key in ("updated", "modified", "changed", "created", "opened"):
        parsed = parse_datetime(detail_first(item, key))
        if parsed is not None:
            return parsed
    return None


def due_time(item: Any) -> Optional[datetime]:
    for key in ("due", "deadline"):
        raw = detail_first(item, key)
        parsed = parse_datetime(raw)
        if parsed is not None:
            return parsed + timedelta(days=1) if _DATE_ONLY.match(raw.strip()) else parsed
    return None


def ticket_row(item: Any) -> Mapping[str, Any]:
    estimate = parse_duration_hours(detail_first(item, "est") or detail_first(item, "estimate"))
    elapsed = parse_duration_hours(detail_first(item, "elapsed"))
    return {
        "id": ticket_id(item), "title": item_title(item), "project": ticket_project(item),
        "status": ticket_status(item), "tracker": detail_first(item, "tracker", "(unspecified)"),
        "priority": detail_first(item, "priority", "(unspecified)"),
        "severity": detail_first(item, "severity", "(unspecified)"),
        "assignee": detail_first(item, "assignee"), "reporter": detail_first(item, "reporter"),
        "component": detail_first(item, "component", "(unspecified)"),
        "due": detail_first(item, "due") or detail_first(item, "deadline"),
        "updated": detail_first(item, "updated") or detail_first(item, "modified") or detail_first(item, "changed"),
        "estimate_hours": estimate, "elapsed_hours": elapsed, "depends_on": detail_values(item, "depends_on"),
    }


def sort_key(row: Mapping[str, Any]) -> Tuple[Any, ...]:
    due = parse_datetime(str(row.get("due") or ""))
    return (
        PRIORITY_ORDER.get(str(row.get("priority") or "").lower(), 10),
        due or datetime.max.replace(tzinfo=timezone.utc),
        str(row.get("id") or ""), str(row.get("title") or "").lower(),
    )
