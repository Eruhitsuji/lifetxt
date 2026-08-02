"""Redacted diagnostic support bundles.

Support bundles contain policy, version, hashes, diagnostics, and recovery metadata,
but never life.txt contents, transaction artifacts, credentials, or raw absolute paths.
"""

from __future__ import unicode_literals

import hashlib
import json
import os
from collections import OrderedDict

from .transaction_journal import utc_now_text


SENSITIVE_KEYS = frozenset(
    (
        "password",
        "token",
        "secret",
        "authorization",
        "cookie",
        "api_key",
        "credential",
        "body",
        "content",
        "replacement",
        "before_artifact",
        "after_artifact",
    )
)
PATH_KEYS = frozenset(
    (
        "path",
        "paths",
        "write_path",
        "writable_path",
        "source",
        "target",
        "journal_path",
        "journal_dir",
        "archive_paths",
        "timer_paths",
    )
)


def write_support_bundle(report, output_path, extra=None):
    value = OrderedDict(
        (
            ("schema_version", 1),
            ("created_at_utc", utc_now_text()),
            (
                "redaction",
                "absolute paths are pseudonymized; authored content and credentials are excluded",
            ),
            ("report", redact(report)),
            ("extra", redact(extra or {})),
        )
    )
    path = os.path.abspath(output_path)
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    from .atomic import atomic_write_text

    atomic_write_text(path, payload, encoding="utf-8")
    value["output"] = path
    value["sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return value


def redact(value, key=None):
    normalized = str(key or "").lower()
    if normalized in SENSITIVE_KEYS or any(
        word in normalized for word in ("password", "secret", "token")
    ):
        return "<redacted>"
    if isinstance(value, dict):
        result = OrderedDict()
        for child_key, child in value.items():
            output_key = (
                _redacted_path(child_key)
                if isinstance(child_key, str) and os.path.isabs(child_key)
                else str(child_key)
            )
            result[output_key] = redact(child, key=child_key)
        return result
    if isinstance(value, (list, tuple)):
        return [redact(child, key=key) for child in value]
    if isinstance(value, str):
        if (
            normalized in PATH_KEYS
            or normalized.endswith("_path")
            or normalized.endswith("_paths")
        ):
            return _redacted_path(value)
        if os.path.isabs(value):
            return _redacted_path(value)
    return value


def _redacted_path(value):
    if value in (None, ""):
        return value
    raw = os.path.expanduser(str(value))
    if not os.path.isabs(raw):
        return value
    text = os.path.abspath(raw)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    basename = os.path.basename(text) or "root"
    return "<path:%s>/%s" % (digest, basename)
