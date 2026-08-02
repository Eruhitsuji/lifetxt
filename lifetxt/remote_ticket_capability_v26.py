"""Publish conservative Remote ticket field metadata through capabilities."""

from __future__ import unicode_literals


def install_remote_ticket_capability_v26():
    from . import remote_ticket_write_core as core
    from . import remote_ticket_writes as surface

    if getattr(surface, "_REMOTE_TICKET_CAPABILITY_V26", False):
        return

    original = surface.enrich_capability

    def enrich_capability(original_or_config, config=None, protocol_version=None):
        if callable(original_or_config):
            actual_protocol = protocol_version
            payload = original(original_or_config, config, actual_protocol)
        else:
            from . import remote_access

            actual_protocol = (
                protocol_version if protocol_version is not None else config
            )
            payload = original(
                remote_access.capability, original_or_config, actual_protocol
            )
        if int(actual_protocol or 1) < 2:
            return payload
        policy = dict(payload.get("mutation_policy") or {})
        policy["editable_fields"] = sorted(core.EDIT_FIELDS)
        policy["create_fields"] = [
            "ticket_id",
            "subject",
            "tracker",
            "project",
            "priority",
            "visibility",
        ]
        policy["raw_source_replacement_enabled"] = False
        policy["field_contract_version"] = "1"
        payload["mutation_policy"] = policy
        import hashlib
        import json

        payload["capability_revision"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return payload

    surface.enrich_capability = enrich_capability
    surface._REMOTE_TICKET_CAPABILITY_V26 = True
