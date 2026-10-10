"""Shared contextual native batch review over exact captured source bytes."""

import copy
import hashlib
import os

from .diagnostic_contract import diagnostics_to_output
from .ids import duplicate_id_diagnostics, id_key_from_config
from .links import reference_diagnostics
from .model import Diagnostic
from .parser import parse_text
from .workspace import config_base_dir
from .workspace_context_snapshot import (
    WorkspaceContextUnavailable,
    read_workspace_context,
)


class PreviewInputError(ValueError):
    def __init__(self, status, code):
        self.status = status
        self.code = code
        super().__init__(code)


def review_batch(text, paths, writable_path, config, read_only, serialize_item):
    """Return public review plus private parsed records and captured context."""
    if not isinstance(text, str):
        raise PreviewInputError(400, "TEXT_REQUIRED")
    if len(text.encode("utf-8")) > 512 * 1024:
        raise PreviewInputError(413, "INPUT_TOO_LARGE")
    config = copy.deepcopy(config)
    key = id_key_from_config(config)
    batch_result = parse_text(text, id_key=key, check_ids=False, check_references=False)
    batch, diagnostics = batch_result
    if batch_result.format_version_state == "unsupported":
        raise PreviewInputError(422, "UNSUPPORTED_FORMAT")
    if len(batch) > 500:
        raise PreviewInputError(422, "TOO_MANY_RECORDS")
    # The snapshot helper captures writable bytes separately, but its text reader
    # exposes only effective read sources. Avoid silently omitting that context.
    canonical = lambda path: os.path.normcase(os.path.realpath(os.path.abspath(path)))
    if not writable_path or canonical(writable_path) not in {
        canonical(p) for p in paths
    }:
        raise WorkspaceContextUnavailable("source_resolution_required")
    configured_paths = config.get("paths") or []
    if isinstance(configured_paths, str):
        configured_paths = [configured_paths]
    dynamic_legacy = any(
        isinstance(path, str)
        and (
            any(char in path for char in "*?[")
            or os.path.isdir(os.path.join(config_base_dir(config), path))
        )
        for path in configured_paths
    )
    context = read_workspace_context(
        paths,
        writable_path,
        config,
        check_manifest=bool(config.get("workspaces")) or dynamic_legacy,
    )
    existing = []
    for index, path in enumerate(paths, 1):
        result = parse_text(
            context.text_for_path(path),
            id_key=key,
            check_ids=False,
            check_references=False,
        )
        records, source_diagnostics = result
        label = "workspace:%d" % index
        for record in records:
            record.source = label
        for diagnostic in source_diagnostics:
            diagnostic.source = label
        if result.format_version_state == "unsupported":
            source_diagnostics.append(
                Diagnostic(
                    "error",
                    "UNSUPPORTED_FORMAT_VERSION",
                    "Workspace source uses an unsupported Format version.",
                    None,
                    None,
                    label,
                )
            )
        existing.extend(records)
        diagnostics.extend(source_diagnostics)
    for record in batch:
        record.source = "batch"
    for diagnostic in diagnostics:
        if not diagnostic.source:
            diagnostic.source = "batch"
    combined = existing + batch
    diagnostics.extend(duplicate_id_diagnostics(combined, key=key))
    diagnostics.extend(reference_diagnostics(combined, key=key))
    output = diagnostics_to_output(diagnostics)
    for row in output:
        row["scope"] = "batch" if row.get("source") == "batch" else "workspace"
        if row["code"] == "W213":
            row["core_code"] = "W213"
            row["code"] = "DUPLICATE_ID"
            row["severity"] = "error"
    items = []
    for record in batch:
        data = serialize_item(record, None, key)
        data.update(source=None, editable=False, generated=False)
        items.append(data)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    token = (
        "batch-preview-v1:"
        + hashlib.sha256(
            (context.fingerprint + ":" + digest).encode("ascii")
        ).hexdigest()
    )
    response = {
        "ok": bool(batch) and not any(row["severity"] == "error" for row in output),
        "item_count": len(batch),
        "items": items,
        "diagnostics": output,
        "context_token": token,
        "input_digest": digest,
        "source_revision": context.writable_revision,
        "read_only": bool(read_only),
        "review_scope": {
            "context": context.scope,
            "source_count": len(paths),
            "record_count": len(combined),
            "workspace_record_count": len(existing),
            "batch_record_count": len(batch),
            "workspace_records_returned": False,
            "omitted_records": 0,
            "omitted_diagnostics": 0,
            "checks": ["syntax", "schema", "ids", "references", "dependency_cycles"],
            "limitations": [
                "human_meaning_review",
                "no_cross_source_atomicity",
                "external_config_requires_restart",
            ],
        },
    }

    return response, batch, context


def preview_batch(text, paths, writable_path, config, read_only, serialize_item):
    return review_batch(text, paths, writable_path, config, read_only, serialize_item)[
        0
    ]
