"""P0 remote attachment and clock-skew contracts.

The routes and MCP tools in this module expose only operations whose touched
revisions and recovery behavior are explicit. Remote package sources are
confined to a configured server-side root, platform open execution is never
performed remotely, and large content is returned in bounded chunks.
"""

from __future__ import unicode_literals

import json
import os
from collections import OrderedDict

from .attachment_transactions import (
    AttachmentTransactionError,
    inspect_directory_package,
    package_directory,
    prepare_open_reference,
    read_attachment_chunk,
    reconcile_attachment,
    reference_directory,
    resolve_package_source,
)
from .attachments import DIR_KEY, FILE_KEY
from .clock_skew import ClockSkewError, require_acceptable_clock
from .transaction_journal import inspect_journal, journal_directory, transaction_id

_INSTALLED = False
_ORIGINALS = {}


def remote_clock_required(config):
    config = config or {}
    section = config.get("clock") if isinstance(config.get("clock"), dict) else {}
    return bool(section.get("require_remote_write_time"))


def remote_client_time_header(config):
    config = config or {}
    section = config.get("clock") if isinstance(config.get("clock"), dict) else {}
    return str(section.get("client_time_header") or "X-Lifetxt-Client-Time")


def attachment_contract(config=None):
    config = config or {}
    section = config.get("attachments") if isinstance(config.get("attachments"), dict) else {}
    return OrderedDict(
        (
            ("contract_version", "1"),
            ("operations", [
                "directory-reference", "package", "reconcile", "open-plan",
                "read-chunk", "inspect-package", "transaction-status",
            ]),
            ("write_revisions", {
                "directory-reference": ["item_revision", "attachment_revision"],
                "package": ["item_revision", "attachment_revision", "transaction_id"],
                "reconcile": ["item_revision", "attachment_revision", "recorded_revision"],
                "open-plan": ["attachment_revision", "metadata_revision when record=true"],
            }),
            ("recovery", {
                "package": ["inspect", "resume", "compensate", "abandon"],
                "directory-reference": ["reload-and-retry"],
                "reconcile": ["reload-and-retry"],
                "open-plan": ["reload-and-retry"],
            }),
            ("remote_source_root", section.get("remote_source_root") or section.get("root") or "attachments"),
            ("max_chunk_bytes", min(int(section.get("remote_chunk_bytes") or 65536), 1024 * 1024)),
            ("remote_open_execution", False),
            ("schemas", [
                "attachment-remote-operation-v1.schema.json",
                "attachment-chunk-v1.schema.json",
                "directory-package-inspection-v1.schema.json",
            ]),
        )
    )


def attachment_transaction_status(life_path, transaction_id_value, config=None):
    txid = transaction_id(transaction_id_value)
    root = journal_directory(config or {}, writable_path=life_path)
    path = os.path.join(root, txid, "journal.json")
    if not os.path.exists(path):
        return OrderedDict(
            (
                ("found", False),
                ("transaction_id", txid),
                ("journal_path", path),
                ("state", "missing"),
                ("recovery_actions", []),
            )
        )
    report = inspect_journal(path)
    report = OrderedDict(report)
    report["found"] = True
    state = report.get("state")
    if state in ("committed", "compensated", "abandoned"):
        actions = ["inspect"]
    else:
        actions = ["inspect", "resume", "compensate", "abandon"]
    report["recovery_actions"] = actions
    return report


def duplicate_transaction_payload(life_path, transaction_id_value, config=None):
    report = attachment_transaction_status(life_path, transaction_id_value, config=config)
    return OrderedDict(
        (
            ("error", "DUPLICATE_TRANSACTION_ID"),
            ("message", "The transaction ID already has recovery evidence; inspect it before retrying."),
            ("transaction", report),
        )
    )


def _require_fields(payload, names):
    missing = [name for name in names if payload.get(name) in (None, "")]
    if missing:
        raise AttachmentTransactionError("Missing required fields: %s" % ", ".join(missing))


def _patch_web():
    from . import surface_runtime, webapp

    if "web_create_app" in _ORIGINALS:
        return
    original = webapp.create_app
    _ORIGINALS["web_create_app"] = original
    # Attachment functions perform their own multi-target revision checks. A
    # staged single-file SurfaceTransaction would otherwise publish the old ETag.
    surface_runtime._WEB_NO_REVISION_PATHS = frozenset(
        set(surface_runtime._WEB_NO_REVISION_PATHS)
        | {
            "/api/attachments",
            "/api/attachments/directory-reference",
            "/api/attachments/package",
            "/api/attachments/reconcile",
            "/api/attachments/open",
        }
    )

    def create_app(paths=None, writable_path=None, config=None, read_only=False):
        from fastapi import Body, HTTPException, Query, Request
        from fastapi.responses import JSONResponse
        from .mutation import MutationConflict
        from .transaction_journal import TransactionJournalError

        app = original(paths=paths, writable_path=writable_path, config=config, read_only=read_only)

        def fail(exc, status=400, transaction_id_value=None):
            if isinstance(exc, MutationConflict):
                raise HTTPException(status_code=409, detail={
                    "error": "CONFLICT",
                    "path": exc.path,
                    "expected_revision": exc.expected_hash,
                    "current_revision": exc.actual_hash,
                    "operation": exc.operation,
                })
            if (
                isinstance(exc, TransactionJournalError)
                and "already exists" in str(exc)
                and transaction_id_value
            ):
                raise HTTPException(status_code=409, detail=duplicate_transaction_payload(
                    app.state.writable_path, transaction_id_value, config=app.state.config,
                ))
            raise HTTPException(status_code=status, detail={"error": "ATTACHMENT_CONTRACT", "message": str(exc)})

        @app.get("/api/attachments/contract")
        def get_attachment_contract():
            return attachment_contract(app.state.config)

        @app.get("/api/attachments/chunk")
        def get_attachment_chunk(
            path: str = Query(...),
            offset: int = 0,
            limit: int = 65536,
            attachment_revision: str = None,
        ):
            try:
                return read_attachment_chunk(
                    app.state.writable_path,
                    path,
                    offset=offset,
                    limit=limit,
                    attachment_expected_revision=attachment_revision,
                    config=app.state.config,
                )
            except Exception as exc:
                fail(exc)

        @app.get("/api/attachments/package-manifest")
        def get_package_manifest(path: str = Query(...), attachment_revision: str = None):
            try:
                return inspect_directory_package(
                    app.state.writable_path,
                    path,
                    attachment_expected_revision=attachment_revision,
                    config=app.state.config,
                )
            except Exception as exc:
                fail(exc)

        @app.get("/api/attachments/transactions/{transaction_id_value}")
        def get_attachment_transaction(transaction_id_value: str):
            try:
                return attachment_transaction_status(
                    app.state.writable_path, transaction_id_value, config=app.state.config
                )
            except Exception as exc:
                fail(exc)

        @app.post("/api/attachments/directory-reference")
        def post_directory_reference(payload=Body(...)):
            try:
                if not isinstance(payload, dict):
                    raise AttachmentTransactionError("Body must be a JSON object.")
                _require_fields(payload, ("id", "path", "item_revision", "attachment_revision"))
                return reference_directory(
                    app.state.writable_path,
                    str(payload["id"]),
                    str(payload["path"]),
                    item_revision=payload["item_revision"],
                    attachment_expected_revision=payload["attachment_revision"],
                    config=app.state.config,
                    allow_symlink=bool(payload.get("allow_symlink")),
                    require_revisions=True,
                )
            except Exception as exc:
                fail(exc)

        @app.post("/api/attachments/package")
        def post_package(payload=Body(...)):
            try:
                if not isinstance(payload, dict):
                    raise AttachmentTransactionError("Body must be a JSON object.")
                _require_fields(payload, ("id", "source", "path", "item_revision", "attachment_revision", "transaction_id"))
                txid = str(payload["transaction_id"])
                source, _root = resolve_package_source(
                    app.state.writable_path,
                    str(payload["source"]),
                    config=app.state.config,
                    allow_symlink=bool(payload.get("allow_symlink")),
                )
                return package_directory(
                    app.state.writable_path,
                    str(payload["id"]),
                    source,
                    str(payload["path"]),
                    item_revision=payload["item_revision"],
                    attachment_expected_revision=payload["attachment_revision"],
                    transaction_id=txid,
                    config=app.state.config,
                    require_revisions=True,
                    include_hidden=bool(payload.get("include_hidden")),
                    allow_symlink=bool(payload.get("allow_symlink")),
                )
            except Exception as exc:
                fail(exc, transaction_id_value=(payload.get("transaction_id") if isinstance(payload, dict) else None))

        @app.post("/api/attachments/reconcile")
        def post_reconcile(payload=Body(...)):
            try:
                if not isinstance(payload, dict):
                    raise AttachmentTransactionError("Body must be a JSON object.")
                _require_fields(payload, ("id", "path", "item_revision", "attachment_revision", "recorded_revision"))
                return reconcile_attachment(
                    app.state.writable_path,
                    str(payload["id"]),
                    str(payload["path"]),
                    key=DIR_KEY if str(payload.get("key") or "file") == "dir" else FILE_KEY,
                    item_revision=payload["item_revision"],
                    attachment_expected_revision=payload["attachment_revision"],
                    recorded_revision=payload["recorded_revision"],
                    config=app.state.config,
                    require_revisions=True,
                )
            except Exception as exc:
                fail(exc)

        @app.post("/api/attachments/open")
        def post_open(payload=Body(...)):
            try:
                if not isinstance(payload, dict):
                    raise AttachmentTransactionError("Body must be a JSON object.")
                _require_fields(payload, ("path", "attachment_revision"))
                record = bool(payload.get("record", True))
                if record:
                    _require_fields(payload, ("metadata_revision",))
                report = prepare_open_reference(
                    app.state.writable_path,
                    str(payload["path"]),
                    attachment_expected_revision=payload["attachment_revision"],
                    metadata_revision=payload.get("metadata_revision"),
                    config=app.state.config,
                    require_revisions=True,
                    record=record,
                )
                report["executed"] = False
                report["remote_execution_allowed"] = False
                return report
            except Exception as exc:
                fail(exc)

        @app.middleware("http")
        async def _remote_clock_guard(request: Request, call_next):
            parser_only = request.url.path in {
                "/api/check-line", "/api/items/parse", "/api/shorthand/parse",
            }
            if (
                not app.state.read_only
                and remote_clock_required(app.state.config)
                and request.method.upper() in ("POST", "PUT", "PATCH", "DELETE")
                and request.url.path.startswith("/api/")
                and not parser_only
            ):
                header = remote_client_time_header(app.state.config)
                value = request.headers.get(header)
                if not value:
                    return JSONResponse(status_code=428, content={
                        "error": "CLIENT_TIME_REQUIRED",
                        "message": "%s is required for remote writes." % header,
                        "server_authoritative": True,
                    })
                try:
                    report = require_acceptable_clock(value, config=app.state.config)
                except (ClockSkewError, ValueError) as exc:
                    return JSONResponse(status_code=409, content={
                        "error": "CLOCK_SKEW",
                        "message": str(exc),
                        "server_authoritative": True,
                    })
                response = await call_next(request)
                response.headers["X-Lifetxt-Clock-State"] = report["state"]
                response.headers["X-Lifetxt-Clock-Skew-Seconds"] = str(report["skew_seconds"])
                return response
            return await call_next(request)

        return app

    webapp.create_app = create_app


def _mcp_tool(name, description, properties, required=None, read_only=False, destructive=False):
    schema = {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        },
        "annotations": {
            "title": name.replace("_", " "),
            "readOnlyHint": bool(read_only),
            "destructiveHint": bool(destructive),
            "idempotentHint": bool(read_only),
            "openWorldHint": False,
        },
    }
    if required:
        schema["inputSchema"]["required"] = list(required)
    return schema


def _patch_mcp():
    from . import mcp

    if "mcp_call_tool" in _ORIGINALS:
        return
    original_call = mcp.call_tool
    original_schemas = mcp.tool_schemas
    _ORIGINALS["mcp_call_tool"] = original_call
    _ORIGINALS["mcp_tool_schemas"] = original_schemas

    def directory_reference(args, context):
        _require_fields(args, ("id", "path", "item_revision", "attachment_revision"))
        return reference_directory(
            context.writable_path, str(args["id"]), str(args["path"]),
            item_revision=args["item_revision"],
            attachment_expected_revision=args["attachment_revision"],
            config=context.config, require_revisions=True,
            allow_symlink=bool(args.get("allow_symlink")),
        )

    def package(args, context):
        _require_fields(args, ("id", "source", "path", "item_revision", "attachment_revision", "transaction_id"))
        source, _root = resolve_package_source(
            context.writable_path, str(args["source"]), config=context.config,
            allow_symlink=bool(args.get("allow_symlink")),
        )
        try:
            return package_directory(
                context.writable_path, str(args["id"]), source, str(args["path"]),
                item_revision=args["item_revision"],
                attachment_expected_revision=args["attachment_revision"],
                transaction_id=str(args["transaction_id"]),
                config=context.config, require_revisions=True,
                include_hidden=bool(args.get("include_hidden")),
                allow_symlink=bool(args.get("allow_symlink")),
            )
        except Exception as exc:
            if "already exists" in str(exc):
                return duplicate_transaction_payload(
                    context.writable_path, str(args["transaction_id"]), config=context.config
                )
            raise

    def reconcile(args, context):
        _require_fields(args, ("id", "path", "item_revision", "attachment_revision", "recorded_revision"))
        return reconcile_attachment(
            context.writable_path, str(args["id"]), str(args["path"]),
            key=DIR_KEY if str(args.get("key") or "file") == "dir" else FILE_KEY,
            item_revision=args["item_revision"],
            attachment_expected_revision=args["attachment_revision"],
            recorded_revision=args["recorded_revision"],
            config=context.config, require_revisions=True,
        )

    def open_plan(args, context):
        _require_fields(args, ("path", "attachment_revision"))
        record = bool(args.get("record", True))
        if record:
            _require_fields(args, ("metadata_revision",))
        report = prepare_open_reference(
            context.writable_path, str(args["path"]),
            attachment_expected_revision=args["attachment_revision"],
            metadata_revision=args.get("metadata_revision"),
            config=context.config, require_revisions=True, record=record,
        )
        report["executed"] = False
        report["remote_execution_allowed"] = False
        return report

    def read_chunk(args, context):
        _require_fields(args, ("path",))
        return read_attachment_chunk(
            context.writable_path, str(args["path"]),
            offset=int(args.get("offset") or 0),
            limit=int(args.get("limit") or 65536),
            attachment_expected_revision=args.get("attachment_revision"),
            config=context.config,
        )

    def inspect_package(args, context):
        _require_fields(args, ("path",))
        return inspect_directory_package(
            context.writable_path, str(args["path"]),
            attachment_expected_revision=args.get("attachment_revision"),
            config=context.config,
        )

    def transaction_status(args, context):
        _require_fields(args, ("transaction_id",))
        return attachment_transaction_status(
            context.writable_path, str(args["transaction_id"]), config=context.config
        )

    handlers = {
        "attachment_directory_reference": directory_reference,
        "attachment_package": package,
        "attachment_reconcile": reconcile,
        "attachment_open": open_plan,
        "attachment_read_chunk": read_chunk,
        "attachment_inspect_package": inspect_package,
        "attachment_transaction_status": transaction_status,
    }
    mcp.TOOL_HANDLERS.update(handlers)
    mcp.READ_ONLY_TOOLS = frozenset(set(mcp.READ_ONLY_TOOLS) | {
        "attachment_read_chunk", "attachment_inspect_package", "attachment_transaction_status"
    })
    mcp.DESTRUCTIVE_TOOLS = frozenset(set(mcp.DESTRUCTIVE_TOOLS) | {
        "attachment_package", "attachment_reconcile"
    })

    def call_tool(name, arguments, context):
        args = dict(arguments or {})
        if name not in mcp.TOOL_HANDLERS:
            return original_call(name, args, context)
        if context.read_only and name not in mcp.READ_ONLY_TOOLS:
            raise ValueError("MCP server is read-only.")
        if name not in mcp.READ_ONLY_TOOLS and remote_clock_required(context.config):
            value = args.get("client_time")
            if not value:
                return {
                    "error": "CLIENT_TIME_REQUIRED",
                    "message": "client_time is required for remote writes.",
                    "server_authoritative": True,
                }
            try:
                clock = require_acceptable_clock(value, config=context.config)
            except (ClockSkewError, ValueError) as exc:
                return {"error": "CLOCK_SKEW", "message": str(exc), "server_authoritative": True}
            result = original_call(name, args, context)
            if isinstance(result, dict):
                result = dict(result)
                result["clock"] = clock
            return result
        return original_call(name, args, context)

    def tool_schemas():
        schemas = list(original_schemas())
        string = lambda description: {"type": "string", "description": description}
        boolean = lambda description: {"type": "boolean", "description": description}
        integer = lambda description: {"type": "integer", "description": description}
        schemas.extend([
            _mcp_tool("attachment_directory_reference", "Reference a confined directory using exact item and tree revisions.", {
                "id": string("Item ID."), "path": string("Confined directory path."),
                "item_revision": string("Exact life.txt revision."), "attachment_revision": string("Exact directory tree revision."),
                "allow_symlink": boolean("Explicit symlink policy override."), "client_time": string("Offset-aware client timestamp when required."),
            }, required=("id", "path", "item_revision", "attachment_revision")),
            _mcp_tool("attachment_package", "Create a deterministic ZIP from a confined server-side directory and journal it with the item reference.", {
                "id": string("Item ID."), "source": string("Confined server-side source directory."), "path": string("ZIP attachment path."),
                "item_revision": string("Exact life.txt revision."), "attachment_revision": string("Exact ZIP target revision or <missing>."),
                "transaction_id": string("Stable retry/recovery transaction ID."), "include_hidden": boolean("Include hidden entries."),
                "allow_symlink": boolean("Explicit symlink policy override."), "client_time": string("Offset-aware client timestamp when required."),
            }, required=("id", "source", "path", "item_revision", "attachment_revision", "transaction_id"), destructive=True),
            _mcp_tool("attachment_reconcile", "Update a file or directory reference only after validating item, target, and recorded revisions.", {
                "id": string("Item ID."), "path": string("Attachment path."), "key": {"type": "string", "enum": ["file", "dir"]},
                "item_revision": string("Exact life.txt revision."), "attachment_revision": string("Exact current attachment revision."),
                "recorded_revision": string("Revision currently stored on the item."), "client_time": string("Offset-aware client timestamp when required."),
            }, required=("id", "path", "item_revision", "attachment_revision", "recorded_revision"), destructive=True),
            _mcp_tool("attachment_open", "Validate an attachment and return a platform open plan without executing it remotely.", {
                "path": string("Attachment path."), "attachment_revision": string("Exact attachment revision."),
                "record": boolean("Update open metadata."), "metadata_revision": string("Exact metadata revision or <missing>."),
                "client_time": string("Offset-aware client timestamp when required."),
            }, required=("path", "attachment_revision")),
            _mcp_tool("attachment_read_chunk", "Read one bounded attachment chunk.", {
                "path": string("Attachment path."), "offset": integer("Byte offset."), "limit": integer("Maximum bytes, capped at 1 MiB."),
                "attachment_revision": string("Optional exact revision."),
            }, required=("path",), read_only=True),
            _mcp_tool("attachment_inspect_package", "Validate a deterministic ZIP and its embedded manifest.", {
                "path": string("ZIP attachment path."), "attachment_revision": string("Optional exact revision."),
            }, required=("path",), read_only=True),
            _mcp_tool("attachment_transaction_status", "Inspect retry/recovery state for one attachment transaction ID.", {
                "transaction_id": string("Stable transaction ID."),
            }, required=("transaction_id",), read_only=True),
        ])
        # Make the optional clock precondition discoverable for every writable
        # tool, not only the new attachment tools. Whether it is required is
        # advertised by the capability document and enforced at call time.
        for schema in schemas:
            name = schema.get("name")
            if name in mcp.READ_ONLY_TOOLS:
                continue
            input_schema = schema.setdefault("inputSchema", {"type": "object"})
            properties = input_schema.setdefault("properties", {})
            properties.setdefault("client_time", string(
                "Offset-aware client timestamp required when remote clock enforcement is enabled."
            ))
        return schemas

    mcp.call_tool = call_tool
    mcp.tool_schemas = tool_schemas


def _patch_capabilities():
    from . import safety_foundation, surface_runtime

    if "capability_document_for" in _ORIGINALS:
        return
    original_for = surface_runtime.capability_document_for
    original_base = safety_foundation.capability_document
    _ORIGINALS["capability_document_for"] = original_for
    _ORIGINALS["capability_document"] = original_base

    def enrich(data, config=None):
        data = OrderedDict(data)
        data["attachment_contract"] = attachment_contract(config)
        data["remote_clock"] = OrderedDict((
            ("required_for_writes", remote_clock_required(config)),
            ("client_time_header", remote_client_time_header(config)),
            ("schema", "clock-skew-v1.schema.json"),
        ))
        return data

    def capability_document_for(surface, read_only=False, authentication="token", writable_targets=None, config=None):
        return enrich(original_for(
            surface, read_only=read_only, authentication=authentication,
            writable_targets=writable_targets, config=config,
        ), config=config)

    def capability_document(read_only=False, authentication="token", writable_targets=None, config=None):
        return enrich(original_base(
            read_only=read_only, authentication=authentication,
            writable_targets=writable_targets, config=config,
        ), config=config)

    surface_runtime.capability_document_for = capability_document_for
    safety_foundation.capability_document = capability_document


def install_remote_contracts_v6():
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_capabilities()
    _patch_web()
    _patch_mcp()
    _INSTALLED = True
