"""Read-only Storage Health facts and conservative recommendations."""

import os
import time

from .parser import parse_text


SCHEMA = "lifetxt-storage-health-v1"
DEFAULT_ACTIVE_BYTES = 16 * 1024 * 1024
DEFAULT_ACTIVE_RECORDS = 200_000


def measure(paths, archive_paths=(), active_threshold=DEFAULT_ACTIVE_BYTES,
            record_threshold=DEFAULT_ACTIVE_RECORDS):
    """Return explainable, read-only storage facts for the supplied sources."""
    started = time.perf_counter()
    active_paths = [os.fspath(path) for path in paths]
    archived = [os.fspath(path) for path in archive_paths]

    def inspect(source_paths):
        bytes_total = 0
        records = 0
        diagnostics = 0
        for path in source_paths:
            if not os.path.exists(path):
                continue
            bytes_total += os.path.getsize(path)
            with open(path, "r", encoding="utf-8") as handle:
                items, found = parse_text(handle.read())
            records += len(items)
            diagnostics += len(found)
        return bytes_total, records, diagnostics

    active_bytes, active_records, active_diagnostics = inspect(active_paths)
    archive_bytes, archive_records, archive_diagnostics = inspect(archived)
    reasons = []
    if active_bytes >= active_threshold:
        reasons.append("active_bytes_at_or_above_threshold")
    if active_records >= record_threshold:
        reasons.append("active_records_at_or_above_threshold")
    if active_diagnostics:
        reasons.append("active_sources_have_diagnostics")
    status = "maintenance_recommended" if reasons else "healthy"
    return {
        "schema": SCHEMA,
        "active_bytes": active_bytes,
        "active_records": active_records,
        "active_sources": len(active_paths),
        "archive_bytes": archive_bytes,
        "archive_records": archive_records,
        "archive_sources": len(archived),
        "active_diagnostics": active_diagnostics,
        "archive_diagnostics": archive_diagnostics,
        "parse_duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "status": status,
        "reasons": reasons,
        "thresholds": {
            "active_bytes": active_threshold,
            "active_records": record_threshold,
        },
        "mutated": False,
    }
