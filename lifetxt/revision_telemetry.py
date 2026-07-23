"""Persistent revision-migration telemetry and strict-mode policy.

The Web compatibility bridge originally kept counters only in process memory.  This
module stores a small operational JSON document through the shared mutation layer so
restart-safe evidence can be used to decide when legacy writes may be disabled.
"""

from __future__ import unicode_literals

import datetime
import json
import os
import uuid

from .mutation import MISSING_HASH, mutate_json, read_text_snapshot


SCHEMA_VERSION = 1
DEFAULT_WINDOW_DAYS = 14
VALID_MODES = ("observe", "required")


class RevisionTelemetryError(ValueError):
    pass


def utc_now_text(now=None):
    value = now or datetime.datetime.now(datetime.timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return (
        value.astimezone(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def metrics_path(config=None, writable_path=None):
    config = config or {}
    web = config.get("web") if isinstance(config.get("web"), dict) else {}
    configured = (
        os.environ.get("LIFETXT_REVISION_METRICS_PATH")
        or web.get("revision_metrics_path")
    )
    if configured:
        return os.path.abspath(os.path.expanduser(str(configured)))
    if writable_path:
        directory = os.path.dirname(os.path.abspath(writable_path))
        return os.path.join(directory, ".lifetxt-revision-metrics.json")
    return os.path.abspath(os.path.join(".cache", "lifetxt", "revision-metrics.json"))


def revision_mode(config=None):
    config = config or {}
    web = config.get("web") if isinstance(config.get("web"), dict) else {}
    value = (
        os.environ.get("LIFETXT_REVISION_MODE")
        or web.get("revision_mode")
        or "observe"
    )
    value = str(value).strip().lower()
    if value not in VALID_MODES:
        raise RevisionTelemetryError(
            "web.revision_mode must be one of %s, found %r."
            % (", ".join(VALID_MODES), value)
        )
    return value


def migration_window_days(config=None):
    config = config or {}
    web = config.get("web") if isinstance(config.get("web"), dict) else {}
    raw = (
        os.environ.get("LIFETXT_REVISION_MIGRATION_WINDOW_DAYS")
        or web.get("revision_migration_window_days")
        or DEFAULT_WINDOW_DAYS
    )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise RevisionTelemetryError("Revision migration window must be an integer.")
    if value < 0:
        raise RevisionTelemetryError("Revision migration window must be non-negative.")
    return value


def initial_metrics(mode="observe", window_days=DEFAULT_WINDOW_DAYS, now=None):
    timestamp = utc_now_text(now)
    return {
        "schema_version": SCHEMA_VERSION,
        "server_instance_id": uuid.uuid4().hex,
        "revision_mode": mode,
        "migration_window_days": int(window_days),
        "observation_started_at": timestamp,
        "legacy_fallback_total": 0,
        "legacy_fallback_by_path": {},
        "legacy_fallback_last_used": None,
        "last_reset_at": None,
        "last_persisted_at": timestamp,
    }


def normalize_metrics(value, mode="observe", window_days=DEFAULT_WINDOW_DAYS, now=None):
    base = initial_metrics(mode=mode, window_days=window_days, now=now)
    if isinstance(value, dict):
        for key in base:
            if key in value:
                base[key] = value[key]
    base["schema_version"] = SCHEMA_VERSION
    base["revision_mode"] = mode
    base["migration_window_days"] = int(window_days)
    try:
        base["legacy_fallback_total"] = max(0, int(base["legacy_fallback_total"]))
    except (TypeError, ValueError):
        base["legacy_fallback_total"] = 0
    counts = base.get("legacy_fallback_by_path")
    if not isinstance(counts, dict):
        counts = {}
    normalized_counts = {}
    for path, count in counts.items():
        try:
            normalized_counts[str(path)] = max(0, int(count))
        except (TypeError, ValueError):
            continue
    base["legacy_fallback_by_path"] = normalized_counts
    return base


def readiness(metrics, now=None):
    now_value = now or datetime.datetime.now(datetime.timezone.utc)
    started = _parse_utc(metrics.get("observation_started_at"))
    elapsed = None
    if started is not None:
        elapsed = max(0.0, (now_value.astimezone(datetime.timezone.utc) - started).total_seconds() / 86400.0)
    window = int(metrics.get("migration_window_days") or 0)
    zero_usage = int(metrics.get("legacy_fallback_total") or 0) == 0
    ready = bool(zero_usage and elapsed is not None and elapsed >= window)
    return {
        "zero_usage": zero_usage,
        "observation_days": None if elapsed is None else round(elapsed, 3),
        "required_observation_days": window,
        "ready_to_require_revisions": ready,
        "reason": (
            "The observation window completed with zero legacy fallback use."
            if ready
            else "Keep observe mode until the configured zero-use window completes."
        ),
    }


class RevisionMetricsStore(object):
    def __init__(self, path, mode="observe", window_days=DEFAULT_WINDOW_DAYS):
        if mode not in VALID_MODES:
            raise RevisionTelemetryError("Unknown revision mode: %s" % mode)
        self.path = os.path.abspath(path)
        self.mode = mode
        self.window_days = int(window_days)

    def snapshot(self, now=None):
        value = None
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as handle:
                    value = json.load(handle)
            except (OSError, ValueError):
                value = None
        metrics = normalize_metrics(value, self.mode, self.window_days, now=now)
        report = dict(metrics)
        report.update(readiness(metrics, now=now))
        report["legacy_fallback_enabled"] = self.mode == "observe"
        report["metrics_path"] = self.path
        report["removal_condition"] = (
            "Switch web.revision_mode to required only after ready_to_require_revisions is true."
        )
        return report

    def ensure(self, now=None):
        timestamp = utc_now_text(now)

        def transform(current):
            value = normalize_metrics(current, self.mode, self.window_days, now=now)
            value["last_persisted_at"] = timestamp
            return value

        mutate_json(
            self.path,
            transform,
            operation="revision_telemetry.ensure",
            create=True,
            default=initial_metrics(self.mode, self.window_days, now=now),
        )
        return self.snapshot(now=now)

    def record_legacy_fallback(self, endpoint, now=None):
        endpoint = str(endpoint or "<unknown>")
        timestamp = utc_now_text(now)

        def transform(current):
            value = normalize_metrics(current, self.mode, self.window_days, now=now)
            value["legacy_fallback_total"] += 1
            counts = value["legacy_fallback_by_path"]
            counts[endpoint] = counts.get(endpoint, 0) + 1
            value["legacy_fallback_last_used"] = timestamp
            value["last_persisted_at"] = timestamp
            return value

        mutate_json(
            self.path,
            transform,
            operation="revision_telemetry.record",
            create=True,
            default=initial_metrics(self.mode, self.window_days, now=now),
        )
        return self.snapshot(now=now)

    def reset(self, expected_hash, now=None):
        if expected_hash is None or str(expected_hash).strip() == "":
            raise RevisionTelemetryError(
                "Reset requires expected_hash from read_text_snapshot()."
            )
        timestamp = utc_now_text(now)

        def transform(current):
            previous = normalize_metrics(current, self.mode, self.window_days, now=now)
            value = initial_metrics(self.mode, self.window_days, now=now)
            value["server_instance_id"] = previous.get("server_instance_id") or value["server_instance_id"]
            value["last_reset_at"] = timestamp
            value["observation_started_at"] = timestamp
            value["last_persisted_at"] = timestamp
            return value

        mutate_json(
            self.path,
            transform,
            expected_hash=expected_hash,
            operation="revision_telemetry.reset",
            create=expected_hash == MISSING_HASH,
            default=initial_metrics(self.mode, self.window_days, now=now),
        )
        return self.snapshot(now=now)

    def content_hash(self):
        return read_text_snapshot(self.path, allow_missing=True).content_hash


def store_from_config(config=None, writable_path=None):
    return RevisionMetricsStore(
        metrics_path(config, writable_path),
        mode=revision_mode(config),
        window_days=migration_window_days(config),
    )


def _parse_utc(value):
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)
