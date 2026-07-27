"""Compatibility normalization for permission-aware Remote client writes."""
from __future__ import unicode_literals


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
            policy.get("ticket_operations")
            or policy.get("operations")
            or []
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
            ) or capabilities.get("capability_revision"),
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

    target.remote_permissions = remote_permissions
    target._error_code = error_code
    target._REMOTE_CLIENT_WRITES_COMPAT_V25 = True
