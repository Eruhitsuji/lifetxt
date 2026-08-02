"""Compatibility normalization for permission-aware Remote client writes."""

from __future__ import unicode_literals

import json
import sys


def install_remote_client_writes_compat_v25():
    from . import remote_client_writes as target
    from .remote_ticket_capability_v26 import install_remote_ticket_capability_v26

    if getattr(target, "_REMOTE_CLIENT_WRITES_COMPAT_V25", False):
        return

    install_remote_ticket_capability_v26()

    def remote_permissions(profile):
        session, session_headers = target.request(
            profile, "GET", "/api/remote/v1/session"
        )
        capabilities, capability_headers = target.request(
            profile, "GET", "/api/remote/v1/capabilities"
        )
        principal = dict(session.get("principal") or {})
        policy = dict(capabilities.get("mutation_policy") or {})
        scopes = list(principal.get("scopes") or [])
        operations = list(
            policy.get("ticket_operations") or policy.get("operations") or []
        )
        enabled = bool(
            policy.get("ticket_mutations_enabled")
            or policy.get("authoritative_remote_writes_enabled")
        )
        admission_only = bool(policy.get("admission_only", False))
        enabled = enabled and not admission_only
        limitations = list(policy.get("limitations") or [])
        flag_limitations = (
            ("single_writable_source_only", "single_writable_source_only"),
            ("multi_file_mutations_enabled", "multi_file_mutations_disabled"),
            ("exact_revision_required", "exact_revision_required"),
            ("transaction_id_required", "transaction_id_required"),
            ("append_only_history_required", "append_only_history_required"),
        )
        for key, label in flag_limitations:
            value = policy.get(key)
            include = (key == "multi_file_mutations_enabled" and value is False) or (
                key != "multi_file_mutations_enabled" and bool(value)
            )
            if include and label not in limitations:
                limitations.append(label)
        denial_reasons = []
        if "write" not in scopes:
            denial_reasons.append("principal_missing_write_scope")
        if admission_only:
            denial_reasons.append("remote_write_admission_only")
        if not enabled:
            denial_reasons.append("ticket_mutations_disabled")
        if enabled and not operations:
            denial_reasons.append("no_ticket_operations_advertised")
        for value in policy.get("denial_reasons") or []:
            if value not in denial_reasons:
                denial_reasons.append(value)
        return {
            "principal": principal,
            "scopes": scopes,
            "grants": {
                "projects": target._grant_list(principal, "projects"),
                "groups": target._grant_list(principal, "groups"),
                "visibilities": target._grant_list(principal, "visibilities"),
            },
            "can_read": "read" in scopes,
            "can_write": "write" in scopes and enabled and bool(operations),
            "can_admin": "admin" in scopes,
            "can_audit": "audit" in scopes,
            "ticket_mutations_enabled": enabled,
            "ticket_operations": operations,
            "editable_fields": list(policy.get("editable_fields") or []),
            "create_fields": list(policy.get("create_fields") or []),
            "field_contract_version": policy.get("field_contract_version"),
            "raw_source_replacement_enabled": bool(
                policy.get("raw_source_replacement_enabled", False)
            ),
            "limitations": limitations,
            "denial_reasons": denial_reasons,
            "protocol": {
                "session": target._header(
                    session_headers, "lifetxt_negotiated_protocol"
                ),
                "capabilities": target._header(
                    capability_headers, "lifetxt_negotiated_protocol"
                ),
            },
            "capability_revision": target._header(
                capability_headers,
                "X-Lifetxt-Remote-Capability-Revision",
            )
            or capabilities.get("capability_revision"),
            "server_read_only": bool(
                policy.get("read_only")
                or capabilities.get("read_only")
                or session.get("read_only")
            ),
            "mutation_policy": policy,
        }

    def error_code(detail):
        nested = detail.get("detail") if isinstance(detail, dict) else None
        nested = nested if isinstance(nested, dict) else {}
        deeper = nested.get("detail") if isinstance(nested.get("detail"), dict) else {}
        candidates = (
            detail.get("code") if isinstance(detail, dict) else None,
            detail.get("error") if isinstance(detail, dict) else None,
            nested.get("code"),
            nested.get("error"),
            deeper.get("code"),
            deeper.get("error"),
        )
        return next((str(value).upper() for value in candidates if value), "")

    def interactive_tui(profile, input_fn=input, output=None):
        output = output or sys.stdout
        permissions = target.remote_permissions(profile)
        output.write("lifetxt remote\n")
        output.write(target.render_permissions(permissions))
        data = target.snapshot(profile)
        target._list_tickets(data, output)
        writes = (
            list(permissions.get("ticket_operations") or [])
            if permissions.get("can_write")
            else []
        )
        allowed = ["show", "refresh", "quit"] + writes
        last_result = None
        while True:
            try:
                operation = (
                    input_fn("operation [%s]: " % "/".join(allowed)).strip().lower()
                )
            except (EOFError, KeyboardInterrupt):
                output.write("\nRemote TUI cancelled.\n")
                return {"cancelled": True, "reason": "interrupted"}
            if operation in ("", "quit", "q"):
                if not permissions.get("can_write") and last_result is None:
                    return {"mode": "read-only", "permissions": permissions}
                return last_result or {"cancelled": True}
            if operation == "refresh":
                data = target.snapshot(profile)
                target._list_tickets(data, output)
                last_result = {"refreshed": True, "revision": data.get("revision")}
                continue
            if operation == "show":
                try:
                    wanted = input_fn("ticket id: ").strip()
                    value = target.ticket_detail(profile, wanted, data)
                except (EOFError, KeyboardInterrupt):
                    output.write("\nTicket detail cancelled.\n")
                    last_result = {"cancelled": True, "reason": "interrupted"}
                    continue
                except KeyError as exc:
                    last_result = {
                        "error": "REMOTE_TICKET_NOT_VISIBLE",
                        "message": str(exc),
                    }
                    output.write(
                        json.dumps(
                            last_result,
                            ensure_ascii=False,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    continue
                output.write(target.render_ticket_detail(value))
                last_result = value
                continue
            if operation not in writes:
                output.write("Operation is not allowed by the server: %s\n" % operation)
                continue
            try:
                payload = target._operation_payload(operation, input_fn)
            except (EOFError, KeyboardInterrupt):
                output.write("\nMutation entry cancelled.\n")
                last_result = {"cancelled": True, "operation": operation}
                continue
            output.write("proposed mutation:\n")
            output.write(
                json.dumps(
                    {"operation": operation, "payload": payload},
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            try:
                confirmed = (
                    input_fn("apply authoritative mutation? [y/N]: ").strip().lower()
                )
            except (EOFError, KeyboardInterrupt):
                output.write("\nMutation confirmation cancelled.\n")
                last_result = {"cancelled": True, "operation": operation}
                continue
            if confirmed not in ("y", "yes"):
                last_result = {"cancelled": True, "operation": operation}
                continue
            try:
                last_result = target.mutate_ticket(profile, operation, payload)
                output.write(
                    json.dumps(
                        last_result,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                )
                data = target.snapshot(profile)
            except target.RemoteMutationConflict as exc:
                last_result = exc.as_dict()
                output.write(
                    json.dumps(
                        last_result,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                )
                data = target.snapshot(profile)

    target.remote_permissions = remote_permissions
    target._error_code = error_code
    target.interactive_tui = interactive_tui
    target._REMOTE_CLIENT_WRITES_COMPAT_V25 = True
