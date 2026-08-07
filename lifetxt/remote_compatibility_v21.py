"""Expanded Remote capability and client-compatibility negotiation."""

from __future__ import unicode_literals

import hashlib
import importlib.util
import json
import re
import sys
import threading
from collections import OrderedDict


_CONTRACT_PATTERNS = OrderedDict(
    (
        ("configuration", ("config", "effective-config", "configuration")),
        ("workspace_manifest", ("workspace-source-manifest", "workspace-manifest")),
        ("transaction_journal_policy", ("transaction", "journal", "policy")),
        ("clock", ("clock", "timezone")),
        ("ticket", ("ticket-v", "ticket-operation", "ticket-project-report")),
        ("ticket_custom_field", ("ticket-custom-field",)),
        ("ticket_workflow", ("ticket-workflow", "ticket-transition")),
        ("ticket_event", ("ticket-event",)),
        ("time_entry", ("time-entry",)),
        ("ticket_planning", ("ticket-version", "ticket-sprint", "ticket-planning")),
        ("attachment", ("attachment", "directory-package", "package-manifest")),
        (
            "remote_resource",
            ("remote-capability", "remote-read-response", "remote-diagnostics"),
        ),
    )
)
_VERSION_RE = re.compile(r"-v([0-9]+)(?:[.-]|$)")
_SCHEMA_INVENTORY = None
_SCHEMA_INVENTORY_LOCK = threading.Lock()
_OPTIONAL_DEPENDENCIES = None
_OPTIONAL_DEPENDENCIES_LOCK = threading.Lock()


def _package_version():
    package = sys.modules.get("lifetxt")
    value = getattr(package, "__version__", None) if package else None
    return str(value or "unknown")


def _module_available(name):
    try:
        return importlib.util.find_spec(str(name)) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def optional_dependencies():
    global _OPTIONAL_DEPENDENCIES
    if _OPTIONAL_DEPENDENCIES is None:
        with _OPTIONAL_DEPENDENCIES_LOCK:
            if _OPTIONAL_DEPENDENCIES is None:
                groups = OrderedDict(
                    (
                        ("web", ("fastapi", "uvicorn")),
                        ("tui", ("textual", "watchdog")),
                    )
                )
                _OPTIONAL_DEPENDENCIES = OrderedDict(
                    (
                        name,
                        OrderedDict(
                            (
                                (
                                    "available",
                                    all(
                                        _module_available(module) for module in modules
                                    ),
                                ),
                                ("modules", list(modules)),
                            )
                        ),
                    )
                    for name, modules in groups.items()
                )
    return OrderedDict(
        (
            name,
            OrderedDict(
                (("available", row["available"]), ("modules", list(row["modules"])))
            ),
        )
        for name, row in _OPTIONAL_DEPENDENCIES.items()
    )


def _schema_inventory():
    global _SCHEMA_INVENTORY
    if _SCHEMA_INVENTORY is None:
        with _SCHEMA_INVENTORY_LOCK:
            if _SCHEMA_INVENTORY is None:
                from . import safety_foundation

                bundle = OrderedDict(safety_foundation.schema_bundle())
                names = tuple(sorted(str(name) for name in bundle))
                canonical = json.dumps(
                    bundle, ensure_ascii=True, sort_keys=True, separators=(",", ":")
                )
                revision = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                _SCHEMA_INVENTORY = (names, revision)
    names, revision = _SCHEMA_INVENTORY
    return list(names), revision


def _matches(name, patterns):
    lowered = str(name).lower()
    return any(pattern in lowered for pattern in patterns)


def _schema_versions(names):
    versions = []
    for name in names:
        match = _VERSION_RE.search(str(name))
        if match:
            versions.append(int(match.group(1)))
    return versions


def contract_versions(schema_names=None):
    if schema_names is None:
        schema_names, _revision = _schema_inventory()
    result = OrderedDict()
    for contract, patterns in _CONTRACT_PATTERNS.items():
        names = [name for name in schema_names if _matches(name, patterns)]
        versions = _schema_versions(names)
        result[contract] = OrderedDict(
            (
                ("available", bool(names)),
                ("minimum", min(versions) if versions else None),
                ("current", max(versions) if versions else None),
                ("schemas", names),
            )
        )
    return result


def compatibility_policy():
    from .remote_access import REMOTE_PROTOCOL_CURRENT, REMOTE_PROTOCOL_MIN

    return OrderedDict(
        (
            ("minimum_client_protocol", REMOTE_PROTOCOL_MIN),
            ("current_client_protocol", REMOTE_PROTOCOL_CURRENT),
            (
                "supported_protocols",
                list(range(REMOTE_PROTOCOL_MIN, REMOTE_PROTOCOL_CURRENT + 1)),
            ),
            ("unknown_fields", "ignore"),
            ("missing_optional_features", "disable"),
            ("removed_features", "explicit-unsupported"),
            ("future_protocols", "reject"),
            ("downgrade", "client-selects-supported-protocol"),
        )
    )


def compatibility_manifest():
    schema_names, bundle_revision = _schema_inventory()
    return OrderedDict(
        (
            (
                "server",
                OrderedDict(
                    (
                        ("package", "lifetxt"),
                        ("version", _package_version()),
                    )
                ),
            ),
            (
                "schema_bundle",
                OrderedDict(
                    (
                        ("document_count", len(schema_names)),
                        ("revision", bundle_revision),
                    )
                ),
            ),
            ("contracts", contract_versions(schema_names)),
            ("optional_dependencies", optional_dependencies()),
            ("compatibility", compatibility_policy()),
        )
    )


_UNSET = object()


def _required_contract_warnings(contracts, required_contracts):
    if isinstance(required_contracts, dict):
        items = list(required_contracts.items())
    else:
        items = [(str(name), None) for name in required_contracts]
    unknown = sorted(
        {name for name, _minimum in items if name not in _CONTRACT_PATTERNS}
    )
    if unknown:
        raise ValueError(
            "Unknown required contract domain(s): %s. Valid domains: %s."
            % (", ".join(unknown), ", ".join(sorted(_CONTRACT_PATTERNS)))
        )
    warnings = []
    for name, minimum in items:
        entry = contracts.get(name) if isinstance(contracts, dict) else None
        if not entry or not entry.get("available"):
            warnings.append(
                "Required contract '%s' is not published by the server." % name
            )
            continue
        current = entry.get("current")
        if minimum is not None and (current is None or current < minimum):
            warnings.append(
                "Required contract '%s' is at version %s, below the required "
                "minimum %s." % (name, current, minimum)
            )
    return warnings


def _header_status(capabilities, capability_revision_header):
    body_revision = capabilities.get("capability_revision")
    if capability_revision_header is None:
        return (
            "missing",
            "Capability-revision header is missing from the response; a proxy "
            "may be stripping it.",
        )
    if body_revision is not None and capability_revision_header != body_revision:
        return (
            "mismatch",
            "Capability-revision header does not match the response body; a "
            "proxy may be rewriting or caching it.",
        )
    return "present-and-consistent", None


def evaluate_compatibility(
    capabilities,
    requested_protocol=None,
    required_contracts=None,
    capability_revision_header=_UNSET,
):
    """Return a deterministic client/server compatibility report.

    ``required_contracts`` and ``capability_revision_header`` are optional and
    purely additive: omitting both reproduces the exact output of every caller
    that predates this parameter pair.

    ``required_contracts`` is either an iterable of contract-domain names (a
    presence-only check) or a mapping of domain name to minimum required
    version (a presence-and-version check). An unknown domain name raises
    ``ValueError`` naming the valid domains.

    ``capability_revision_header`` is the raw ``X-Lifetxt-Remote-Capability-
    Revision`` header value the transport layer received, or ``None`` if the
    header was absent. Passing ``None`` explicitly is not the same as omitting
    the parameter: omitting it skips the header check entirely, while passing
    ``None`` reports a missing header. When supplied, the result gains a
    ``header_status`` key: ``"present-and-consistent"``, ``"missing"``, or
    ``"mismatch"``.
    """
    from .remote_access import REMOTE_PROTOCOL_CURRENT, REMOTE_PROTOCOL_MIN

    capabilities = dict(capabilities or {})
    protocol = (
        capabilities.get("protocol")
        if isinstance(capabilities.get("protocol"), dict)
        else {}
    )
    server_min = int(
        protocol.get("minimum", capabilities.get("protocol_min", REMOTE_PROTOCOL_MIN))
    )
    server_current = int(
        protocol.get("current", capabilities.get("protocol_current", server_min))
    )
    client_min = REMOTE_PROTOCOL_MIN
    client_current = REMOTE_PROTOCOL_CURRENT
    requested = int(
        requested_protocol if requested_protocol is not None else client_current
    )
    overlap_min = max(server_min, client_min)
    overlap_current = min(server_current, client_current)
    overlap = (
        list(range(overlap_min, overlap_current + 1))
        if overlap_min <= overlap_current
        else []
    )
    requested_supported = requested in overlap
    manifest_present = all(
        key in capabilities
        for key in (
            "server",
            "schema_bundle",
            "contracts",
            "compatibility",
            "optional_dependencies",
        )
    )
    warnings = []
    if not manifest_present:
        warnings.append(
            "Server capability metadata predates the expanded compatibility manifest."
        )
    if server_current > client_current:
        warnings.append("Server supports a newer Remote protocol than this client.")
    if server_min > client_current:
        warnings.append("Server minimum Remote protocol is newer than this client.")
    if required_contracts:
        warnings.extend(
            _required_contract_warnings(
                capabilities.get("contracts"), required_contracts
            )
        )
    header_status = None
    if capability_revision_header is not _UNSET:
        header_status, header_warning = _header_status(
            capabilities, capability_revision_header
        )
        if header_warning:
            warnings.append(header_warning)
    result = OrderedDict(
        (
            ("ok", bool(overlap and requested_supported)),
            (
                "status",
                "compatible" if overlap and requested_supported else "incompatible",
            ),
            ("requested_protocol", requested),
            ("client", {"minimum": client_min, "current": client_current}),
            ("server", {"minimum": server_min, "current": server_current}),
            ("overlap", overlap),
            ("selected_protocol", requested if requested_supported else None),
            ("manifest_present", manifest_present),
            ("warnings", warnings),
        )
    )
    if capability_revision_header is not _UNSET:
        result["header_status"] = header_status
    return result


def install_remote_compatibility_v21():
    from . import remote_access

    if getattr(remote_access, "_lifetxt_remote_compatibility_v21", False):
        return
    original = remote_access._capability_v2

    def capability_v2(config):
        payload = OrderedDict(original(config))
        payload.pop("capability_revision", None)
        payload.update(compatibility_manifest())
        payload["capability_revision"] = hashlib.sha256(
            json.dumps(
                payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        return payload

    remote_access._capability_v2 = capability_v2
    remote_access._lifetxt_remote_compatibility_v21 = True


def install_remote_client_compatibility_v21():
    from . import remote_client

    if getattr(remote_client, "_lifetxt_remote_compatibility_v21", False):
        return
    original = remote_client.test_connection

    def test_connection(profile):
        result = OrderedDict(original(profile))
        result["compatibility"] = evaluate_compatibility(
            result.get("capabilities"),
            result.get("requested_protocol"),
            capability_revision_header=result.get("capability_revision"),
        )
        return result

    remote_client.test_connection = test_connection
    remote_client._lifetxt_remote_compatibility_v21 = True
