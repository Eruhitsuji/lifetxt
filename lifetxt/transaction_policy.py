"""Retention, privacy, integrity, and deterministic fault policy for journals."""

from __future__ import unicode_literals

import contextlib
import contextvars
import hashlib
import json
import os
import stat
from collections import OrderedDict


_FAULT_HANDLER = contextvars.ContextVar("lifetxt_transaction_fault_handler", default=None)


class TransactionPolicyError(RuntimeError):
    pass


@contextlib.contextmanager
def fault_injection(handler):
    """Install a deterministic boundary hook for tests and fault drills.

    ``handler(point, details)`` may raise to simulate abrupt write failures.
    Production code pays only one context-variable lookup per boundary.
    """
    token = _FAULT_HANDLER.set(handler)
    try:
        yield
    finally:
        _FAULT_HANDLER.reset(token)


def fault_point(point, **details):
    handler = _FAULT_HANDLER.get()
    if handler is not None:
        handler(str(point), dict(details))


def policy_from_config(config=None):
    config = config or {}
    raw = config.get("transactions") if isinstance(config.get("transactions"), dict) else {}
    return OrderedDict(
        (
            ("terminal_retention_days", _number(raw.get("terminal_retention_days"), 30.0, minimum=0.0)),
            ("max_transactions", _integer(raw.get("max_transactions"), 500, minimum=1)),
            ("max_total_bytes", _integer(raw.get("max_total_bytes"), 256 * 1024 * 1024, minimum=1024)),
            ("max_transaction_bytes", _integer(raw.get("max_transaction_bytes"), 64 * 1024 * 1024, minimum=1024)),
            ("require_private_permissions", _boolean(raw.get("require_private_permissions"), True)),
            ("allow_newer_read_only", _boolean(raw.get("allow_newer_read_only"), True)),
            ("evidence_include_paths", _boolean(raw.get("evidence_include_paths"), False)),
        )
    )


def journal_usage(root):
    absolute = os.path.abspath(root)
    count = 0
    total = 0
    largest = 0
    if os.path.isdir(absolute):
        for directory, _subdirs, files in os.walk(absolute):
            if "journal.json" in files:
                count += 1
            for name in files:
                try:
                    size = os.path.getsize(os.path.join(directory, name))
                except OSError:
                    continue
                total += size
                largest = max(largest, size)
    return OrderedDict(
        (("path", absolute), ("transactions", count), ("total_bytes", total), ("largest_file_bytes", largest))
    )


def enforce_capacity(root, policy, estimated_bytes=0):
    usage = journal_usage(root)
    if usage["transactions"] >= int(policy["max_transactions"]):
        raise TransactionPolicyError(
            "Transaction journal limit reached (%d). Clean or archive terminal journals."
            % policy["max_transactions"]
        )
    if usage["total_bytes"] + int(estimated_bytes) > int(policy["max_total_bytes"]):
        raise TransactionPolicyError(
            "Transaction journal size limit would be exceeded (%d bytes)."
            % policy["max_total_bytes"]
        )
    if int(estimated_bytes) > int(policy["max_transaction_bytes"]):
        raise TransactionPolicyError(
            "Transaction evidence exceeds the per-transaction limit (%d bytes)."
            % policy["max_transaction_bytes"]
        )
    return usage


def permission_report(path, require_private=True):
    absolute = os.path.abspath(path)
    report = OrderedDict(
        (
            ("path", absolute),
            ("exists", os.path.exists(absolute)),
            ("owner_matches", True),
            ("private", True),
            ("mode", None),
            ("problems", []),
        )
    )
    if not report["exists"]:
        return report
    try:
        st = os.stat(absolute)
    except OSError as exc:
        report["problems"].append(str(exc))
        report["private"] = False
        return report
    report["mode"] = oct(stat.S_IMODE(st.st_mode))
    if hasattr(os, "geteuid"):
        report["owner_matches"] = st.st_uid == os.geteuid()
        if not report["owner_matches"]:
            report["problems"].append("journal is not owned by the current user")
    if require_private:
        unsafe = stat.S_IMODE(st.st_mode) & 0o077
        if unsafe:
            report["private"] = False
            report["problems"].append("group/other permissions are present")
    return report


def ensure_private_tree(root, require_private=True):
    absolute = os.path.abspath(root)
    os.makedirs(absolute, mode=0o700, exist_ok=True)
    try:
        os.chmod(absolute, 0o700)
    except OSError:
        pass
    report = permission_report(absolute, require_private=require_private)
    if report["problems"]:
        raise TransactionPolicyError(
            "Unsafe transaction journal permissions: %s" % "; ".join(report["problems"])
        )
    return report


def build_integrity_manifest(root):
    absolute = os.path.abspath(root)
    files = []
    for directory, subdirs, names in os.walk(absolute):
        subdirs.sort()
        names.sort()
        for name in names:
            full = os.path.join(directory, name)
            relative = os.path.relpath(full, absolute).replace(os.sep, "/")
            if relative == "integrity-manifest.json":
                continue
            with open(full, "rb") as handle:
                payload = handle.read()
            files.append(
                OrderedDict(
                    (
                        ("path", relative),
                        ("size", len(payload)),
                        ("sha256", hashlib.sha256(payload).hexdigest()),
                    )
                )
            )
    manifest = OrderedDict((("version", 1), ("files", files)))
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return manifest


def write_integrity_manifest(root):
    from .atomic import atomic_write_text

    manifest = build_integrity_manifest(root)
    path = os.path.join(os.path.abspath(root), "integrity-manifest.json")
    atomic_write_text(path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return path, manifest


def verify_integrity_manifest(root):
    absolute = os.path.abspath(root)
    path = os.path.join(absolute, "integrity-manifest.json")
    with open(path, "r", encoding="utf-8") as handle:
        expected = json.load(handle, object_pairs_hook=OrderedDict)
    observed = build_integrity_manifest(absolute)
    expected_files = expected.get("files") or []
    observed_files = observed.get("files") or []
    ok = json.dumps(expected_files, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == json.dumps(observed_files, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return OrderedDict(
        (
            ("ok", ok),
            ("path", path),
            ("expected_manifest_sha256", expected.get("manifest_sha256")),
            ("observed_manifest_sha256", observed.get("manifest_sha256")),
            ("file_count", len(observed.get("files") or [])),
        )
    )


def version_compatibility(record, supported_version):
    try:
        actual = int(record.get("schema_version"))
    except (TypeError, ValueError):
        return OrderedDict((("state", "invalid"), ("actual", record.get("schema_version")), ("supported", supported_version), ("writable", False)))
    if actual == int(supported_version):
        state = "current"
        writable = True
    elif actual < int(supported_version):
        state = "older"
        writable = False
    else:
        state = "newer"
        writable = False
    return OrderedDict((("state", state), ("actual", actual), ("supported", int(supported_version)), ("writable", writable)))


def _integer(value, default, minimum=0):
    try:
        return max(int(minimum), int(value))
    except (TypeError, ValueError):
        return int(default)


def _number(value, default, minimum=0.0):
    try:
        return max(float(minimum), float(value))
    except (TypeError, ValueError):
        return float(default)


def _boolean(value, default):
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")
