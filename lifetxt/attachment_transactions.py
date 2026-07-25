"""Journal-backed attachment content and life.txt reference operations."""

from __future__ import unicode_literals

import hashlib
import io
import json
import mimetypes
import os
import platform
import stat
import zipfile
from collections import OrderedDict

from . import mutation
from .attachments import (DIR_KEY, FILE_KEY, HASH_LENGTH, DEFAULT_IGNORES, DEFAULT_MAX_BYTES, DEFAULT_MAX_FILES, hash_directory, join_value, normalize_stored_path, split_value)
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
    transaction_id=None,
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
        transaction_id=transaction_id,
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
    transaction_id=None,
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
        transaction_id=transaction_id,
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
    transaction_id=None,
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
        transaction_id=transaction_id,
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
    is_file = os.path.isfile(target)
    is_dir = os.path.isdir(target)
    mime_type = mimetypes.guess_type(target)[0] if is_file else ("inode/directory" if is_dir else None)
    size = os.path.getsize(target) if is_file else None
    file_type = _file_type(target) if exists else "missing"
    policy = _content_policy(config or {}, target, mime_type=mime_type, size=size)
    return OrderedDict(
        (
            ("stored_path", _stored_relative_path(life_path, target)),
            ("resolved_path", target),
            ("root", root),
            ("exists", exists),
            ("is_file", is_file),
            ("is_directory", is_dir),
            ("is_symlink", os.path.islink(target)),
            ("file_type", file_type),
            ("mime_type", mime_type),
            ("size", size),
            ("executable", _is_executable(target) if exists else False),
            ("policy", policy),
            ("revision", directory_revision(target, config=config) if is_dir else attachment_revision(target)),
        )
    )



def read_bounded_file(path, max_bytes=None, chunk_size=1024 * 1024):
    """Read a source file in bounded chunks and reject growth past policy."""
    limit = int(max_bytes if max_bytes is not None else DEFAULT_MAX_BYTES)
    payload = bytearray()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(max(4096, int(chunk_size)))
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > limit:
                raise AttachmentTransactionError(
                    "Attachment source exceeds the configured maximum of %d bytes." % limit
                )
    return bytes(payload)


def put_attachment_from_path(life_path, item_id, stored_path, source_path, config=None, **kwargs):
    config = config or {}
    policy = _attachment_settings(config)
    payload = read_bounded_file(source_path, max_bytes=policy["max_file_bytes"])
    mime_type = mimetypes.guess_type(source_path)[0] or "application/octet-stream"
    _enforce_mime_policy(config, stored_path, mime_type)
    result = put_attachment(life_path, item_id, stored_path, payload, config=config, **kwargs)
    result["source"] = os.path.abspath(source_path)
    result["mime_type"] = mime_type
    result["size"] = len(payload)
    return result


def directory_revision(path, config=None):
    settings = _attachment_settings(config or {})
    return hash_directory(
        path,
        length=64,
        ignores=settings["ignores"],
        max_files=settings["max_files"],
        max_bytes=settings["max_bytes"],
    )


def reference_directory(
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
        life_path, stored_path, root=_attachment_root(config, life_path), allow_symlink=allow_symlink
    )
    if not os.path.isdir(target):
        raise AttachmentTransactionError("Directory attachment target is not a directory: %s" % target)
    if _file_type(target) != "directory":
        raise AttachmentTransactionError("Unsupported directory attachment type: %s" % _file_type(target))
    digest = directory_revision(target, config=config)
    directory_expected = _resolve_revision(
        attachment_expected_revision, digest, require_revisions, "attachment_revision"
    )
    if directory_expected != digest:
        raise AttachmentTransactionError("Directory attachment revision changed before reference.")
    normalized = _stored_relative_path(life_path, target)
    value = join_value(normalized, digest[:HASH_LENGTH])
    snapshot = mutation.read_text_snapshot(life_path)
    expected = _resolve_revision(item_revision, snapshot.content_hash, require_revisions, "item_revision")
    id_key = id_key_from_config(config)
    # A sidecar lock serializes lifetxt-aware directory writers while the tree
    # revision is rechecked and the life.txt reference is committed.
    with mutation.FileLock(target, operation="attachment.directory_reference"):
        latest = directory_revision(target, config=config)
        if latest != directory_expected:
            raise AttachmentTransactionError("Directory attachment revision changed before commit.")
        result = mutation.write_text(
            life_path,
            expected_hash=expected,
            operation="attachment.directory_reference",
            create=False,
            transform=lambda text: _set_reference(text, item_id, id_key, DIR_KEY, value, normalized),
        )
    return OrderedDict((
        ("action", "directory-reference"),
        ("id", item_id),
        ("path", target),
        ("value", value),
        ("attachment_revision", digest),
        ("item_revision", result.after_hash),
        ("file_count_limit", _attachment_settings(config)["max_files"]),
        ("byte_limit", _attachment_settings(config)["max_bytes"]),
    ))



def resolve_package_source(life_path, source_directory, config=None, allow_symlink=False):
    """Resolve a server-side package source under the configured remote source root."""
    config = config or {}
    section = config.get("attachments") if isinstance(config.get("attachments"), dict) else {}
    root = section.get("remote_source_root") or _attachment_root(config, life_path)
    target, root_abs = resolve_attachment_target(
        life_path, source_directory, root=root, allow_symlink=allow_symlink
    )
    if not os.path.isdir(target):
        raise AttachmentTransactionError("Package source is not a confined directory: %s" % target)
    return target, root_abs

def package_directory(
    life_path,
    item_id,
    source_directory,
    stored_path,
    config=None,
    include_hidden=False,
    allow_symlink=False,
    **kwargs
):
    config = config or {}
    target, _root = resolve_attachment_target(
        life_path, stored_path, root=_attachment_root(config, life_path), allow_symlink=allow_symlink
    )
    if not str(target).lower().endswith(".zip"):
        raise AttachmentTransactionError("Directory packages must use a .zip attachment path.")
    payload, manifest = build_directory_package(
        source_directory,
        config=config,
        include_hidden=include_hidden,
        allow_symlink=allow_symlink,
    )
    result = put_attachment(
        life_path,
        item_id,
        stored_path,
        payload,
        config=config,
        allow_symlink=allow_symlink,
        **kwargs
    )
    result["action"] = "package"
    result["package"] = manifest
    result["mime_type"] = "application/zip"
    return result


def build_directory_package(source_directory, config=None, include_hidden=False, allow_symlink=False):
    config = config or {}
    source = os.path.abspath(source_directory)
    if not os.path.isdir(source):
        raise AttachmentTransactionError("Package source is not a directory: %s" % source)
    settings = _attachment_settings(config)
    records = []
    total = 0
    for root, dirnames, filenames in os.walk(source, followlinks=allow_symlink):
        dirnames[:] = sorted(name for name in dirnames if name not in settings["ignores"] and (include_hidden or not name.startswith(".")))
        for name in sorted(filenames):
            if name in settings["ignores"] or (not include_hidden and name.startswith(".")):
                continue
            full = os.path.join(root, name)
            if os.path.islink(full) and not allow_symlink:
                raise AttachmentTransactionError("Package source contains a symlink: %s" % full)
            if _file_type(full) != "file":
                raise AttachmentTransactionError("Package source contains a non-regular file: %s" % full)
            relative = os.path.relpath(full, source).replace(os.sep, "/")
            if relative.startswith("../") or relative.startswith("/"):
                raise AttachmentTransactionError("Package entry escapes its root: %s" % relative)
            size = os.path.getsize(full)
            total += size
            records.append((relative, full, size))
            if len(records) > settings["max_files"]:
                raise AttachmentTransactionError("Directory package exceeds %d files." % settings["max_files"])
            if total > settings["max_bytes"]:
                raise AttachmentTransactionError("Directory package exceeds %d bytes." % settings["max_bytes"])
    manifest_files = []
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, full, size in records:
            data = read_bounded_file(full, max_bytes=settings["max_file_bytes"])
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100600 << 16
            archive.writestr(info, data)
            manifest_files.append(OrderedDict((
                ("path", relative),
                ("size", size),
                ("sha256", hashlib.sha256(data).hexdigest()),
            )))
        manifest = OrderedDict((
            ("version", 1),
            ("source_name", os.path.basename(source)),
            ("file_count", len(manifest_files)),
            ("total_bytes", total),
            ("files", manifest_files),
        ))
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        info = zipfile.ZipInfo("lifetxt-package-manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100600 << 16
        archive.writestr(info, manifest_bytes)
    payload = buffer.getvalue()
    if len(payload) > settings["max_file_bytes"]:
        raise AttachmentTransactionError("Compressed directory package exceeds %d bytes." % settings["max_file_bytes"])
    manifest["package_sha256"] = hashlib.sha256(payload).hexdigest()
    manifest["package_bytes"] = len(payload)
    return payload, manifest


def reconcile_attachment(
    life_path,
    item_id,
    stored_path,
    key=FILE_KEY,
    item_revision=None,
    recorded_revision=None,
    attachment_expected_revision=None,
    config=None,
    require_revisions=False,
):
    config = config or {}
    target, _root = resolve_attachment_target(life_path, stored_path, root=_attachment_root(config, life_path))
    if key == DIR_KEY:
        if not os.path.isdir(target):
            raise AttachmentTransactionError("Directory attachment does not exist: %s" % target)
        actual = directory_revision(target, config=config)
    else:
        if not os.path.isfile(target):
            raise AttachmentTransactionError("File attachment does not exist: %s" % target)
        actual = attachment_revision(target)
    attachment_expected = _resolve_revision(
        attachment_expected_revision, actual, require_revisions, "attachment_revision"
    )
    if attachment_expected != actual:
        raise AttachmentTransactionError("Attachment revision changed before reconcile.")
    normalized = _stored_relative_path(life_path, target)
    snapshot = mutation.read_text_snapshot(life_path)
    expected = _resolve_revision(item_revision, snapshot.content_hash, require_revisions, "item_revision")
    id_key = id_key_from_config(config)
    if recorded_revision:
        _assert_recorded_reference(snapshot.text, item_id, id_key, key, normalized, recorded_revision)

    with mutation.FileLock(target, operation="attachment.reconcile.target"):
        latest = directory_revision(target, config=config) if key == DIR_KEY else attachment_revision(target)
        if latest != attachment_expected:
            raise AttachmentTransactionError("Attachment revision changed before reconcile commit.")
        value = join_value(normalized, latest[:HASH_LENGTH])
        result = mutation.write_text(
            life_path,
            expected_hash=expected,
            operation="attachment.reconcile",
            create=False,
            transform=lambda text: _set_reference(text, item_id, id_key, key, value, normalized),
        )
        final_revision = directory_revision(target, config=config) if key == DIR_KEY else attachment_revision(target)
        if final_revision != latest:
            try:
                mutation.write_text(
                    life_path, snapshot.text, expected_hash=result.after_hash,
                    operation="attachment.reconcile.rollback", create=False,
                )
            except Exception as rollback_error:
                raise AttachmentTransactionError(
                    "Attachment changed during reconcile and the life.txt rollback failed: %s" % rollback_error
                )
            raise AttachmentTransactionError(
                "Attachment changed during reconcile; the life.txt reference was restored."
            )
    return OrderedDict((
        ("action", "reconcile"),
        ("id", item_id),
        ("key", key),
        ("path", target),
        ("value", value),
        ("attachment_revision", latest),
        ("item_revision", result.after_hash),
    ))

def prepare_open_reference(
    life_path,
    stored_path,
    attachment_expected_revision=None,
    metadata_revision=None,
    config=None,
    require_revisions=False,
    record=True,
):
    config = config or {}
    state = attachment_state(life_path, stored_path, config=config)
    if not state["exists"] or state["file_type"] not in ("file", "directory"):
        raise AttachmentTransactionError("Attachment is not openable: %s" % state["resolved_path"])
    if not state["policy"]["allowed"]:
        raise AttachmentTransactionError("Attachment open policy rejected the target: %s" % "; ".join(state["policy"]["problems"]))
    expected = _resolve_revision(attachment_expected_revision, state["revision"], require_revisions, "attachment_revision")
    if expected != state["revision"]:
        raise AttachmentTransactionError("Attachment revision changed before open.")
    command = _platform_open_command(state["resolved_path"])
    report = OrderedDict((
        ("action", "open-reference"),
        ("path", state["resolved_path"]),
        ("stored_path", state["stored_path"]),
        ("attachment_revision", state["revision"]),
        ("platform", platform.system().lower() or os.name),
        ("command", command),
        ("metadata_written", False),
    ))
    if record:
        metadata_path = _open_metadata_path(config, life_path)
        from .timezone_policy import utcnow
        now_value = utcnow().replace(microsecond=0).isoformat().replace("+00:00", "Z")
        snapshot = mutation.read_text_snapshot(metadata_path, allow_missing=True)
        metadata_expected = _resolve_revision(metadata_revision, snapshot.content_hash, require_revisions, "metadata_revision")
        def transform(value):
            value = value if isinstance(value, dict) else {}
            records = value.setdefault("references", {})
            row = records.setdefault(state["stored_path"], {})
            row["count"] = int(row.get("count") or 0) + 1
            row["last_opened_at"] = now_value
            row["attachment_revision"] = state["revision"]
            row["platform"] = report["platform"]
            value["version"] = 1
            return value
        meta_result = mutation.mutate_json(
            metadata_path,
            transform,
            expected_hash=metadata_expected,
            operation="attachment.open_metadata",
            create=not snapshot.exists,
            default={"version": 1, "references": {}},
        )
        report["metadata_written"] = True
        report["metadata_path"] = metadata_path
        report["metadata_revision"] = meta_result.after_hash
    return report



def read_attachment_chunk(
    life_path,
    stored_path,
    offset=0,
    limit=65536,
    attachment_expected_revision=None,
    config=None,
):
    """Return one bounded base64-ready attachment chunk with revision metadata."""
    import base64

    config = config or {}
    target, _root = resolve_attachment_target(
        life_path, stored_path, root=_attachment_root(config, life_path)
    )
    if not os.path.isfile(target):
        raise AttachmentTransactionError("Attachment target is not a regular file: %s" % target)
    revision = attachment_revision(target)
    if attachment_expected_revision not in (None, "") and str(attachment_expected_revision) != revision:
        raise AttachmentTransactionError("Attachment revision changed before chunk read.")
    settings = _attachment_settings(config)
    section = config.get("attachments") if isinstance(config.get("attachments"), dict) else {}
    remote_max = max(1, min(int(section.get("remote_chunk_bytes") or 65536), 1024 * 1024))
    bounded_limit = max(1, min(int(limit), settings["max_file_bytes"], remote_max, 1024 * 1024))
    bounded_offset = max(0, int(offset))
    size = os.path.getsize(target)
    if size > settings["max_file_bytes"]:
        raise AttachmentTransactionError("Attachment exceeds the configured file limit.")
    if bounded_offset > size:
        raise AttachmentTransactionError("Attachment chunk offset exceeds file size.")
    with open(target, "rb") as handle:
        handle.seek(bounded_offset)
        data = handle.read(bounded_limit)
    latest = attachment_revision(target)
    if latest != revision:
        raise AttachmentTransactionError("Attachment changed during chunk read.")
    next_offset = bounded_offset + len(data)
    return OrderedDict((
        ("path", target),
        ("stored_path", _stored_relative_path(life_path, target)),
        ("attachment_revision", revision),
        ("size", size),
        ("offset", bounded_offset),
        ("limit", bounded_limit),
        ("bytes", len(data)),
        ("content_base64", base64.b64encode(data).decode("ascii")),
        ("next_offset", next_offset),
        ("eof", next_offset >= size),
    ))


def inspect_directory_package(
    life_path,
    stored_path,
    attachment_expected_revision=None,
    config=None,
):
    """Validate a deterministic package and its embedded integrity manifest."""
    config = config or {}
    target, _root = resolve_attachment_target(
        life_path, stored_path, root=_attachment_root(config, life_path)
    )
    if not os.path.isfile(target):
        raise AttachmentTransactionError("Directory package does not exist: %s" % target)
    revision = attachment_revision(target)
    if attachment_expected_revision not in (None, "") and str(attachment_expected_revision) != revision:
        raise AttachmentTransactionError("Directory package revision changed before inspection.")
    settings = _attachment_settings(config)
    if os.path.getsize(target) > settings["max_file_bytes"]:
        raise AttachmentTransactionError("Directory package exceeds the configured file limit.")
    try:
        with zipfile.ZipFile(target, "r") as archive:
            names = archive.namelist()
            if "lifetxt-package-manifest.json" not in names:
                raise AttachmentTransactionError("Directory package is missing lifetxt-package-manifest.json.")
            raw = archive.read("lifetxt-package-manifest.json")
            manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=OrderedDict)
            records = manifest.get("files") if isinstance(manifest, dict) else None
            if not isinstance(records, list):
                raise AttachmentTransactionError("Directory package manifest files must be an array.")
            problems = []
            if len(names) != len(set(names)):
                problems.append("duplicate package entry")
            if len(records) > settings["max_files"]:
                problems.append("manifest exceeds configured file count")
            seen = set()
            total = 0
            for row in records:
                if not isinstance(row, dict):
                    problems.append("manifest entry is not an object")
                    continue
                name = str(row.get("path") or "")
                if not name or name.startswith("/") or ".." in name.split("/"):
                    problems.append("unsafe manifest path: %s" % name)
                    continue
                if name in seen:
                    problems.append("duplicate manifest path: %s" % name)
                    continue
                seen.add(name)
                if name not in names:
                    problems.append("missing package entry: %s" % name)
                    continue
                info = archive.getinfo(name)
                if info.file_size > settings["max_file_bytes"]:
                    problems.append("entry exceeds configured file limit: %s" % name)
                    continue
                data = archive.read(name)
                total += len(data)
                if total > settings["max_bytes"]:
                    problems.append("package contents exceed configured total limit")
                if int(row.get("size", -1)) != len(data):
                    problems.append("size mismatch: %s" % name)
                if str(row.get("sha256") or "") != hashlib.sha256(data).hexdigest():
                    problems.append("sha256 mismatch: %s" % name)
            package_entries = set(names) - {"lifetxt-package-manifest.json"}
            extras = sorted(package_entries - seen)
            for name in extras:
                problems.append("unmanifested package entry: %s" % name)
            if int(manifest.get("file_count", -1)) != len(records):
                problems.append("file_count mismatch")
            if int(manifest.get("total_bytes", -1)) != total:
                problems.append("total_bytes mismatch")
    except (OSError, ValueError, zipfile.BadZipFile, KeyError) as exc:
        raise AttachmentTransactionError("Cannot inspect directory package: %s" % exc)
    return OrderedDict((
        ("ok", not problems),
        ("path", target),
        ("stored_path", _stored_relative_path(life_path, target)),
        ("attachment_revision", revision),
        ("manifest", manifest),
        ("problems", problems),
    ))

def _assert_recorded_reference(text, item_id, id_key, key, normalized_path, recorded_revision):
    from .parser import parse_text
    items, diagnostics = parse_text(text, id_key=id_key, check_ids=False, check_references=False)
    errors = [row for row in diagnostics if row.severity == "error"]
    if errors:
        raise AttachmentTransactionError(errors[0].format())
    matches = [item for item in items if item_id in [str(v) for v in item.details.get(id_key, [])]]
    if len(matches) != 1:
        raise AttachmentTransactionError("Expected exactly one item with %s:%s." % (id_key, item_id))
    for value in matches[0].details.get(key, []):
        path, digest = split_value(value)
        if normalize_stored_path(path) == normalize_stored_path(normalized_path):
            if str(digest) != str(recorded_revision)[:len(str(digest))]:
                raise AttachmentTransactionError("Recorded attachment revision does not match the item reference.")
            return
    raise AttachmentTransactionError("Item does not contain the requested attachment reference.")


def _attachment_settings(config):
    section = config.get("attachments") if isinstance(config.get("attachments"), dict) else {}
    ignores = section.get("ignores")
    return {
        "max_files": max(1, int(section.get("max_files") or DEFAULT_MAX_FILES)),
        "max_bytes": max(1, int(section.get("max_bytes") or DEFAULT_MAX_BYTES)),
        "max_file_bytes": max(1, int(section.get("max_file_bytes") or section.get("max_bytes") or DEFAULT_MAX_BYTES)),
        "ignores": tuple(ignores) if isinstance(ignores, (list, tuple)) else tuple(DEFAULT_IGNORES),
    }


def _content_policy(config, path, mime_type=None, size=None):
    problems = []
    file_type = _file_type(path) if os.path.exists(path) else "missing"
    if file_type not in ("file", "directory", "missing"):
        problems.append("non-regular filesystem target")
    if file_type == "file":
        try:
            _enforce_mime_policy(config, path, mime_type or "application/octet-stream")
        except AttachmentTransactionError as exc:
            problems.append(str(exc))
        limit = _attachment_settings(config)["max_file_bytes"]
        if size is not None and size > limit:
            problems.append("file exceeds %d bytes" % limit)
    return OrderedDict((("allowed", not problems), ("problems", problems)))


def _enforce_mime_policy(config, path, mime_type):
    section = config.get("attachments") if isinstance(config.get("attachments"), dict) else {}
    allowed = section.get("allowed_mime") or []
    blocked = section.get("blocked_mime") or []
    mime = str(mime_type or "application/octet-stream").lower()
    if any(_mime_match(mime, pattern) for pattern in blocked):
        raise AttachmentTransactionError("MIME type %s is blocked for %s." % (mime, path))
    if allowed and not any(_mime_match(mime, pattern) for pattern in allowed):
        raise AttachmentTransactionError("MIME type %s is not in attachments.allowed_mime." % mime)


def _mime_match(value, pattern):
    pattern = str(pattern).lower().strip()
    return pattern == value or (pattern.endswith("/*") and value.startswith(pattern[:-1]))


def _file_type(path):
    try:
        mode = os.lstat(path).st_mode
    except OSError:
        return "missing"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
        return "device"
    return "other"


def _platform_open_command(path):
    system = platform.system().lower()
    if system == "windows":
        return ["cmd", "/c", "start", "", path]
    if system == "darwin":
        return ["open", path]
    return ["xdg-open", path]


def _open_metadata_path(config, life_path):
    section = config.get("attachments") if isinstance(config.get("attachments"), dict) else {}
    value = section.get("open_state_file") or ".lifetxt-attachment-open.json"
    if not os.path.isabs(str(value)):
        value = os.path.join(os.path.dirname(os.path.abspath(life_path)), str(value))
    return os.path.abspath(value)

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
