"""Opt-in contextual batch save; the legacy writer remains separate."""

import re

from . import mutation
from .batch_preview import PreviewInputError, review_batch
from .serializer import item_to_line
from .ids import id_key_from_config
from .workspace_context_snapshot import WorkspaceContextUnavailable


class BatchSaveError(ValueError):
    def __init__(self, status, code, **fields):
        self.status = status
        self.detail = {"error": code, "saved": 0, **fields}
        super().__init__(code)


def save_contextual_batch(payload, paths, writable_path, config, serialize_item):
    token = payload["context_token"]
    if not isinstance(token, str) or not re.fullmatch(
        r"batch-preview-v1:[0-9a-f]{64}", token
    ):
        raise BatchSaveError(400, "CONTEXT_TOKEN_INVALID")
    expected = payload.get("expected_source_revision") or payload.get(
        "expected_revision"
    )
    if not expected:
        raise BatchSaveError(428, "REVISION_REQUIRED")
    try:
        review, batch, context = review_batch(
            payload["text"], paths, writable_path, config, False, serialize_item
        )
    except PreviewInputError as exc:
        raise BatchSaveError(exc.status, exc.code) from None
    except WorkspaceContextUnavailable as exc:
        raise BatchSaveError(
            409, "CONTEXT_CHANGED", reason=exc.reason, repreview_required=True
        ) from None
    except (RecursionError, UnicodeError):
        raise BatchSaveError(
            409, "CONTEXT_CHANGED", reason="review_unavailable", repreview_required=True
        ) from None
    # A stale review wins over duplicates introduced since that review. No
    # previous snapshot is retained: a hash mismatch cannot identify which
    # source changed, so do not invent more specific change categories.
    if review["context_token"] != token:
        raise BatchSaveError(
            409,
            "CONTEXT_CHANGED",
            reason="context_or_input_changed",
            repreview_required=True,
        )
    if not review["ok"]:
        code = (
            "DUPLICATE_ID"
            if any(row["code"] == "DUPLICATE_ID" for row in review["diagnostics"])
            else "VALIDATION_ERROR"
        )
        raise BatchSaveError(422, code, diagnostics=review["diagnostics"])
    if expected != context.writable_revision:
        raise BatchSaveError(409, "CONFLICT")
    from .surface_runtime import active_transaction

    transaction = active_transaction()
    if (
        transaction is not None
        and transaction.expected_hash != context.writable_revision
    ):
        raise BatchSaveError(409, "CONFLICT")
    addition = "\n".join(item_to_line(item) for item in batch) + "\n"
    # This is one destination CAS, not a workspace-wide transaction. Another
    # source can change after the final captured scan and before this write.
    try:
        result = mutation.write_text(
            writable_path,
            transform=lambda current: (
                current
                + ("\n" if current and not current.endswith(("\n", "\r")) else "")
                + addition
            ),
            expected_hash=context.writable_revision,
            operation="web contextual batch create",
        )
    except mutation.MutationConflict:
        raise BatchSaveError(409, "CONFLICT") from None
    for item in batch:
        item.source = writable_path
    key = id_key_from_config(config)
    return {
        "ok": True,
        "count": len(batch),
        "saved": len(batch),
        "source_revision": result.snapshot.content_hash,
        "items": [serialize_item(item, writable_path, key) for item in batch],
    }
