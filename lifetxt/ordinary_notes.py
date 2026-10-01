"""Shared ordinary/user-facing Note projection over unchanged Format N Items."""

import hashlib
import json
from datetime import datetime, time

from .agenda import item_time_matches
from .native_history import is_item_event
from .personal_context import is_personal_context_item
from .progress_history import is_progress_event
from .ticket_activity import is_ticket_event, is_time_entry
from .timeutil import comparison_datetime, parse_date, parse_date_or_datetime
from .web_read_service import sort_items

DEFAULT_LIMIT = 5
MAX_LIMIT = 100


def is_ordinary_note(item):
    """Exclude only authoritative person/history/ticket/progress conventions."""
    return item.kind == "N" and not (
        is_personal_context_item(item, person=None)
        or is_item_event(item)
        or is_ticket_event(item)
        or is_time_entry(item)
        or is_progress_event(item)
    )


def _date_context(value):
    if value in (None, ""):
        return None
    result = parse_date(str(value))
    if result is None:
        raise ValueError("date must be a valid YYYY-MM-DD date.")
    return result


def _timestamp(item, key):
    values = item.details.get(key) or []
    parsed = parse_date_or_datetime(str(values[0])) if values else None
    return comparison_datetime(parsed) if parsed is not None else datetime.min


def _stable_key(item):
    return (
        str((item.details.get("id") or [""])[0]),
        item.title,
        json.dumps(item.details, sort_keys=True, ensure_ascii=False),
        item.status,
        bool(getattr(item, "generated", False)),
        str(getattr(item, "source", None) or ""),
        item.line or 0,
    )


def select_ordinary_notes(items, date=None, sort="relevance", order="desc"):
    """Classify before sorting. Selected-day association, updated, then created.

    Without useful metadata, ID/title/content provide a deterministic fallback.
    Explicit alternate sorts use the existing item sort contract.
    """
    selected_date = _date_context(date)
    if order not in ("asc", "desc"):
        raise ValueError("order must be asc or desc.")
    rows = sorted((item for item in items if is_ordinary_note(item)), key=_stable_key)
    if sort != "relevance":
        if sort not in ("title", "line", "updated", "created"):
            raise ValueError("sort must be relevance, title, line, updated or created.")
        return sort_items(rows, sort, order)
    rows.sort(key=lambda item: _timestamp(item, "created"), reverse=True)
    rows.sort(key=lambda item: _timestamp(item, "updated"), reverse=True)
    if selected_date is not None:
        start = datetime.combine(selected_date, time.min)
        end = datetime.combine(selected_date, time.max)
        rows.sort(key=lambda item: not bool(item_time_matches(item, start, end)))
    return rows


def ordinary_notes_page(
    items, date=None, offset=0, limit=DEFAULT_LIMIT, sort="relevance", order="desc"
):
    """Return a bounded Item page and transport-neutral pagination metadata."""
    if any(
        isinstance(value, bool) or not isinstance(value, (int, str))
        for value in (offset, limit)
    ):
        raise ValueError("offset and limit must be integers.")
    try:
        offset, limit = int(offset), int(limit)
    except (TypeError, ValueError):
        raise ValueError("offset and limit must be integers.") from None
    if offset < 0 or not 1 <= limit <= MAX_LIMIT:
        raise ValueError("offset must be >= 0 and limit must be between 1 and 100.")
    rows = select_ordinary_notes(items, date=date, sort=sort, order=order)
    revision = hashlib.sha256(
        json.dumps([_stable_key(item) for item in rows], ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    page = rows[offset : offset + limit]
    next_offset = offset + len(page)
    has_more = next_offset < len(rows)
    return {
        "items": page,
        "count": len(page),
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "has_more": has_more,
        "next_offset": next_offset if has_more else None,
        "date": str(_date_context(date)) if date not in (None, "") else None,
        "sort": sort,
        "order": "desc" if sort == "relevance" else order,
        "revision": revision,
    }
