"""Revision-required operation contracts for high-risk lifetxt writes.

These helpers deliberately refuse blind replacement writes.  A caller must read a
:class:`lifetxt.mutation.TextSnapshot` first and pass its exact content hash.  The
operation name is stable so conflicts and lock metadata identify the originating
workflow rather than the generic write primitive.
"""

from __future__ import unicode_literals

from .mutation import MISSING_HASH, mutate_json, mutate_text, write_text


class ExpectedRevisionRequired(ValueError):
    """Raised when a safety-critical operation omits its revision precondition."""


OPERATION_NAMES = (
    "quick_capture",
    "item_update",
    "mcp_write",
    "notification_acknowledgement",
    "timer_state",
    "archive",
    "undo",
)


def require_expected_hash(expected_hash, operation):
    if expected_hash is None or str(expected_hash).strip() == "":
        raise ExpectedRevisionRequired(
            "%s requires expected_hash. Read the target snapshot and retry with "
            "its exact content hash." % operation
        )
    return expected_hash


def quick_capture(path, line, expected_hash):
    """Append one already-serialized record without accepting a stale snapshot."""
    expected_hash = require_expected_hash(expected_hash, "quick_capture")
    value = str(line).rstrip("\r\n")

    def transform(current):
        prefix = "" if not current or current.endswith(("\n", "\r")) else "\n"
        return current + prefix + value + "\n"

    return mutate_text(
        path,
        transform,
        expected_hash=expected_hash,
        operation="quick_capture",
        create=expected_hash == MISSING_HASH,
    )


def item_update(path, transform, expected_hash):
    """Apply an item-level semantic transform to the current in-lock text."""
    return _semantic_text_operation(path, transform, expected_hash, "item_update")


def mcp_write(path, transform, expected_hash):
    """Apply an MCP-proposed semantic transform with a mandatory revision."""
    return _semantic_text_operation(path, transform, expected_hash, "mcp_write")


def notification_acknowledgement(path, transform, expected_hash):
    """Persist acknowledgement state only against the revision the client read."""
    return _semantic_text_operation(
        path, transform, expected_hash, "notification_acknowledgement"
    )


def timer_state(path, transform, expected_hash, default=None):
    """Mutate timer JSON state under the same CAS and sidecar-lock contract."""
    expected_hash = require_expected_hash(expected_hash, "timer_state")
    return mutate_json(
        path,
        transform,
        expected_hash=expected_hash,
        operation="timer_state",
        create=expected_hash == MISSING_HASH,
        default={} if default is None else default,
        sort_keys=True,
    )


def archive(path, transform, expected_hash):
    """Apply an archive semantic transform without overwriting newer content."""
    return _semantic_text_operation(path, transform, expected_hash, "archive")


def undo(path, replacement_text, expected_hash):
    """Restore a snapshot only when the current file is the revision being undone."""
    expected_hash = require_expected_hash(expected_hash, "undo")
    return write_text(
        path,
        replacement_text,
        expected_hash=expected_hash,
        operation="undo",
        create=False,
    )


def _semantic_text_operation(path, transform, expected_hash, operation):
    if not callable(transform):
        raise TypeError("%s transform must be callable." % operation)
    expected_hash = require_expected_hash(expected_hash, operation)
    return mutate_text(
        path,
        transform,
        expected_hash=expected_hash,
        operation=operation,
        create=expected_hash == MISSING_HASH,
    )
