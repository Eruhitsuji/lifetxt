"""Revision-aware runtime integration for Web and MCP public surfaces.

The core mutation layer already provides sidecar locking and optimistic
concurrency.  This module connects that contract to the existing Web and MCP
handlers without duplicating their item semantics.  Existing helper functions
continue to build updates, but writes are staged in one request/tool
transaction and committed once with the exact revision the client supplied.
"""

from __future__ import unicode_literals

import contextlib
import difflib
import json
import os
import warnings
from collections import OrderedDict
from contextvars import ContextVar
from urllib.parse import parse_qs, urlencode

from . import mutation as _mutation
from .mutation import MISSING_HASH, MutationConflict, MutationOperation
from .safe_ops import ExpectedRevisionRequired
from .safety_foundation import format_version_report, serve_target_diagnostic


class UnsupportedFormatVersion(ValueError):
    """Raised when a mutation targets a declared unsupported format version."""

    def __init__(self, path, declared):
        self.path = os.path.abspath(path)
        self.declared = declared
        ValueError.__init__(
            self,
            "Unsupported format version %s in %s. Migrate the file before writing."
            % (declared, self.path),
        )


OPERATION_REGISTRY = OrderedDict(
    (
        ("query", {"surfaces": ("cli", "web", "mcp"), "write": False}),
        ("create", {"surfaces": ("cli", "web", "mcp"), "write": True}),
        ("update", {"surfaces": ("cli", "web", "mcp"), "write": True}),
        ("delete", {"surfaces": ("cli", "web", "mcp"), "write": True}),
        ("complete", {"surfaces": ("cli", "web", "mcp"), "write": True}),
        ("agenda", {"surfaces": ("cli", "web", "mcp"), "write": False}),
        ("review", {"surfaces": ("cli", "web", "mcp"), "write": False}),
        ("next", {"surfaces": ("cli", "web", "mcp"), "write": False}),
        ("timer", {"surfaces": ("cli", "web", "mcp"), "write": True}),
        ("message", {"surfaces": ("cli", "web", "mcp"), "write": True}),
        ("acknowledge", {"surfaces": ("web", "mcp"), "write": True}),
        ("snooze", {"surfaces": ("web", "mcp"), "write": True}),
        ("presence", {"surfaces": ("cli", "web", "mcp"), "write": True}),
        ("links", {"surfaces": ("cli", "web", "mcp"), "write": False}),
        ("attachments", {"surfaces": ("cli", "web", "mcp"), "write": True}),
        ("capabilities", {"surfaces": ("cli", "web", "mcp"), "write": False}),
    )
)


MCP_REVISION_TOOLS = frozenset(
    (
        "create_item",
        "update_item",
        "mark_done",
        "complete_item",
        "delete_item",
        "create_message",
        "reply_message",
        "ack_message",
        "snooze_message",
        "set_status",
        "capture_item",
        "complete",
    )
)

_WEB_NO_REVISION_PATHS = frozenset(
    (
        "/api/check-line",
        "/api/items/parse",
        "/api/shorthand/parse",
        "/api/timer",
    )
)

_ACTIVE_TRANSACTION = ContextVar("lifetxt_surface_transaction", default=None)
_INSTALLED = False
_ORIGINALS = {}


def operation_names(surface=None):
    """Return registry-derived operation names for one public surface."""
    result = []
    for name, spec in OPERATION_REGISTRY.items():
        if surface is None or surface in spec["surfaces"]:
            result.append(name)
    return result


def operation_matrix():
    """Return a stable JSON-compatible surface/capability matrix."""
    rows = []
    for name, spec in OPERATION_REGISTRY.items():
        rows.append(
            OrderedDict(
                (
                    ("operation", name),
                    ("write", bool(spec["write"])),
                    ("revision_required", bool(spec["write"])),
                    ("surfaces", list(spec["surfaces"])),
                )
            )
        )
    return rows


def normalize_revision(value, supplied=True):
    """Normalize HTTP/MCP revision tokens to mutation-layer hashes."""
    if not supplied or value is None:
        return None
    text = str(value).strip()
    if text.startswith("W/"):
        text = text[2:].strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1]
    if text in ("", "missing", MISSING_HASH):
        return MISSING_HASH
    return text


def current_revision(path):
    return _mutation.read_text_snapshot(path, allow_missing=True).content_hash


def etag_value(revision):
    return '"%s"' % revision


def _ensure_supported_text(path, text):
    report = format_version_report(text)
    if report["state"] == "unsupported":
        raise UnsupportedFormatVersion(path, report.get("declared"))


class SurfaceTransaction(object):
    """Stage all life.txt writes in one public request and commit once."""

    def __init__(self, path, expected_hash, operation, require_revision=True):
        self.path = os.path.abspath(path)
        self.operation = str(operation or "surface.write")
        self.expected_hash = normalize_revision(
            expected_hash, supplied=expected_hash is not None
        )
        if require_revision and self.expected_hash is None:
            raise ExpectedRevisionRequired(
                "%s requires an expected revision. Read the current ETag/file hash and retry."
                % self.operation
            )
        self.before = _mutation.read_text_snapshot(self.path, allow_missing=True)
        if self.expected_hash is not None and self.expected_hash != self.before.content_hash:
            raise MutationConflict(
                self.path,
                self.expected_hash,
                self.before.content_hash,
                operation=self.operation,
            )
        _ensure_supported_text(self.path, self.before.text)
        self.text = self.before.text
        self.dirty = False
        self.result = None

    def matches(self, path):
        return os.path.abspath(path) == self.path

    def read(self, path):
        if self.matches(path):
            return self.text
        return _ORIGINALS["web_read_text"](path)

    def stage(self, path, text):
        if not self.matches(path):
            return _ORIGINALS["web_write_text"](path, text)
        if not isinstance(text, str):
            raise TypeError("SurfaceTransaction.stage expects text.")
        _ensure_supported_text(self.path, text)
        self.text = text
        self.dirty = True
        return None

    def predicted_hash(self):
        if not self.dirty:
            return self.before.content_hash
        return _mutation.hash_text(
            self.text,
            encoding=self.before.encoding,
            bom=self.before.bom,
        )

    def commit(self):
        if not self.dirty:
            return self.before.content_hash
        self.result = _mutation.write_text(
            self.path,
            self.text,
            expected_hash=self.expected_hash,
            operation=self.operation,
            create=self.expected_hash == MISSING_HASH,
        )
        return self.result.after_hash

    def snapshot_state(self):
        return self.text, self.dirty

    def restore_state(self, state):
        self.text, self.dirty = state


@contextlib.contextmanager
def transaction_scope(path, expected_hash, operation, require_revision=True):
    transaction = SurfaceTransaction(
        path,
        expected_hash,
        operation,
        require_revision=require_revision,
    )
    token = _ACTIVE_TRANSACTION.set(transaction)
    try:
        yield transaction
    finally:
        _ACTIVE_TRANSACTION.reset(token)


def active_transaction():
    return _ACTIVE_TRANSACTION.get()


def precondition_payload(path, operation):
    return OrderedDict(
        (
            ("error", "PRECONDITION_REQUIRED"),
            ("message", "An expected revision is required for this write."),
            ("expected_revision", None),
            ("current_revision", current_revision(path)),
            ("attempted_change", {"operation": operation, "path": os.path.abspath(path)}),
        )
    )


def conflict_payload(exc, attempted_change=None):
    return OrderedDict(
        (
            ("error", "CONFLICT"),
            ("message", str(exc)),
            ("expected_revision", exc.expected_hash),
            ("current_revision", exc.actual_hash),
            ("current_item", None),
            ("attempted_change", attempted_change or {"operation": exc.operation, "path": exc.path}),
        )
    )


def unsupported_format_payload(exc, operation):
    return OrderedDict(
        (
            ("error", "UNSUPPORTED_FORMAT_VERSION"),
            ("message", str(exc)),
            ("declared_version", exc.declared),
            ("path", exc.path),
            ("attempted_change", {"operation": operation}),
        )
    )


def capability_document_for(surface, read_only=False, authentication="token", writable_targets=None, config=None):
    original = _ORIGINALS.get("capability_document")
    if original is None:
        from .safety_foundation import capability_document as original
    data = original(
        read_only=read_only,
        authentication=authentication,
        writable_targets=writable_targets,
    )
    data["operations"] = operation_names(surface)
    data["operation_matrix"] = operation_matrix()
    data["surface"] = surface
    return data


def _guard_mutation_layer():
    if "mutation_apply" in _ORIGINALS:
        return
    original = _mutation.apply_text_mutation
    _ORIGINALS["mutation_apply"] = original

    def guarded_apply(path, operation, **kwargs):
        def transform(current):
            _ensure_supported_text(path, current)
            replacement = operation.transform(current)
            if isinstance(replacement, str):
                _ensure_supported_text(path, replacement)
            return replacement

        guarded = MutationOperation(
            operation.name,
            transform,
            validate=operation.validate,
            create=operation.create,
            default_text=operation.default_text,
        )
        return original(path, guarded, **kwargs)

    _mutation.apply_text_mutation = guarded_apply


def _patch_capability_document():
    from . import safety_foundation

    if "capability_document" in _ORIGINALS:
        return
    original = safety_foundation.capability_document
    _ORIGINALS["capability_document"] = original

    def registered_capability_document(read_only=False, authentication="token", writable_targets=None, config=None):
        data = original(
            read_only=read_only,
            authentication=authentication,
            writable_targets=writable_targets,
            config=config,
        )
        data["operations"] = operation_names()
        data["operation_matrix"] = operation_matrix()
        return data

    safety_foundation.capability_document = registered_capability_document


def _patch_webapp():
    from . import webapp

    if "web_create_app" in _ORIGINALS:
        return
    _ORIGINALS["web_read_text"] = webapp.read_text
    _ORIGINALS["web_write_text"] = webapp.write_text
    _ORIGINALS["web_create_app"] = webapp.create_app

    def transaction_read_text(path):
        transaction = active_transaction()
        if transaction is not None and transaction.matches(path):
            return transaction.text
        return _ORIGINALS["web_read_text"](path)

    def transaction_write_text(path, text):
        transaction = active_transaction()
        if transaction is not None and transaction.matches(path):
            return transaction.stage(path, text)
        return _ORIGINALS["web_write_text"](path, text)

    webapp.read_text = transaction_read_text
    webapp.write_text = transaction_write_text
    webapp.HTML_PAGE = _install_browser_revision_bridge(webapp.HTML_PAGE)

    def create_app(paths=None, writable_path=None, config=None, read_only=False):
        selected_paths = paths if paths is not None else ["life.txt"]
        selected_write = writable_path
        if selected_write:
            report = serve_target_diagnostic(selected_paths, selected_write)
            if report.get("windows_drive_relative"):
                raise ValueError(" ".join(report.get("messages") or []))
            if report.get("mismatch"):
                warnings.warn(" ".join(report.get("messages") or []), RuntimeWarning)
        app = _ORIGINALS["web_create_app"](
            paths=paths,
            writable_path=writable_path,
            config=config,
            read_only=read_only,
        )
        actual_report = serve_target_diagnostic(app.state.paths, app.state.writable_path)
        app.state.serve_target_diagnostic = actual_report

        @app.get("/api/revision")
        def get_revision():
            revision = current_revision(app.state.writable_path)
            return {"path": app.state.writable_path, "revision": revision}

        @app.get("/api/capabilities")
        def get_capabilities():
            data = capability_document_for(
                "web",
                read_only=app.state.read_only,
                authentication=("token" if (app.state.config or {}).get("api", {}).get("token") else "none"),
                writable_targets=[] if app.state.read_only else [app.state.writable_path],
                config=app.state.config,
            )
            data["revision"] = current_revision(app.state.writable_path)
            data["serve_target"] = app.state.serve_target_diagnostic
            return data

        @app.middleware("http")
        async def _revision_contract(request, call_next):
            from fastapi.responses import JSONResponse

            _rewrite_named_review_query(request)
            method = request.method.upper()
            path = request.url.path
            unsafe = method in ("POST", "PUT", "PATCH", "DELETE")
            guarded = (
                unsafe
                and path.startswith("/api/")
                and path not in _WEB_NO_REVISION_PATHS
                and not path.startswith("/api/git/")
                and not app.state.read_only
            )
            transaction = None
            token = None
            operation = _web_operation(method, path)
            if guarded:
                header_supplied = "if-match" in request.headers or "x-lifetxt-expected-revision" in request.headers
                raw_expected = request.headers.get("if-match")
                if raw_expected is None:
                    raw_expected = request.headers.get("x-lifetxt-expected-revision")
                if not header_supplied:
                    return JSONResponse(
                        status_code=428,
                        content=precondition_payload(app.state.writable_path, operation),
                    )
                try:
                    transaction = SurfaceTransaction(
                        app.state.writable_path,
                        normalize_revision(raw_expected, supplied=True),
                        operation,
                    )
                except ExpectedRevisionRequired:
                    return JSONResponse(
                        status_code=428,
                        content=precondition_payload(app.state.writable_path, operation),
                    )
                except MutationConflict as exc:
                    return JSONResponse(status_code=409, content=conflict_payload(exc))
                except UnsupportedFormatVersion as exc:
                    return JSONResponse(
                        status_code=409,
                        content=unsupported_format_payload(exc, operation),
                    )
                token = _ACTIVE_TRANSACTION.set(transaction)
            try:
                response = await call_next(request)
                if transaction is not None and response.status_code < 400:
                    try:
                        revision = transaction.commit()
                    except MutationConflict as exc:
                        return JSONResponse(status_code=409, content=conflict_payload(exc))
                    except UnsupportedFormatVersion as exc:
                        return JSONResponse(
                            status_code=409,
                            content=unsupported_format_payload(exc, operation),
                        )
                else:
                    revision = current_revision(app.state.writable_path)
                if path.startswith("/api/"):
                    response.headers["ETag"] = etag_value(revision)
                    response.headers["X-Lifetxt-Revision"] = revision
                return response
            finally:
                if token is not None:
                    _ACTIVE_TRANSACTION.reset(token)

        return app

    webapp.create_app = create_app


def _patch_mcp():
    from . import mcp

    if "mcp_call_tool" in _ORIGINALS:
        return
    _ORIGINALS["mcp_call_tool"] = mcp.call_tool
    _ORIGINALS["mcp_tool_schemas"] = mcp.tool_schemas
    _ORIGINALS["mcp_resource_list"] = mcp.resource_list
    _ORIGINALS["mcp_resource_read"] = mcp.resource_read
    _ORIGINALS["mcp_applied"] = mcp._applied
    _ORIGINALS["mcp_preview_write"] = mcp._preview_write
    _ORIGINALS["mcp_get_review"] = mcp.TOOL_HANDLERS.get("get_review")

    def get_capabilities(_args, context):
        data = capability_document_for(
            "mcp",
            read_only=context.read_only,
            authentication="stdio",
            writable_targets=[] if context.read_only else [context.writable_path],
            config=context.config,
        )
        data["revision"] = current_revision(context.writable_path)
        return data

    def named_review(args, context):
        selector = args.get("range") or args.get("selector")
        if selector:
            from .review import resolve_named_review_range

            start, end = resolve_named_review_range(selector, year=args.get("year"))
            args = dict(args)
            args.pop("range", None)
            args.pop("selector", None)
            args["from"] = start.isoformat()
            args["to"] = end.isoformat()
        return _ORIGINALS["mcp_get_review"](args, context)

    mcp.TOOL_HANDLERS["get_capabilities"] = get_capabilities
    mcp.TOOL_HANDLERS["get_review"] = named_review
    mcp.READ_ONLY_TOOLS = frozenset(set(mcp.READ_ONLY_TOOLS) | {"get_capabilities"})

    def call_tool(name, arguments, context):
        args = dict(arguments or {})
        if name not in MCP_REVISION_TOOLS:
            return _ORIGINALS["mcp_call_tool"](name, args, context)
        supplied = "expected_file_hash" in args or "file_hash" in args
        expected = args.get("expected_file_hash") if "expected_file_hash" in args else args.get("file_hash")
        operation = "mcp.%s" % name
        attempted = {"operation": operation, "tool": name, "argument_keys": sorted(args)}
        if not supplied:
            return precondition_payload(context.writable_path, operation)
        try:
            transaction = SurfaceTransaction(
                context.writable_path,
                normalize_revision(expected, supplied=True),
                operation,
            )
        except ExpectedRevisionRequired:
            return precondition_payload(context.writable_path, operation)
        except MutationConflict as exc:
            return conflict_payload(exc, attempted_change=attempted)
        except UnsupportedFormatVersion as exc:
            return unsupported_format_payload(exc, operation)
        token = _ACTIVE_TRANSACTION.set(transaction)
        try:
            result = _ORIGINALS["mcp_call_tool"](name, args, context)
            if not (_truthy(args.get("dry_run")) or _truthy(args.get("propose"))):
                revision = transaction.commit()
            else:
                revision = transaction.before.content_hash
            if isinstance(result, dict):
                result = dict(result)
                result["file_hash"] = revision
                result["revision"] = revision
            return result
        except MutationConflict as exc:
            return conflict_payload(exc, attempted_change=attempted)
        except UnsupportedFormatVersion as exc:
            return unsupported_format_payload(exc, operation)
        finally:
            _ACTIVE_TRANSACTION.reset(token)

    def tool_schemas():
        schemas = _ORIGINALS["mcp_tool_schemas"]()
        found_capabilities = False
        for schema in schemas:
            name = schema.get("name")
            input_schema = schema.setdefault("inputSchema", {"type": "object", "properties": {}})
            properties = input_schema.setdefault("properties", {})
            if name in MCP_REVISION_TOOLS:
                properties["expected_file_hash"] = {
                    "type": "string",
                    "description": "Exact SHA-256 revision returned by get_file_state; use <missing> for a missing target.",
                }
                required = input_schema.setdefault("required", [])
                if "expected_file_hash" not in required:
                    required.append("expected_file_hash")
            if name == "get_review":
                properties["range"] = {
                    "type": "string",
                    "enum": ["last-week", "last-month", "year"],
                    "description": "Named review range resolved by the shared review module.",
                }
                properties["year"] = {"type": "integer", "description": "Year used with range=year."}
            if name == "get_capabilities":
                found_capabilities = True
        if not found_capabilities:
            schemas.append(
                {
                    "name": "get_capabilities",
                    "description": "Return the versioned MCP capability and revision contract.",
                    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                    "annotations": {
                        "title": "get capabilities",
                        "readOnlyHint": True,
                        "destructiveHint": False,
                        "idempotentHint": True,
                        "openWorldHint": False,
                    },
                }
            )
        return schemas

    def resource_list(context):
        resources = list(_ORIGINALS["mcp_resource_list"](context))
        resources.append(
            {
                "uri": "lifetxt://capabilities",
                "name": "lifetxt capabilities",
                "description": "Versioned operations, schemas, and revision-precondition support.",
                "mimeType": "application/json",
            }
        )
        return resources

    def resource_read(context, uri):
        if str(uri) == "lifetxt://capabilities":
            data = get_capabilities({}, context)
            return {
                "contents": [
                    {
                        "uri": "lifetxt://capabilities",
                        "mimeType": "application/json",
                        "text": json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    }
                ]
            }
        return _ORIGINALS["mcp_resource_read"](context, uri)

    def applied(context, result, summary=""):
        value = _ORIGINALS["mcp_applied"](context, result, summary)
        transaction = active_transaction()
        if transaction is not None and transaction.matches(context.writable_path):
            value["file_hash"] = transaction.predicted_hash()
        return value

    def preview_write(context, apply_fn, summary):
        transaction = active_transaction()
        if transaction is None or not transaction.matches(context.writable_path):
            return _ORIGINALS["mcp_preview_write"](context, apply_fn, summary)
        state = transaction.snapshot_state()
        before = transaction.text
        try:
            apply_fn()
            after = transaction.text
        finally:
            transaction.restore_state(state)
        return {
            "applied": False,
            "proposal": True,
            "summary": summary,
            "path": context.writable_path,
            "file_hash": transaction.before.content_hash,
            "diff": list(
                difflib.unified_diff(
                    before.splitlines(),
                    after.splitlines(),
                    fromfile="%s (current)" % context.writable_path,
                    tofile="%s (proposed)" % context.writable_path,
                    lineterm="",
                    n=2,
                )
            ),
        }

    mcp.call_tool = call_tool
    mcp.tool_schemas = tool_schemas
    mcp.resource_list = resource_list
    mcp.resource_read = resource_read
    mcp._applied = applied
    mcp._preview_write = preview_write


def _install_browser_revision_bridge(html):
    marker = "lifetxt-revision-contract-v1"
    if marker in html:
        return html
    script = r"""
<script id="lifetxt-revision-contract-v1">
(function () {
  const nativeFetch = window.fetch.bind(window);
  let revision = null;
  const excluded = new Set(['/api/check-line', '/api/items/parse', '/api/shorthand/parse', '/api/timer']);
  function pathOf(input) {
    try { return new URL(typeof input === 'string' ? input : input.url, window.location.href).pathname; }
    catch (_) { return ''; }
  }
  async function refreshRevision() {
    const response = await nativeFetch('/api/revision');
    const etag = response.headers.get('ETag');
    if (etag) revision = etag;
    return revision;
  }
  window.fetch = async function (input, init) {
    init = init || {};
    const method = String(init.method || (input && input.method) || 'GET').toUpperCase();
    const path = pathOf(input);
    const unsafe = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method);
    if (unsafe && path.startsWith('/api/') && !excluded.has(path) && !path.startsWith('/api/git/')) {
      if (!revision) await refreshRevision();
      const headers = new Headers(init.headers || (input && input.headers) || {});
      if (revision && !headers.has('If-Match')) headers.set('If-Match', revision);
      init = Object.assign({}, init, {headers: headers});
    }
    const response = await nativeFetch(input, init);
    const etag = response.headers.get('ETag');
    if (etag) revision = etag;
    return response;
  };
  refreshRevision().catch(function () {});
})();
</script>
"""
    if "</body>" in html:
        return html.replace("</body>", script + "</body>", 1)
    return html + script


def _rewrite_named_review_query(request):
    if request.method.upper() != "GET" or request.url.path != "/api/review":
        return
    raw = request.scope.get("query_string", b"").decode("utf-8")
    values = parse_qs(raw, keep_blank_values=True)
    selector_values = values.pop("range", None) or values.pop("selector", None)
    if not selector_values:
        return
    from .review import resolve_named_review_range

    selector = selector_values[-1]
    year_values = values.pop("year", None)
    year = year_values[-1] if year_values else None
    start, end = resolve_named_review_range(selector, year=year)
    values["from"] = [start.isoformat()]
    values["to"] = [end.isoformat()]
    request.scope["query_string"] = urlencode(values, doseq=True).encode("utf-8")


def _web_operation(method, path):
    value = path.lower()
    if "ack" in value:
        name = "acknowledge"
    elif "snooze" in value:
        name = "snooze"
    elif "/messages" in value:
        name = "message"
    elif "/status" in value:
        name = "presence"
    elif "complete" in value or "done" in value:
        name = "complete"
    elif method == "DELETE":
        name = "delete"
    elif method in ("PUT", "PATCH"):
        name = "update"
    else:
        name = "create"
    return "web.%s" % name


def _truthy(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on", "only")


def install_runtime_contracts():
    """Install the public-surface adapters once for this Python process."""
    global _INSTALLED
    if _INSTALLED:
        return
    _guard_mutation_layer()
    _patch_capability_document()
    _patch_webapp()
    _patch_mcp()
    _INSTALLED = True
