"""Per-recipient delivery state and acknowledgement policy for messages.

Delivery state is derived authoritatively from the message record itself: a
Message item lists its recipients and records who acknowledged (``ack:``) or
read (``read:``) it. That keeps the single source of truth in life.txt and
avoids a second store that could drift. Each recipient maps to a
``delivery-state-v1`` record (pending / read / acknowledged / skipped).

Acknowledgement policy (``any``, ``all``, or an explicit count) decides when a
multi-recipient message is complete. One recipient acknowledging must not
complete an ``all`` message on its own.
"""

from __future__ import unicode_literals

from collections import OrderedDict


DELIVERY_VERSION = "1"
STATES = ("pending", "delivered", "failed", "read", "acknowledged", "skipped")


def _values(item, key):
    return [str(v) for v in item.details.get(key, [])]


def _first(item, key, default=None):
    values = item.details.get(key)
    return values[0] if values else default


def message_recipients(item):
    return _values(item, "recipient")


def delivery_states(item, config=None, resolver=None, updated_at=None):
    """Return per-recipient ``delivery-state-v1`` records for a message item.

    ``resolver`` optionally expands team/group recipients into people (pass
    :func:`lifetxt.groups.resolve_recipients`-style output); by default the
    literal ``recipient:`` values are used.
    """
    message_id = _first(item, "id") or ""
    acknowledged = set(_values(item, "ack"))
    read = set(_values(item, "read"))
    skipped = set(_values(item, "skip"))
    updated_at = updated_at or _first(item, "updated") or _first(item, "created") or ""

    recipients = message_recipients(item)
    if resolver is not None and config is not None:
        resolved = resolver(config, recipients)
        recipients = resolved.get("recipients", recipients)

    rows = []
    for recipient in recipients:
        if recipient in skipped:
            state = "skipped"
        elif recipient in acknowledged:
            state = "acknowledged"
        elif recipient in read:
            state = "read"
        else:
            state = "pending"
        rows.append(
            OrderedDict(
                (
                    ("delivery_version", DELIVERY_VERSION),
                    ("message_id", message_id),
                    ("recipient", recipient),
                    ("state", state),
                    ("updated_at", updated_at),
                    ("error", None),
                )
            )
        )
    return rows


def acknowledgement_status(item, config=None, resolver=None, policy=None):
    """Return whether a message is complete under its acknowledgement policy."""
    states = delivery_states(item, config=config, resolver=resolver)
    policy = str(policy or _first(item, "ack_policy") or "any").lower()
    total = len(states)
    acknowledged = sum(1 for row in states if row["state"] == "acknowledged")
    skipped = sum(1 for row in states if row["state"] == "skipped")
    effective_total = total - skipped

    if policy == "all":
        required = effective_total
    elif policy == "any":
        required = 1 if effective_total else 0
    else:
        try:
            required = min(int(policy), effective_total)
        except (TypeError, ValueError):
            required = 1 if effective_total else 0
            policy = "any"

    complete = effective_total > 0 and acknowledged >= required
    return OrderedDict(
        (
            ("policy", policy),
            ("total", total),
            ("effective_total", effective_total),
            ("acknowledged", acknowledged),
            ("skipped", skipped),
            ("required", required),
            ("complete", complete),
            (
                "pending",
                [
                    row["recipient"]
                    for row in states
                    if row["state"] in ("pending", "read")
                ],
            ),
        )
    )


def delivery_summary(item, config=None, resolver=None, policy=None):
    states = delivery_states(item, config=config, resolver=resolver)
    counts = OrderedDict((state, 0) for state in STATES)
    for row in states:
        counts[row["state"]] += 1
    return OrderedDict(
        (
            ("message_id", _first(item, "id") or ""),
            ("title", item.title),
            ("recipient_count", len(states)),
            ("counts", counts),
            ("acknowledgement", acknowledgement_status(item, config, resolver, policy)),
            ("states", states),
        )
    )
