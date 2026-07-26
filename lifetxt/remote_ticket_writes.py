"""Install protocol-v2 authenticated single-source Remote ticket mutations."""
from __future__ import unicode_literals

from . import mutation
from .remote_access import RemoteAccessError, require_exact_revision, require_scope
from .remote_backend import source_revision
from .remote_ticket_write_core import (
    OPERATIONS,
    ROUTE,
    as_remote_error,
    enabled,
    enrich_capability,
    existing_ticket_path,
    mutation_response,
    replay,
    request_hash,
    ticket_key,
    transaction_id,
)
from .remote_ticket_write_operations import create_ticket, mutate_ticket

_INSTALLED = False


def install_remote_ticket_writes():
    global _INSTALLED
    if _INSTALLED:
        return
    from . import config_registry, remote_access, remote_web, surface_runtime, webapp

    if "remote.ticket_writes_enabled" not in config_registry.CONFIG_REGISTRY:
        config_registry.CONFIG_REGISTRY["remote.ticket_writes_enabled"] = (
            config_registry._entry(
                "boolean",
                False,
                "Enable the protocol-v2 single-source Remote ticket mutation adapter. "
                "Every mutation requires authenticated write scope, exact If-Match "
                "admission, a stable transaction_id, per-file CAS, and an append-only "
                "ticket event.",
                restart_required=True,
            )
        )

    surface_runtime._WEB_NO_REVISION_PATHS = frozenset(
        set(surface_runtime._WEB_NO_REVISION_PATHS) | {ROUTE}
    )
    original_capability = remote_access.capability

    def capability(config, protocol_version=None):
        return enrich_capability(original_capability, config, protocol_version)

    remote_access.capability = capability
    remote_access.capability_revision = (
        lambda config: capability(config, 2)["capability_revision"]
    )
    remote_web.capability = capability
    original_create_app = webapp.create_app

    def create_app(paths=None, writable_path=None, config=None, read_only=False):
        from fastapi import Body, Request

        app = original_create_app(
            paths=paths,
            writable_path=writable_path,
            config=config,
            read_only=read_only,
        )

        @app.post(ROUTE)
        def remote_ticket_mutation(request: Request, payload=Body(default={})):
            try:
                if int(getattr(request.state, "remote_protocol", 1)) < 2:
                    raise RemoteAccessError(
                        "REMOTE_VERSION_REQUIRED",
                        "Remote ticket mutations require protocol version 2.",
                        426,
                        {"required": 2},
                    )
                principal = request.state.remote_principal
                require_scope(principal, "write")
                if read_only:
                    raise RemoteAccessError(
                        "REMOTE_READ_ONLY",
                        "This server is read-only.",
                        403,
                    )
                if not enabled(app.state.config):
                    raise RemoteAccessError(
                        "REMOTE_TICKET_WRITES_DISABLED",
                        "Remote ticket mutations are disabled by configuration.",
                        403,
                    )
                if not writable_path:
                    raise RemoteAccessError(
                        "REMOTE_WRITABLE_SOURCE_REQUIRED",
                        "A writable life.txt source is required.",
                        409,
                    )
                operation = str(
                    (payload or {}).get("operation") or ""
                ).strip().lower()
                if operation not in OPERATIONS:
                    raise RemoteAccessError(
                        "REMOTE_TICKET_OPERATION_UNKNOWN",
                        "operation must be one of: %s." % ", ".join(OPERATIONS),
                        400,
                    )
                txid = transaction_id(payload)
                digest = request_hash(operation, payload)
                key = ticket_key(app.state.config)
                ticket_id_value = str(
                    (payload or {}).get("ticket_id") or ""
                ).strip()
                path = (
                    writable_path
                    if operation == "create"
                    else existing_ticket_path(
                        app.state.paths,
                        writable_path,
                        ticket_id_value,
                        key,
                    )
                )
                if ticket_id_value:
                    prior = replay(
                        path,
                        app.state.paths,
                        key,
                        operation,
                        ticket_id_value,
                        txid,
                        digest,
                    )
                    if prior is not None:
                        return prior
                aggregate_before = source_revision(app.state.paths)
                require_exact_revision(request.headers, aggregate_before)
                target_before = mutation.read_text_snapshot(
                    path,
                    allow_missing=False,
                ).content_hash
                dry_run = bool((payload or {}).get("dry_run", False))
                try:
                    result = (
                        create_ticket(
                            path,
                            payload,
                            principal,
                            target_before,
                            app.state.config,
                            key,
                            digest,
                            txid,
                            dry_run,
                        )
                        if operation == "create"
                        else mutate_ticket(
                            operation,
                            path,
                            payload,
                            principal,
                            target_before,
                            app.state.config,
                            key,
                            digest,
                            txid,
                            dry_run,
                        )
                    )
                except ValueError as exc:
                    if "already exists" in str(exc) and ticket_id_value:
                        prior = replay(
                            path,
                            app.state.paths,
                            key,
                            operation,
                            ticket_id_value,
                            txid,
                            digest,
                        )
                        if prior is not None:
                            return prior
                    raise
                result.setdefault(
                    "target_revision_before",
                    result.get("revision_before", target_before),
                )
                result.setdefault(
                    "target_revision_after",
                    result.get("revision_after"),
                )
                aggregate_after = (
                    aggregate_before
                    if dry_run
                    else source_revision(app.state.paths)
                )
                return mutation_response(
                    operation,
                    txid,
                    False,
                    aggregate_before,
                    aggregate_after,
                    result,
                )
            except Exception as exc:
                raise as_remote_error(exc)

        return app

    webapp.create_app = create_app
    _INSTALLED = True
