"""Compatibility edges for the public-surface runtime adapter.

The public protocols gain strict revision contracts without changing internal
Python helper semantics. MCP's direct ``call_tool`` remains an embeddable API;
JSON-RPC ``tools/call`` is the strict public boundary. Web clients enter strict
mode by discovering `/api/revision` or `/api/capabilities`, while legacy clients
receive a server-captured revision and a deprecation warning until the planned
compatibility removal.
"""

import datetime

from . import mutation
from .mutation import MISSING_HASH, MutationConflict
from .surface_runtime import (
    OPERATION_REGISTRY,
    _ORIGINALS,
    active_transaction,
    current_revision,
    etag_value,
    normalize_revision,
    transaction_scope,
)


_INSTALLED = False
_REVISION_COOKIE = "lifetxt_revision_contract"


def install_runtime_compatibility():
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_mutation_signature()
    _patch_capability_matrix()
    _scope_mcp_contract_to_jsonrpc()
    _patch_mcp_expected_hash()
    _patch_web_path_shape_and_reads()
    _INSTALLED = True


def _patch_mutation_signature():
    current = mutation.apply_text_mutation
    if getattr(current, "_lifetxt_signature_compatible", False):
        return

    def compatible_apply_text_mutation(
        path,
        operation,
        expected_hash=None,
        lock_timeout=mutation.DEFAULT_LOCK_TIMEOUT,
        poll_interval=mutation.DEFAULT_POLL_INTERVAL,
        stale_lock_after=mutation.DEFAULT_STALE_LOCK_AFTER,
        encoding="utf-8",
    ):
        return current(
            path,
            operation,
            expected_hash=expected_hash,
            lock_timeout=lock_timeout,
            poll_interval=poll_interval,
            stale_lock_after=stale_lock_after,
            encoding=encoding,
        )

    compatible_apply_text_mutation._lifetxt_signature_compatible = True
    mutation.apply_text_mutation = compatible_apply_text_mutation


def _patch_capability_matrix():
    from . import surface_runtime

    # Timer state and attachment side effects still need their own multi-path
    # revision contracts. Do not advertise stronger guarantees than exist.
    OPERATION_REGISTRY["timer"]["revision_required"] = False
    OPERATION_REGISTRY["attachments"]["revision_required"] = False

    def operation_matrix():
        rows = []
        for name, spec in OPERATION_REGISTRY.items():
            rows.append(
                {
                    "operation": name,
                    "write": bool(spec["write"]),
                    "revision_required": bool(
                        spec.get("revision_required", spec["write"])
                    ),
                    "surfaces": list(spec["surfaces"]),
                }
            )
        return rows

    surface_runtime.operation_matrix = operation_matrix


def _scope_mcp_contract_to_jsonrpc():
    """Keep direct Python calls compatible and enforce CAS at JSON-RPC."""
    from . import mcp

    strict_call_tool = mcp.call_tool
    if getattr(strict_call_tool, "_lifetxt_jsonrpc_scoped", False):
        return
    legacy_call_tool = _ORIGINALS.get("mcp_call_tool", strict_call_tool)
    original_handle_request = mcp.handle_request

    def handle_request(request, context):
        if isinstance(request, dict) and request.get("method") == "tools/call":
            request_id = request.get("id")
            params = request.get("params") or {}
            try:
                name = params.get("name")
                arguments = params.get("arguments") or {}
                result = strict_call_tool(name, arguments, context)
                return mcp._jsonrpc_result(request_id, mcp._tool_result(result))
            except ValueError as exc:
                return mcp._jsonrpc_error(request_id, -32000, str(exc))
            except Exception as exc:
                return mcp._jsonrpc_error(request_id, -32603, str(exc))
        return original_handle_request(request, context)

    strict_call_tool._lifetxt_jsonrpc_scoped = True
    mcp.call_tool = legacy_call_tool
    mcp.handle_request = handle_request


def _patch_mcp_expected_hash():
    from . import mcp

    original = mcp._check_expected_hash
    if getattr(original, "_lifetxt_revision_aware", False):
        return

    def check_expected_hash(context, args):
        supplied = "expected_file_hash" in args or "file_hash" in args
        raw = (
            args.get("expected_file_hash")
            if "expected_file_hash" in args
            else args.get("file_hash")
        )
        transaction = active_transaction()
        if transaction is not None and transaction.matches(context.writable_path):
            if not supplied:
                return original(context, args)
            expected = normalize_revision(raw, supplied=True)
            if expected != transaction.expected_hash:
                raise MutationConflict(
                    context.writable_path,
                    expected,
                    transaction.expected_hash,
                    operation="mcp.precondition",
                )
            return None
        if supplied and normalize_revision(raw, supplied=True) == MISSING_HASH:
            current = mcp.file_hash(context.writable_path)
            if current == "":
                return None
        return original(context, args)

    check_expected_hash._lifetxt_revision_aware = True
    mcp._check_expected_hash = check_expected_hash


def _patch_web_path_shape_and_reads():
    from . import webapp

    original = webapp.create_app
    if getattr(original, "_lifetxt_path_shape_compatible", False):
        return

    def create_app(paths=None, writable_path=None, config=None, read_only=False):
        normalized = [paths] if isinstance(paths, str) else paths
        app = original(
            paths=normalized,
            writable_path=writable_path,
            config=config,
            read_only=read_only,
        )
        app.state.revision_contract_metrics = {
            "legacy_fallback_enabled": True,
            "legacy_fallback_total": 0,
            "legacy_fallback_by_path": {},
            "legacy_fallback_last_used": None,
        }

        @app.get("/api/revision-metrics")
        def revision_metrics():
            metrics = app.state.revision_contract_metrics
            return {
                "legacy_fallback_enabled": metrics["legacy_fallback_enabled"],
                "legacy_fallback_total": metrics["legacy_fallback_total"],
                "legacy_fallback_by_path": dict(metrics["legacy_fallback_by_path"]),
                "legacy_fallback_last_used": metrics["legacy_fallback_last_used"],
                "removal_condition": "Remove the fallback after supported clients report zero usage during the documented migration window.",
            }

        @app.middleware("http")
        async def _compatibility_and_read_snapshot_contract(request, call_next):
            method = request.method.upper()
            path = request.url.path
            unsafe = method in ("POST", "PUT", "PATCH", "DELETE")
            life_api_write = (
                unsafe
                and path.startswith("/api/")
                and not path.startswith("/api/git/")
                and path
                not in (
                    "/api/check-line",
                    "/api/items/parse",
                    "/api/shorthand/parse",
                    "/api/timer",
                )
            )
            strict = request.cookies.get(_REVISION_COOKIE) == "1" or str(
                request.headers.get("x-lifetxt-require-revision") or ""
            ).lower() in ("1", "true", "yes", "on")
            supplied = (
                "if-match" in request.headers
                or "x-lifetxt-expected-revision" in request.headers
            )
            compatibility_revision = None
            if life_api_write and not strict and not supplied:
                compatibility_revision = current_revision(app.state.writable_path)
                headers = list(request.scope.get("headers") or [])
                headers.append(
                    (b"if-match", etag_value(compatibility_revision).encode("ascii"))
                )
                request.scope["headers"] = headers
                metrics = app.state.revision_contract_metrics
                metrics["legacy_fallback_total"] += 1
                metrics["legacy_fallback_by_path"][path] = (
                    metrics["legacy_fallback_by_path"].get(path, 0) + 1
                )
                metrics["legacy_fallback_last_used"] = (
                    datetime.datetime.now(datetime.timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z")
                )

            if method in ("GET", "HEAD") and path.startswith("/api/"):
                with transaction_scope(
                    app.state.writable_path,
                    expected_hash=None,
                    operation="web.read",
                    require_revision=False,
                ) as transaction:
                    response = await call_next(request)
                    revision = transaction.before.content_hash
                    response.headers["ETag"] = etag_value(revision)
                    response.headers["X-Lifetxt-Revision"] = revision
            else:
                response = await call_next(request)

            if compatibility_revision is not None:
                response.headers["Warning"] = (
                    '299 lifetxt "Legacy write without client revision; fetch '
                    '/api/revision and send If-Match."'
                )
                response.headers["Deprecation"] = "true"
                response.headers["X-Lifetxt-Legacy-Revision-Fallback"] = "used"
            if (
                path in ("/api/revision", "/api/capabilities")
                and response.status_code < 400
            ):
                response.set_cookie(
                    _REVISION_COOKIE,
                    "1",
                    httponly=True,
                    samesite="strict",
                    path="/",
                )
            return response

        return app

    create_app._lifetxt_path_shape_compatible = True
    webapp.create_app = create_app
