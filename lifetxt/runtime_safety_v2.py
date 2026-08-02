"""Install the second-stage safety runtime without importing optional dependencies."""

from __future__ import unicode_literals

import os


_INSTALLED = False


def install_runtime_safety_v2():
    global _INSTALLED
    if _INSTALLED:
        return
    _install_schemas_and_diagnostics()
    _install_timezone_comparisons()
    _install_mcp_timezone_context()
    _install_web_revision_policy()
    _install_safe_multi_target_operations()
    _INSTALLED = True


def _install_schemas_and_diagnostics():
    from . import release_policy, safety_foundation
    from .schema_extensions_v2 import install_extended_schemas
    from .workspace_diagnostics import stable_file_diagnostics

    install_extended_schemas()
    safety_foundation.stable_diagnostics = stable_file_diagnostics
    release_policy.stable_diagnostics = stable_file_diagnostics


def _install_timezone_comparisons():
    from . import timeutil
    from .timezone_policy import comparison_datetime

    timeutil.comparison_datetime = comparison_datetime


def _install_mcp_timezone_context():
    from . import mcp
    from .safety_foundation import read_text_exact
    from .timezone_policy import resolve_timezone_name, timezone_context

    original = mcp.handle_request
    if getattr(original, "_lifetxt_timezone_context_v2", False):
        return

    def handle_request(request, context):
        config = getattr(context, "config", None) or {}
        path = getattr(context, "writable_path", None)
        text = ""
        if path and os.path.exists(path):
            try:
                text, _raw, _bom = read_text_exact(path)
            except OSError:
                text = ""
        name = resolve_timezone_name(config, text=text)
        with timezone_context(name):
            return original(request, context)

    handle_request._lifetxt_timezone_context_v2 = True
    mcp.handle_request = handle_request


def _install_web_revision_policy():
    from . import webapp
    from .revision_telemetry import store_from_config
    from .safety_foundation import read_text_exact
    from .timezone_policy import resolve_timezone_name, timezone_context

    original = webapp.create_app
    if getattr(original, "_lifetxt_persistent_revision_v2", False):
        return

    def create_app(paths=None, writable_path=None, config=None, read_only=False):
        normalized = [paths] if isinstance(paths, str) else list(paths or [])
        config_data = config or {}
        app = original(
            paths=normalized,
            writable_path=writable_path,
            config=config_data,
            read_only=read_only,
        )
        store = store_from_config(config_data, writable_path=app.state.writable_path)
        persisted = store.ensure()
        _sync_legacy_metric_state(app, persisted)
        app.state.revision_metrics_store = store
        app.state.revision_mode = store.mode
        text = ""
        if app.state.writable_path and os.path.exists(app.state.writable_path):
            try:
                text, _raw, _bom = read_text_exact(app.state.writable_path)
            except OSError:
                text = ""
        app.state.timezone_name = resolve_timezone_name(config_data, text=text)

        # Replace the compatibility endpoint with the persisted version-1 report.
        app.router.routes[:] = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/api/revision-metrics"
        ]

        @app.get("/api/revision-metrics")
        def revision_metrics_v2():
            report = store.snapshot()
            _sync_legacy_metric_state(app, report)
            return report

        @app.get("/api/revision-metrics/export")
        def revision_metrics_export():
            report = store.snapshot()
            report["metrics_revision"] = store.content_hash()
            return report

        @app.middleware("http")
        async def _persistent_revision_and_timezone_context(request, call_next):
            path = request.url.path
            method = request.method.upper()
            supplied = (
                "if-match" in request.headers
                or "x-lifetxt-expected-revision" in request.headers
            )
            life_write = _is_life_api_write(method, path)
            if store.mode == "required" and life_write and not supplied:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=428,
                    content={
                        "error": "PRECONDITION_REQUIRED",
                        "message": "Revision discovery and If-Match are required for this write.",
                        "revision_mode": "required",
                    },
                    headers={"X-Lifetxt-Revision-Mode": "required"},
                )
            before_total = store.snapshot().get("legacy_fallback_total", 0)
            with timezone_context(app.state.timezone_name):
                response = await call_next(request)
            if response.headers.get("X-Lifetxt-Legacy-Revision-Fallback") == "used":
                report = store.record_legacy_fallback(path)
                _sync_legacy_metric_state(app, report)
            else:
                report = store.snapshot()
                _sync_legacy_metric_state(app, report)
            response.headers["X-Lifetxt-Revision-Mode"] = store.mode
            response.headers["X-Lifetxt-Timezone"] = app.state.timezone_name
            if path.startswith("/api/revision-metrics"):
                response.headers["X-Lifetxt-Metrics-Revision"] = store.content_hash()
            # Guard against an inner compatibility counter changing without a
            # persisted event. The normal path records exactly once above.
            if response.headers.get(
                "X-Lifetxt-Legacy-Revision-Fallback"
            ) != "used" and app.state.revision_contract_metrics.get(
                "legacy_fallback_total", 0
            ) > report.get("legacy_fallback_total", before_total):
                _sync_legacy_metric_state(app, report)
            return response

        return app

    create_app._lifetxt_persistent_revision_v2 = True
    webapp.create_app = create_app


def _is_life_api_write(method, path):
    if method not in ("POST", "PUT", "PATCH", "DELETE"):
        return False
    if not path.startswith("/api/") or path.startswith("/api/git/"):
        return False
    return path not in (
        "/api/check-line",
        "/api/items/parse",
        "/api/shorthand/parse",
        "/api/timer",
        "/api/attachments",
        "/api/work-session",
    )


def _sync_legacy_metric_state(app, report):
    metrics = app.state.revision_contract_metrics
    metrics["legacy_fallback_enabled"] = bool(report.get("legacy_fallback_enabled"))
    metrics["legacy_fallback_total"] = int(report.get("legacy_fallback_total") or 0)
    metrics["legacy_fallback_by_path"] = dict(
        report.get("legacy_fallback_by_path") or {}
    )
    metrics["legacy_fallback_last_used"] = report.get("legacy_fallback_last_used")


def _install_safe_multi_target_operations():
    from . import safe_ops
    from .multi_target import (
        attachment_and_item_transaction,
        timer_and_item_transaction,
    )

    safe_ops.timer_and_item_transaction = timer_and_item_transaction
    safe_ops.attachment_and_item_transaction = attachment_and_item_transaction


def install_cli_timezone_context(cli_module):
    """Wrap legacy CLI main once so configured paths establish timezone context."""
    from .config import config_paths, load_config
    from .safety_foundation import read_text_exact
    from .timezone_policy import resolve_timezone_name, timezone_context

    current = cli_module.main
    if getattr(current, "_lifetxt_timezone_context_v2", False):
        return

    def main(argv=None):
        raw = list(argv or [])
        config_path = None
        for index, value in enumerate(raw):
            if value == "--config" and index + 1 < len(raw):
                config_path = raw[index + 1]
            elif value.startswith("--config="):
                config_path = value.split("=", 1)[1]
        config = load_config(config_path)
        candidates = []
        for value in raw:
            if value and not value.startswith("-") and os.path.exists(value):
                candidates.append(value)
        candidates.extend(config_paths(config))
        text = ""
        for path in candidates:
            if path and path != "-" and os.path.exists(path):
                try:
                    text, _raw, _bom = read_text_exact(path)
                    break
                except OSError:
                    continue
        name = resolve_timezone_name(config, text=text)
        with timezone_context(name):
            return current(argv)

    main._lifetxt_timezone_context_v2 = True
    cli_module.main = main
