"""Strict default-disabled operator policy for the dedicated resource consumer."""

from copy import deepcopy
import hashlib
import json
import os
import re

from .resource_reference_store import BindingUnavailable

LIMITS = dict(
    file_bytes=10485760,
    chunk_bytes=65536,
    active_process=2,
    active_principal=1,
    rate_principal=30,
    rate_process=120,
    deadline_seconds=30,
)
DEFAULTS = dict(
    enabled=False,
    contract_version="1",
    workspace_id=None,
    store_path=None,
    enrolled_items=[],
    metadata=dict(label=False, size=False, mime=False, digest=False),
    limits=LIMITS,
)
HANDLE = re.compile(r"[0-9a-f]{64}\Z")


def policy(config):
    section = (config.get("remote") or {}).get("resource_references", {})
    if not isinstance(section, dict) or set(section) - set(DEFAULTS):
        raise BindingUnavailable()
    result = deepcopy(DEFAULTS)
    result.update(section)
    if type(result["enabled"]) is not bool or result["contract_version"] != "1":
        raise BindingUnavailable()
    for key in ("metadata", "limits"):
        if not isinstance(result[key], dict) or set(result[key]) - set(DEFAULTS[key]):
            raise BindingUnavailable()
        result[key] = dict(DEFAULTS[key], **result[key])
    if any(type(x) is not bool for x in result["metadata"].values()):
        raise BindingUnavailable()
    for key, value in result["limits"].items():
        if type(value) is not int or not 1 <= value <= LIMITS[key]:
            raise BindingUnavailable()
    if (
        not isinstance(result["enrolled_items"], list)
        or len(result["enrolled_items"]) > 10000
    ):
        raise BindingUnavailable()
    seen = set()
    for entry in result["enrolled_items"]:
        if not isinstance(entry, dict) or set(entry) != {
            "source_id",
            "item_id",
            "attachment",
        }:
            raise BindingUnavailable()
        if not isinstance(entry["source_id"], str) or not HANDLE.fullmatch(
            entry["source_id"]
        ):
            raise BindingUnavailable()
        if (
            not safe_text(entry["item_id"])
            or not isinstance(entry["attachment"], str)
            or not 1 <= len(entry["attachment"].encode("utf-8")) <= 4095
        ):
            raise BindingUnavailable()
        selector = tuple(entry[key] for key in ("source_id", "item_id", "attachment"))
        if selector in seen:
            raise BindingUnavailable()
        seen.add(selector)
    if result["enabled"]:
        if not isinstance(result["workspace_id"], str) or not HANDLE.fullmatch(
            result["workspace_id"]
        ):
            raise BindingUnavailable()
        if not isinstance(result["store_path"], str) or not os.path.isabs(
            result["store_path"]
        ):
            raise BindingUnavailable()
        remote = config.get("remote") or {}
        if (
            not remote.get("enabled")
            or remote.get("browser_ui")
            or remote.get("allow_multi_worker")
        ):
            raise BindingUnavailable()
        if int(os.environ.get("WEB_CONCURRENCY", "1")) != 1:
            raise BindingUnavailable()
    return result


def safe_text(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        return False
    try:
        if len(value.encode("utf-8")) > 512:
            return False
    except UnicodeError:
        return False
    return not any(
        ord(c) < 32
        or 127 <= ord(c) <= 159
        or ord(c) in (0x061C, 0x200E, 0x200F, 0x2028, 0x2029)
        or 0x202A <= ord(c) <= 0x202E
        or 0x2066 <= ord(c) <= 0x2069
        for c in value
    )


def fingerprint(config):
    """Private full policy validator, never an HTTP digest/ETag."""
    relevant = {k: v for k, v in config.items() if k != "_path"}
    return hashlib.sha256(
        json.dumps(
            relevant, sort_keys=True, ensure_ascii=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def validate_principals(config):
    from .remote_access import principal_registry, _token_for, _principal_rows

    registry = principal_registry(config)
    rows = _principal_rows(config)
    if len(rows) != len(registry) or len(rows) > 10000:
        raise BindingUnavailable()
    tokens = []
    for entry in registry.values():
        mode = entry.get("disclosure_mode", "trusted")
        if mode not in ("trusted", "restricted-resource"):
            raise BindingUnavailable()
        token = _token_for(entry)
        if token:
            if token in tokens:
                raise BindingUnavailable()
            tokens.append(token)
        if policy(config)["enabled"] and not entry["disabled"]:
            if mode != "restricted-resource" or not token:
                raise BindingUnavailable()
    return registry
