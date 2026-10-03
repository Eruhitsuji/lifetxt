"""Minimal native Python Worker adapter for the #827 feasibility PoC."""

import json
import time
from datetime import datetime, timezone

try:
    from workers import Response, WorkerEntrypoint
except ModuleNotFoundError:  # CPython-only evidence harness; Workers supplies this SDK.
    class WorkerEntrypoint:
        pass

    class Response:
        @staticmethod
        def json(value, status=200):
            return {"status": status, "json": value}

_import_started = time.perf_counter()
import lifetxt
PACKAGE_ROOT_IMPORT_SECONDS = round(time.perf_counter() - _import_started, 6)
_shared_import_started = time.perf_counter()
from lifetxt.conversion import convert_text
from lifetxt.parser import parse_text
from lifetxt.priority_matrix import classify_item
from lifetxt.quick_input import resolve_quick_input
SHARED_IMPORT_SECONDS_AFTER_ROOT = round(time.perf_counter() - _shared_import_started, 6)

ENGINE_BASE_REVISION = "0d340f0e24b60d3ee6cd95186ac0fd9bec6b715a"


def _json(value, status=200):
    return Response.json(value, status=status)


def _diagnostic(value):
    return {
        "severity": getattr(value, "severity", None),
        "code": getattr(value, "code", None),
        "message": getattr(value, "message", str(value)),
        "line": getattr(value, "line", None),
        "column": getattr(value, "column", None),
    }


def check_text(text):
    started = time.perf_counter()
    items, diagnostics = parse_text(text)
    return {
        "valid": not any(getattr(d, "severity", None) == "error" for d in diagnostics),
        "items": len(items),
        "diagnostics": [_diagnostic(d) for d in diagnostics],
        "elapsed_seconds": round(time.perf_counter() - started, 6),
    }


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = request.url
        path = url.split("/", 3)[-1] if "/" in url else ""
        if path == "health":
            return _json({"ok": True})
        if path == "v1/info":
            return _json({
                "service": "lifetxt-public-api-poc",
                "engine_version": lifetxt.__version__,
                "runtime": "cloudflare-python-worker",
                "engine_base_revision": ENGINE_BASE_REVISION,
                "package_root_import_seconds": PACKAGE_ROOT_IMPORT_SECONDS,
                "shared_import_seconds_after_root": SHARED_IMPORT_SECONDS_AFTER_ROOT,
            })
        if path == "v1/check" and request.method == "POST":
            body = await request.json()
            text = body.get("text") if isinstance(body, dict) else None
            if not isinstance(text, str):
                return _json({"error": "text must be a string"}, status=400)
            return _json(check_text(text))
        return _json({"error": "not found"}, status=404)


def shared_core_smoke(text):
    """Non-contractual smoke calls used by the evidence harness."""
    result = convert_text("life", "json", text)
    quick = resolve_quick_input("Review 日本語")
    items, diagnostics = parse_text(text)
    matrix = (
        classify_item(items[0], reference_time=datetime(2026, 10, 3, tzinfo=timezone.utc))
        if items
        else None
    )
    return {
        "conversion": json.loads(result.content),
        "quick_input": quick.__class__.__name__,
        "priority_matrix": matrix,
        "diagnostics": len(diagnostics),
    }
