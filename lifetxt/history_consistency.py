"""Read-only consistency verification between Native History and Git evidence."""

from __future__ import unicode_literals

import json
import os
from collections import OrderedDict

from .historical_temporal import (
    _git,
    _read_blob,
    resolve_commit,
    resolve_git_inputs,
)
from .native_history import (
    is_item_event,
    item_event_history_diagnostics,
    normalize_native_events,
)
from .parser import parse_text
from .progress_history import is_progress_event, progress_history_diagnostics


DEFAULT_COMMIT_LIMIT = 100
MAX_COMMIT_LIMIT = 500
_RELATIONS = ("follows", "realizes", "replaced_by")
_SCHEDULES = ("on", "due", "from", "to", "at")
_CLASSIFICATIONS = (
    "verified",
    "native_only",
    "git_only",
    "conflict",
    "unverifiable",
)


def _values(item, key):
    return [str(value) for value in (getattr(item, "details", {}).get(key) or [])]


def _first(item, key, default=None):
    values = _values(item, key)
    return values[0] if values else default


def _identity(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _projection(items, id_key):
    rows = {}
    for item in items:
        if _values(item, "record") and _first(item, "record") in (
            "item_event",
            "progress_event",
            "ticket_event",
            "time_entry",
        ):
            continue
        identifiers = _values(item, id_key)
        if len(identifiers) != 1:
            continue
        item_id = identifiers[0]
        rows[item_id] = OrderedDict(
            (
                ("kind", item.kind),
                ("title", item.title),
                ("status", item.status),
                ("progress", _first(item, "progress")),
                (
                    "relations",
                    OrderedDict((key, sorted(set(_values(item, key)))) for key in _RELATIONS),
                ),
                (
                    "schedule",
                    OrderedDict((key, _first(item, key)) for key in _SCHEDULES),
                ),
                ("source", getattr(item, "source", None)),
            )
        )
    return rows


def _snapshot(repo_root, inputs, commit, id_key):
    items = []
    revisions = {}
    missing = []
    from .mutation import hash_text

    for entry in inputs:
        blob = _read_blob(repo_root, commit, entry["tree_path"])
        if blob is None:
            missing.append(entry["tree_path"])
            continue
        text, _size = blob
        revisions[entry["tree_path"]] = hash_text(text)
        parsed, _diagnostics = parse_text(
            text, id_key=id_key, check_ids=False, check_references=False
        )
        for item in parsed:
            item.source = entry["tree_path"]
        items.extend(parsed)
    return {
        "projection": _projection(items, id_key),
        "source_revisions": revisions,
        "missing_paths": missing,
    }


def _change(item_id, domain, field, before, after, source_path=None, target=None):
    return OrderedDict(
        (
            ("item_id", item_id),
            ("domain", domain),
            ("field", field),
            ("before", before),
            ("after", after),
            ("target", target),
            ("source_path", source_path),
        )
    )


def _semantic_changes(before, after):
    rows = []
    for item_id in sorted(set(after) - set(before)):
        value = after[item_id]
        rows.append(
            _change(
                item_id,
                "item",
                "created",
                None,
                OrderedDict(
                    (
                        ("kind", value["kind"]),
                        ("title", value["title"]),
                        ("status", value["status"]),
                    )
                ),
                value.get("source"),
            )
        )
    for item_id in sorted(set(before) & set(after)):
        left = before[item_id]
        right = after[item_id]
        if left["status"] != right["status"]:
            rows.append(
                _change(
                    item_id,
                    "item",
                    "status",
                    left["status"],
                    right["status"],
                    right.get("source"),
                )
            )
        if left["progress"] != right["progress"]:
            rows.append(
                _change(
                    item_id,
                    "progress",
                    "progress",
                    left["progress"],
                    right["progress"],
                    right.get("source"),
                )
            )
        for field in _RELATIONS:
            old = set(left["relations"][field])
            new = set(right["relations"][field])
            for target in sorted(new - old):
                rows.append(
                    _change(
                        item_id,
                        "relation",
                        field,
                        False,
                        True,
                        right.get("source"),
                        target,
                    )
                )
            for target in sorted(old - new):
                rows.append(
                    _change(
                        item_id,
                        "relation",
                        field,
                        True,
                        False,
                        right.get("source"),
                        target,
                    )
                )
        for field in _SCHEDULES:
            if left["schedule"][field] != right["schedule"][field]:
                rows.append(
                    _change(
                        item_id,
                        "schedule",
                        field,
                        left["schedule"][field],
                        right["schedule"][field],
                        right.get("source"),
                    )
                )
    return rows


def _native_change(row):
    payload = row["payload"]
    event = row["event"]

    def scalar(name):
        values = payload.get(name) or []
        return values[0] if values else None

    if row["record_kind"] == "item_event":
        if event == "created":
            after = OrderedDict(
                (
                    ("kind", scalar("item_kind")),
                    ("title", scalar("item_title")),
                    ("status", scalar("after_status")),
                )
            )
            return _change(row["parent"], "item", "created", None, after)
        if event in ("status_changed", "completed", "reopened", "canceled"):
            return _change(
                row["parent"],
                "item",
                "status",
                scalar("before_status"),
                scalar("after_status"),
            )
        if event in ("relation_added", "relation_removed"):
            added = event == "relation_added"
            return _change(
                row["parent"],
                "relation",
                scalar("relation"),
                not added,
                added,
                target=scalar("target"),
            )
        if event == "schedule_changed":
            before = None if scalar("before_missing") == "true" else scalar("before")
            after = None if scalar("after_missing") == "true" else scalar("after")
            return _change(row["parent"], "schedule", scalar("field"), before, after)
    if row["record_kind"] == "progress_event":
        before = None if scalar("before_missing") == "true" else scalar("before_progress")
        return _change(row["parent"], "progress", "progress", before, scalar("after_progress"))
    return None


def _match_key(change, include_after=True):
    values = [
        change["item_id"],
        change["domain"],
        change["field"],
        change["before"],
        change["target"],
    ]
    if include_after:
        values.append(change["after"])
    return _identity(values)


def _conflict_key(change):
    return _identity(
        [
            change["item_id"],
            change["domain"],
            change["field"],
            change["target"],
        ]
    )


def _invalid_streams(items, id_key):
    parents = {}
    for item in items:
        if is_item_event(item):
            key = ("item_event", str(_first(item, "parent", "")))
            parents.setdefault(key, []).append(item)
        elif is_progress_event(item):
            key = ("progress_event", str(_first(item, "parent", "")))
            parents.setdefault(key, []).append(item)
    invalid = set()
    for (record_kind, parent), events in parents.items():
        current = [
            item
            for item in items
            if not is_item_event(item)
            and not is_progress_event(item)
            and parent in _values(item, id_key)
        ]
        relevant = current + events
        diagnostics = (
            item_event_history_diagnostics(relevant, id_key=id_key)
            if record_kind == "item_event"
            else progress_history_diagnostics(relevant, id_key=id_key)
        )
        blocking = [row for row in diagnostics if row.code not in ("W243", "W277")]
        if blocking:
            invalid.add((record_kind, parent))
    return invalid


def _comparison(classification, change, native=None, git=None, reason=None):
    return OrderedDict(
        (
            ("classification", classification),
            ("item_id", change["item_id"]),
            ("domain", change["domain"]),
            ("field", change["field"]),
            ("before", change["before"]),
            ("after", change["after"]),
            ("target", change["target"]),
            ("native", native),
            ("git", git),
            ("reason", reason),
        )
    )


def _native_evidence(row):
    return OrderedDict(
        (
            ("record_kind", row["record_kind"]),
            ("record_id", row["record_id"]),
            ("transaction", row["transaction"]),
            ("source_revision", row["source_revision"]),
            ("at", row["at"]),
            ("sequence", row["sequence"]),
        )
    )


def _git_evidence(change):
    return OrderedDict(
        (
            ("before_commit", change.get("before_commit")),
            ("after_commit", change.get("after_commit")),
            ("source_path", change.get("source_path")),
            ("source_revision", change.get("source_revision")),
            ("before", change.get("before")),
            ("after", change.get("after")),
            ("target", change.get("target")),
        )
    )


def _git_transitions(paths, id_key, commit_limit):
    repo_root, inputs = resolve_git_inputs(paths)
    head = resolve_commit(repo_root, "HEAD")
    args = [
        "rev-list",
        "--reverse",
        "--max-count=%d" % (commit_limit + 1),
        head,
        "--",
    ] + [entry["tree_path"] for entry in inputs]
    result = _git(repo_root, args)
    if result.returncode != 0:
        raise ValueError("Could not enumerate Git history: %s" % result.stderr.strip())
    commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    truncated = len(commits) > commit_limit
    if truncated:
        commits = commits[-commit_limit:]
    shallow = _git(repo_root, ["rev-parse", "--is-shallow-repository"])
    history_complete = (
        shallow.returncode == 0
        and shallow.stdout.strip() == "false"
        and not truncated
    )
    limitations = []
    if shallow.returncode != 0 or shallow.stdout.strip() != "false":
        limitations.append("shallow_or_unverifiable_history")
    if truncated:
        limitations.append("commit_limit_truncated")
    if not commits:
        return repo_root, head, [], history_complete, limitations, 0

    parent = _git(repo_root, ["rev-parse", "--verify", commits[0] + "^"])
    if parent.returncode == 0:
        before_commit = parent.stdout.strip()
        before_snapshot = _snapshot(repo_root, inputs, before_commit, id_key)
    else:
        before_commit = None
        before_snapshot = {"projection": {}, "source_revisions": {}, "missing_paths": []}
    changes = []
    missing_paths = set(before_snapshot["missing_paths"])
    for commit in commits:
        after_snapshot = _snapshot(repo_root, inputs, commit, id_key)
        missing_paths.update(after_snapshot["missing_paths"])
        for change in _semantic_changes(
            before_snapshot["projection"], after_snapshot["projection"]
        ):
            change["before_commit"] = before_commit
            change["after_commit"] = commit
            change["source_revision"] = before_snapshot["source_revisions"].get(
                change.get("source_path")
            )
            changes.append(change)
        before_commit = commit
        before_snapshot = after_snapshot
    if missing_paths:
        limitations.extend("missing_at_revision:%s" % path for path in sorted(missing_paths))
        history_complete = False
    return repo_root, head, changes, history_complete, limitations, len(commits)


def verify_history_consistency(
    items, paths, id_key="id", item_id=None, commit_limit=DEFAULT_COMMIT_LIMIT
):
    """Compare bounded semantic transition sets; never mutate either source."""
    try:
        commit_limit = int(commit_limit)
    except (TypeError, ValueError):
        raise ValueError("History-check commit limit must be an integer.")
    if commit_limit < 1 or commit_limit > MAX_COMMIT_LIMIT:
        raise ValueError("History-check commit limit must be between 1 and %d." % MAX_COMMIT_LIMIT)

    native_rows = normalize_native_events(items, item_id)
    invalid_streams = _invalid_streams(items, id_key)
    comparisons = []
    comparable = []
    for row in native_rows:
        change = _native_change(row)
        if not row["valid"] or (row["record_kind"], row["parent"]) in invalid_streams:
            fallback = change or _change(
                row["parent"], "unsupported", row["event"], None, None
            )
            comparisons.append(
                _comparison(
                    "unverifiable",
                    fallback,
                    native=_native_evidence(row),
                    reason="malformed_or_non_authoritative_native_event",
                )
            )
        elif change is None:
            fallback = _change(row["parent"], row["record_kind"], row["event"], None, None)
            comparisons.append(
                _comparison(
                    "unverifiable",
                    fallback,
                    native=_native_evidence(row),
                    reason="unsupported_git_semantic_projection",
                )
            )
        else:
            comparable.append((change, row))

    git_available = True
    try:
        (
            repo_root,
            head,
            git_changes,
            history_complete,
            limitations,
            examined,
        ) = _git_transitions(paths, id_key, commit_limit)
    except ValueError as exc:
        git_available = False
        repo_root = None
        head = None
        git_changes = []
        history_complete = False
        limitations = ["git_evidence_unavailable:%s" % str(exc)]
        examined = 0

    if item_id is not None:
        git_changes = [row for row in git_changes if row["item_id"] == str(item_id)]
    exact = {}
    conflict_key = {}
    for index, change in enumerate(git_changes):
        exact.setdefault(_match_key(change), []).append(index)
        conflict_key.setdefault(_conflict_key(change), []).append(index)
    consumed = set()
    for change, row in comparable:
        native_value = _native_evidence(row)
        candidates = [
            index
            for index in exact.get(_match_key(change), [])
            if index not in consumed
        ]
        if candidates:
            native_revision = row.get("source_revision")
            provenance_matches = [
                index
                for index in candidates
                if native_revision
                and git_changes[index].get("source_revision") == native_revision
            ]
            index = (provenance_matches or candidates)[0]
            consumed.add(index)
            comparisons.append(
                _comparison(
                    "verified",
                    change,
                    native=native_value,
                    git=_git_evidence(git_changes[index]),
                )
            )
            continue
        conflicts = [
            index
            for index in conflict_key.get(_conflict_key(change), [])
            if index not in consumed
        ]
        if conflicts:
            index = conflicts[0]
            consumed.add(index)
            git_change = git_changes[index]
            comparisons.append(
                _comparison(
                    "conflict",
                    change,
                    native=native_value,
                    git=_git_evidence(git_change),
                    reason="comparable_before_after_values_disagree",
                )
            )
        else:
            reason = (
                "git_evidence_unavailable"
                if not git_available
                else "no_matching_git_transition"
            )
            comparisons.append(
                _comparison(
                    "native_only", change, native=native_value, reason=reason
                )
            )
    for index, change in enumerate(git_changes):
        if index not in consumed:
            comparisons.append(
                _comparison(
                    "git_only",
                    change,
                    git=_git_evidence(change),
                    reason="native_event_not_found",
                )
            )

    comparisons.sort(
        key=lambda row: (
            row["item_id"],
            row["domain"],
            row["field"],
            _identity(row["before"]),
            _identity(row["after"]),
            row["classification"],
        )
    )
    summary = OrderedDict((name, 0) for name in _CLASSIFICATIONS)
    for row in comparisons:
        summary[row["classification"]] += 1
    complete = bool(
        git_available
        and history_complete
        and all(summary[name] == 0 for name in _CLASSIFICATIONS if name != "verified")
        and not limitations
    )
    return OrderedDict(
        (
            ("schema", "native-git-history-consistency-v1"),
            ("item_id", str(item_id) if item_id is not None else None),
            ("complete", complete),
            ("limitations", sorted(set(limitations))),
            (
                "native_evidence",
                OrderedDict(
                    (
                        ("available", bool(native_rows)),
                        ("event_count", len(native_rows)),
                        ("source", "native_life_txt"),
                    )
                ),
            ),
            (
                "git_evidence",
                OrderedDict(
                    (
                        ("available", git_available),
                        ("repo_root", repo_root),
                        ("head", head),
                        ("commits_examined", examined),
                        ("history_complete", history_complete),
                    )
                ),
            ),
            ("summary", summary),
            ("comparisons", comparisons),
        )
    )
