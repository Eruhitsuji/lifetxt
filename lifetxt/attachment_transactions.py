"""Journal-backed attachment content and life.txt reference operations."""

from __future__ import unicode_literals

import hashlib
import os
import stat
from collections import OrderedDict

from . import mutation
from .attachments import FILE_KEY, HASH_LENGTH, join_value, normalize_stored_path, split_value
from .ids import id_key_from_config
from .multi_target import attachment_and_item_transaction, bytes_plan, delete_plan
from .transaction_journal import journal_directory
from .write_operations import transform_items_text


class AttachmentTransactionError(ValueError):
    pass


def resolve_attachment_target(life_path, stored_path, root=None, allow_symlink=False):
    base = os.path.dirname(os.path.abspath(life_path))
    root_abs = os.path.realpath(os.path.abspath(root or base))
    raw = str(stored_path or "").strip()
    if not raw:
        raise AttachmentTransactionError("Attachment path must not be empty.")
    candidate = raw.replace("\\", os.sep)
    absolute = candidate if os.path.isabs(candidate) else os.path.join(base, candidate)
    absolute = os.path.abspath(absolute)
    real = os.path.realpath(absolute)
    try:
        confined = os.path.commonpath([root_abs, real]) == root_abs
    except ValueError:
        confined = False
    if not confined:
        raise AttachmentTransactionError(
            "Attachment path escapes the configured root: %s" % raw
        )
    if os.path.islink(absolute) and not allow_symlink:
        raise AttachmentTransactionError(
            "Attachment path is a symlink; pass an explicit allow_symlink policy to use it."
        )
    return absolute, root_abs


def attachment_revision(path):
    try:
        with open(path, "rb") as handle:
            return mutation.hash_bytes(handle.read())
    except FileNotFoundError:
        return mutation.MISSING_HASH


def put_attachment(
    life_path,
    item_id,
    stored_path,
    payload,
    item_revision=None,
    attachment_expected_revision=None,
    config=None,
    allow_symlink=False,
    allow_executable=False,
    require_revisions=False,
):
    if not isinstance(payload, bytes):
        raise TypeError("Attachment payload must be bytes.")
    config = config or {}
    target, _root = resolve_attachment_target(
        life_path,
        stored_path,
        root=_attachment_root(config, life_path),
        allow_symlink=allow_symlink,
    )
    _reject_executable_target(target, payload, allow_executable)
    item_snapshot = mutation.read_text_snapshot(life_path)
    target_revision = attachment_revision(target)
    item_expected = _resolve_revision(item_revision, item_snapshot.content_hash, require_revisions, "item_revision")
    attachment_expected = _resolve_revision(
        attachment_expected_revision,
        target_revision,
        require_revisions,
        "attachment_revision",
    )
    digest = hashlib.sha256(payload).hexdigest()[:HASH_LENGTH]
    normalized = _stored_relative_path(life_path, target)
    value = join_value(normalized, digest)
    id_key = id_key_from_config(config)

    def item_transform(text):
        return _set_reference(text, item_id, id_key, FILE_KEY, value, normalized)

    plan = bytes_plan(
        target,
        lambda _current: payload,
        attachment_expected,
        create=attachment_expected == mutation.MISSING_HASH,
        default=b"",
        validate=lambda data: _validate_payload(data, allow_executable),
    )
    result = attachment_and_item_transaction(
        plan,
        life_path,
        item_transform,
        item_expected,
        operation="attachment.put",
        journal_dir=journal_directory(config, writable_path=life_path),
        config=config,
    )
    return _result(result, item_id, target, value, "put")


def reference_attachment(
    life_path,
    item_id,
    stored_path,
    item_revision=None,
    attachment_expected_revision=None,
    config=None,
    allow_symlink=False,
    require_revisions=False,
):
    config = config or {}
    target, _root = resolve_attachment_target(
        life_path,
        stored_path,
        root=_attachment_root(config, life_path),
        allow_symlink=allow_symlink,
    )
    if not os.path.isfile(target):
        raise AttachmentTransactionError("Attachment target is not a file: %s" % target)
    item_snapshot = mutation.read_text_snapshot(life_path)
    target_revision = attachment_revision(target)
    item_expected = _resolve_revision(item_revision, item_snapshot.content_hash, require_revisions, "item_revision")
    attachment_expected = _resolve_revision(
        attachment_expected_revision,
        target_revision,
        require_revisions,
        "attachment_revision",
    )
    normalized = _stored_relative_path(life_path, target)
    value = join_value(normalized, target_revision[:HASH_LENGTH])
    id_key = id_key_from_config(config)

    def item_transform(text):
        return _set_reference(text, item_id, id_key, FILE_KEY, value, normalized)

    plan = bytes_plan(target, lambda current: current, attachment_expected)
    result = attachment_and_item_transaction(
        plan,
        life_path,
        item_transform,
        item_expected,
        operation="attachment.reference",
        journal_dir=journal_directory(config, writable_path=life_path),
        config=config,
    )
    return _result(result, item_id, target, value, "reference")


def delete_attachment(
    life_path,
    item_id,
    stored_path,
    item_revision=None,
    attachment_expected_revision=None,
    config=None,
    allow_symlink=False,
    require_revisions=False,
):
    config = config or {}
    target, _root = resolve_attachment_target(
        life_path,
        stored_path,
        root=_attachment_root(config, life_path),
        allow_symlink=allow_symlink,
    )
    item_snapshot = mutation.read_text_snapshot(life_path)
    target_revision = attachment_revision(target)
    if target_revision == mutation.MISSING_HASH:
        raise AttachmentTransactionError("Attachment target does not exist: %s" % target)
    item_expected = _resolve_revision(item_revision, item_snapshot.content_hash, require_revisions, "item_revision")
    attachment_expected = _resolve_revision(
        attachment_expected_revision,
        target_revision,
        require_revisions,
        "attachment_revision",
    )
    normalized = _stored_relative_path(life_path, target)
    id_key = id_key_from_config(config)

    def item_transform(text):
        return _remove_reference(text, item_id, id_key, normalized)

    result = attachment_and_item_transaction(
        delete_plan(target, attachment_expected, kind="bytes"),
        life_path,
        item_transform,
        item_expected,
        operation="attachment.delete",
        journal_dir=journal_directory(config, writable_path=life_path),
        config=config,
    )
    return _result(result, item_id, target, None, "delete")


def attachment_state(life_path, stored_path, config=None, allow_symlink=False):
    target, root = resolve_attachment_target(
        life_path,
        stored_path,
        root=_attachment_root(config or {}, life_path),
        allow_symlink=allow_symlink,
    )
    exists = os.path.exists(target)
    return OrderedDict(
        (
            ("stored_path", _stored_relative_path(life_path, target)),
            ("resolved_path", target),
            ("root", root),
            ("exists", exists),
            ("is_file", os.path.isfile(target)),
            ("is_symlink", os.path.islink(target)),
            ("executable", _is_executable(target) if exists else False),
            ("revision", attachment_revision(target)),
        )
    )


def _set_reference(text, item_id, id_key, key, value, normalized_path):
    from .parser import parse_text

    items, diagnostics = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
    errors = [diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"]
    if errors:
        raise AttachmentTransactionError(errors[0].format())
    matches = [item for item in items if item_id in [str(v) for v in item.details.get(id_key, [])]]
    if len(matches) != 1:
        raise AttachmentTransactionError("Expected exactly one item with %s:%s." % (id_key, item_id))
    existing = []
    for old in matches[0].details.get(key, []):
        try:
            old_path, _digest = split_value(old)
        except Exception:
            existing.append(str(old))
            continue
        if normalize_stored_path(old_path) != normalize_stored_path(normalized_path):
            existing.append(str(old))
    return transform_items_text(
        text,
        [{"id": item_id, "set_details": {key: existing + [value]}}],
        id_key=id_key,
    )


def _remove_reference(text, item_id, id_key, normalized_path):
    from .parser import parse_text

    items, diagnostics = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
    errors = [diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"]
    if errors:
        raise AttachmentTransactionError(errors[0].format())
    matches = [item for item in items if item_id in [str(v) for v in item.details.get(id_key, [])]]
    if len(matches) != 1:
        raise AttachmentTransactionError("Expected exactly one item with %s:%s." % (id_key, item_id))
    updates = {}
    removed = False
    for key in ("file", "dir"):
        kept = []
        for old in matches[0].details.get(key, []):
            try:
                old_path, _digest = split_value(old)
            except Exception:
                kept.append(str(old))
                continue
            if normalize_stored_path(old_path) == normalize_stored_path(normalized_path):
                removed = True
            else:
                kept.append(str(old))
        updates[key] = kept
    if not removed:
        raise AttachmentTransactionError(
            "Item %s does not reference attachment %s." % (item_id, normalized_path)
        )
    return transform_items_text(text, [{"id": item_id, "set_details": updates}], id_key=id_key)


def _result(result, item_id, target, value, action):
    payload = OrderedDict(
        (
            ("action", action),
            ("id", item_id),
            ("path", target),
            ("value", value),
            ("transaction_id", result.transaction_id),
            ("journal_path", result.journal_path),
            ("recovery_required", bool(result.recovery_required)),
            ("targets", []),
        )
    )
    for target_result in result.targets:
        payload["targets"].append(
            OrderedDict(
                (
                    ("path", target_result.path),
                    ("before_revision", target_result.before_hash),
                    ("after_revision", target_result.after_hash),
                    ("created", target_result.created),
                    ("deleted", target_result.deleted),
                )
            )
        )
        if os.path.abspath(target_result.path) == os.path.abspath(target):
            payload["attachment_revision"] = target_result.after_hash
        else:
            payload["item_revision"] = target_result.after_hash
    return payload


def _resolve_revision(provided, actual, required, label):
    if provided in (None, ""):
        if required:
            raise AttachmentTransactionError("%s is required." % label)
        return actual
    return str(provided)


def _attachment_root(config, life_path):
    section = config.get("attachments") if isinstance(config.get("attachments"), dict) else {}
    value = section.get("root") or os.path.dirname(os.path.abspath(life_path))
    if not os.path.isabs(str(value)):
        value = os.path.join(os.path.dirname(os.path.abspath(life_path)), str(value))
    return value


def _stored_relative_path(life_path, target):
    base = os.path.dirname(os.path.abspath(life_path))
    relative = os.path.relpath(target, base).replace(os.sep, "/")
    if not relative.startswith("."):
        relative = "./" + relative
    return normalize_stored_path(relative)


def _is_executable(path):
    try:
        mode = os.stat(path).st_mode
    except OSError:
        return False
    return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)) or os.path.splitext(path)[1].lower() in (
        ".exe", ".com", ".bat", ".cmd", ".ps1", ".sh", ".app", ".msi"
    )


def _reject_executable_target(path, payload, allow):
    if allow:
        return
    extension = os.path.splitext(path)[1].lower()
    if extension in (".exe", ".com", ".bat", ".cmd", ".ps1", ".sh", ".app", ".msi"):
        raise AttachmentTransactionError("Refusing to create a potentially executable attachment: %s" % path)
    if payload.startswith(b"#!"):
        raise AttachmentTransactionError("Refusing to create a script attachment without allow_executable.")


def _validate_payload(payload, allow_executable):
    if not isinstance(payload, bytes):
        return False
    if not allow_executable and payload.startswith(b"#!"):
        raise AttachmentTransactionError("Refusing to write executable script content.")
    return True
