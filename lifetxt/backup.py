"""Disaster-recovery backup core (`lifetxt-backup-v1`, #836/#841).

Implements a self-describing, integrity-verifiable local snapshot format,
independent of #731's periodic Git-commit worker: that mechanism protects
against *edit/history* mistakes inside an existing local repository, while
this module protects against host loss, disk failure, device loss, or
destruction of the repository itself. The two are never substitutes for
each other.

Format (see ``docs/en/backup-format-v1.md``): one ``.ltbackup`` file is a
ZIP archive containing ``manifest.json`` plus one ``files/<index>`` member
per included source file. The whole archive is built in memory and
committed through the shared :func:`lifetxt.atomic.atomic_write_bytes`
primitive (the same commit-or-nothing pattern already established by
``lifetxt/lifetxtz_codec.py``, #692/#693), so an interrupted build can
never leave a file at the destination path that this module -- or a
directory listing -- would mistake for a complete backup: either the
temporary file (which atomic_write_bytes itself always cleans up on
failure) exists with a name nothing here ever globs for, or the finished
``.ltbackup`` file exists, never something in between.

Snapshot consistency boundary: each source file's bytes are read
independently and as close together as this process can manage, but this
is a best-effort sequential read, not a cross-file transaction -- lifetxt
has no existing multi-file read-lock/snapshot primitive to reuse for
arbitrary file reads (the existing transaction/journal machinery covers
*writes*). Each file's manifest entry records the modification time
observed at read time so an operator can see whether files were captured
at meaningfully different moments.

Secret/data-selection policy: this module only ever archives the explicit
``paths`` its caller supplies. It never walks a directory tree on its own,
so it can never accidentally sweep up an rclone config, an OS credential
store, or an unrelated file merely because it happened to sit in a nearby
directory -- the caller (CLI/#842) is responsible for building that
explicit list from workspace configuration, and is documented to exclude
credential/secret paths by construction (they are never part of a
workspace's ``sources``).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import zipfile
from collections import OrderedDict
from io import BytesIO

from .atomic import atomic_write_bytes

__all__ = [
    "BACKUP_FORMAT_VERSION",
    "DEFAULT_BACKUP_SUFFIX",
    "BackupError",
    "BackupResult",
    "VerifyResult",
    "RestoreResult",
    "PruneResult",
    "create_backup",
    "verify_backup",
    "restore_backup",
    "list_backups",
    "prune_backups",
    "default_backup_filename",
    "utc_now_iso",
]

#: The only backup format version this module produces, and the only one
#: it accepts without an explicit, clearly-labeled "unsupported version"
#: refusal (#845). Bump this, and add an explicit migration/refusal note
#: to the format doc, before changing the manifest shape in any
#: backward-incompatible way.
BACKUP_FORMAT_VERSION = "lifetxt-backup-v1"

MANIFEST_NAME = "manifest.json"
_FILES_PREFIX = "files/"

#: Every backup this module creates uses this filename suffix, so
#: `list_backups`/`prune_backups` can distinguish lifetxt's own backup
#: files from unrelated files an operator may also keep in the same
#: directory without having to open and parse every file in it.
DEFAULT_BACKUP_SUFFIX = ".ltbackup"

#: Fixed ZIP member metadata, matching lifetxtz_codec.py's own convention,
#: so two backups of byte-identical input content differ only in
#: manifest.json's own created_at/source_identity fields.
_FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)
_FIXED_EXTERNAL_ATTR = 0o600 << 16

#: Decompression resource limits, checked against each member's *declared*
#: (not inflated) size before any decompression -- mirrors lifetxtz_codec's
#: own safety boundary against a maliciously/accidentally huge archive.
_MAX_MANIFEST_BYTES = 8 * 1024 * 1024
_MAX_FILE_BYTES = 512 * 1024 * 1024


class BackupError(ValueError):
    """Raised for a malformed, corrupt, incomplete, or unsupported backup
    artifact. Always raised before any destination is mutated."""


class BackupResult:
    """The outcome of :func:`create_backup`."""

    __slots__ = ("path", "manifest")

    def __init__(self, path, manifest):
        self.path = path
        self.manifest = manifest


class VerifyResult:
    """The outcome of :func:`verify_backup`. ``ok`` is False whenever
    ``errors`` is non-empty; ``manifest`` is populated whenever it could be
    parsed at all (even for an otherwise-invalid backup), so a caller can
    still show *what* the backup claims to be."""

    __slots__ = ("ok", "manifest", "errors")

    def __init__(self, ok, manifest, errors):
        self.ok = ok
        self.manifest = manifest
        self.errors = list(errors)


class RestoreResult:
    """The outcome of :func:`restore_backup`."""

    __slots__ = ("dry_run", "restored", "conflicts", "errors")

    def __init__(self, dry_run, restored, conflicts, errors):
        self.dry_run = dry_run
        self.restored = list(restored)
        self.conflicts = list(conflicts)
        self.errors = list(errors)

    @property
    def ok(self):
        return not self.errors and not self.conflicts


class PruneResult:
    """The outcome of :func:`prune_backups`."""

    __slots__ = ("dry_run", "kept", "deleted", "errors", "ignored")

    def __init__(self, dry_run, kept, deleted, errors, ignored):
        self.dry_run = dry_run
        self.kept = list(kept)
        self.deleted = list(deleted)
        self.errors = list(errors)
        self.ignored = list(ignored)


def utc_now_iso():
    """Current UTC time as an offset-aware ISO 8601 string with
    microsecond precision (``...Z``). Microsecond, not second,
    granularity is deliberate: :func:`default_backup_filename` derives
    its filename from this, and two runs of ``run_scheduled`` completing
    within the same second must not collide on the same filename."""
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


#: Backward-compatible alias; new code should prefer utc_now_iso().
_utc_now_iso = utc_now_iso


def default_backup_filename(created_at=None):
    """Return the deterministic filename ``create_backup`` uses by default:
    ``lifetxt-<UTC timestamp>.ltbackup``, sortable by name and safe on
    every supported filesystem (no ``:`` characters)."""
    stamp = created_at or utc_now_iso()
    safe = stamp.replace(":", "").replace("+00:00", "Z")
    return "lifetxt-%s%s" % (safe, DEFAULT_BACKUP_SUFFIX)


def _relative_archive_path(path, base_dir, used_names):
    """Return the manifest ``path`` field for one source file: a forward-
    slash relative path under ``base_dir`` when the file is actually under
    it, otherwise a disambiguated basename. Either way the result is a
    single documented selection policy every backup uses, never an
    absolute path or one containing ``..`` -- so it can always be safely
    joined onto an arbitrary restore destination later (#846)."""
    candidate = None
    if base_dir:
        try:
            rel = os.path.relpath(os.path.abspath(path), os.path.abspath(base_dir))
        except ValueError:
            rel = None
        if rel is not None and not rel.startswith("..") and not os.path.isabs(rel):
            candidate = rel.replace(os.sep, "/")
    if candidate is None:
        candidate = os.path.basename(path) or "file"
    name = candidate
    n = 1
    while name in used_names:
        stem, dot, ext = candidate.rpartition(".")
        name = (
            ("%s-%d%s%s" % (stem or candidate, n, dot, ext))
            if dot
            else ("%s-%d" % (candidate, n))
        )
        n += 1
    used_names.add(name)
    return name


def create_backup(
    paths,
    output_path,
    *,
    base_dir=None,
    source_identity=None,
    lifetxt_version=None,
    created_at=None,
):
    """Create a `lifetxt-backup-v1` archive at ``output_path`` from
    ``paths``. Only files that currently exist are included (a source
    that has already been removed is silently skipped -- consistent with
    the shared multi-file input policy elsewhere in this project -- but is
    still visible via ``manifest["requested_paths"]``).

    ``base_dir``, when given, lets multi-file/workspace input preserve its
    relative directory structure in the manifest (and therefore on
    restore); otherwise each file is recorded by its own (disambiguated)
    basename.

    Raises :class:`BackupError` if no requested path currently exists.
    Never mutates any source file; never leaves a partial file at
    ``output_path`` (see the module docstring for why).
    """
    if not paths:
        raise BackupError("create_backup requires at least one source path.")
    if os.path.lexists(output_path):
        raise BackupError(
            "Refusing to create a backup at '%s': it already exists. Each "
            "backup file name is unique to the moment it was created; a "
            "collision here would mean silently overwriting a previous "
            "valid backup." % output_path
        )

    created_at = created_at or utc_now_iso()
    entries = []
    used_names = set()
    for path in paths:
        if not path or not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            data = handle.read()
        stat = os.stat(path)
        mtime = datetime.datetime.fromtimestamp(
            stat.st_mtime, tz=datetime.timezone.utc
        ).isoformat(timespec="seconds")
        entries.append(
            {
                "path": _relative_archive_path(path, base_dir, used_names),
                "source_path": os.path.abspath(path),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "mtime": mtime,
                "data": data,
            }
        )

    if not entries:
        raise BackupError(
            "None of the requested paths exist; refusing to create an "
            "empty backup: %r" % (list(paths),)
        )

    manifest = OrderedDict(
        (
            ("format", BACKUP_FORMAT_VERSION),
            ("status", "complete"),
            ("created_at", created_at),
            ("lifetxt_version", lifetxt_version),
            ("source_identity", source_identity),
            ("requested_paths", list(paths)),
            (
                "files",
                [
                    OrderedDict(
                        (
                            ("path", e["path"]),
                            ("archive_name", "%s%d" % (_FILES_PREFIX, i)),
                            ("size", e["size"]),
                            ("sha256", e["sha256"]),
                            ("mtime", e["mtime"]),
                        )
                    )
                    for i, e in enumerate(entries)
                ],
            ),
            ("file_count", len(entries)),
            ("total_bytes", sum(e["size"] for e in entries)),
        )
    )
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    ).encode("utf-8")

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        _write_member(zip_file, MANIFEST_NAME, manifest_bytes)
        for i, e in enumerate(entries):
            _write_member(zip_file, "%s%d" % (_FILES_PREFIX, i), e["data"])

    atomic_write_bytes(output_path, buffer.getvalue())
    manifest.pop("requested_paths", None)
    return BackupResult(output_path, manifest)


def _write_member(zip_file, name, data):
    info = zipfile.ZipInfo(name, date_time=_FIXED_DATE_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = _FIXED_EXTERNAL_ATTR
    zip_file.writestr(info, data)


def _open_zip(path):
    try:
        return zipfile.ZipFile(path, "r")
    except (zipfile.BadZipFile, OSError, EOFError) as exc:
        raise BackupError("'%s' is not a valid backup archive: %s" % (path, exc))


def _load_manifest(zip_file, path):
    if MANIFEST_NAME not in zip_file.namelist():
        raise BackupError("'%s' has no manifest.json." % path)
    info = zip_file.getinfo(MANIFEST_NAME)
    if info.file_size > _MAX_MANIFEST_BYTES:
        raise BackupError(
            "'%s': manifest.json declares %d bytes, exceeding the %d byte "
            "limit; refused before decompressing."
            % (path, info.file_size, _MAX_MANIFEST_BYTES)
        )
    try:
        raw = zip_file.read(MANIFEST_NAME)
    except (zipfile.BadZipFile, EOFError, OSError) as exc:
        raise BackupError(
            "'%s': manifest.json could not be decompressed: %s" % (path, exc)
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BackupError("'%s': manifest.json is not valid UTF-8: %s" % (path, exc))
    try:
        manifest = json.loads(text)
    except ValueError as exc:
        raise BackupError("'%s': manifest.json is not valid JSON: %s" % (path, exc))
    if not isinstance(manifest, dict):
        raise BackupError("'%s': manifest.json must be a JSON object." % path)
    return manifest


def verify_backup(path):
    """Read-only structural and integrity verification of the backup
    archive at ``path``. Never mutates the archive, any source, or any
    current lifetxt data.

    Returns a :class:`VerifyResult`; ``ok`` is only True when every check
    below passes:

    - the file is a well-formed ZIP archive;
    - it has a parseable ``manifest.json``;
    - ``manifest["format"]`` is a version this module supports (an
      unrecognized/future version is reported as its own distinct error,
      never silently accepted);
    - ``manifest["status"] == "complete"`` (an interrupted/partial build
      is rejected, never treated as restorable);
    - every ``files[]`` entry's recorded relative ``path`` is safe (no
      absolute path, no ``..`` traversal, no empty/"." path);
    - every archive member the manifest declares is actually present, and
      every member present is declared (no unexpected/missing entries);
    - each declared member's *declared* size is checked against its
      resource-limit ceiling before it is decompressed at all;
    - each member's actual decompressed size and SHA-256 match the
      manifest exactly.
    """
    errors = []
    manifest = None
    try:
        zip_file = _open_zip(path)
    except BackupError as exc:
        return VerifyResult(False, None, [str(exc)])

    try:
        try:
            manifest = _load_manifest(zip_file, path)
        except BackupError as exc:
            return VerifyResult(False, None, [str(exc)])

        fmt = manifest.get("format")
        if fmt != BACKUP_FORMAT_VERSION:
            errors.append(
                "Unsupported backup format %r in '%s' (this lifetxt "
                "supports %r). Refused rather than best-effort read."
                % (fmt, path, BACKUP_FORMAT_VERSION)
            )
            return VerifyResult(False, manifest, errors)

        if manifest.get("status") != "complete":
            errors.append(
                "'%s' is not marked complete (status=%r); it looks like an "
                "interrupted or partial backup and is refused."
                % (path, manifest.get("status"))
            )

        files = manifest.get("files")
        if not isinstance(files, list):
            errors.append("'%s': manifest.files is missing or not a list." % path)
            return VerifyResult(False, manifest, errors)

        declared_names = set()
        for entry in files:
            if not isinstance(entry, dict):
                errors.append("'%s': a manifest.files entry is not an object." % path)
                continue
            rel = entry.get("path")
            archive_name = entry.get("archive_name")
            if not isinstance(rel, str) or not rel or rel in (".", ".."):
                errors.append("'%s': unsafe or missing recorded path %r." % (path, rel))
                continue
            normalized = rel.replace("\\", "/")
            if (
                normalized.startswith("/")
                or normalized.startswith("../")
                or "/../" in ("/" + normalized + "/")
            ):
                errors.append(
                    "'%s': recorded path %r escapes the restore destination "
                    "(path traversal); refused." % (path, rel)
                )
                continue
            if not isinstance(archive_name, str) or not archive_name.startswith(
                _FILES_PREFIX
            ):
                errors.append(
                    "'%s': entry for %r has no valid archive_name." % (path, rel)
                )
                continue
            declared_names.add(archive_name)
            if archive_name not in zip_file.namelist():
                errors.append(
                    "'%s': manifest declares %r but the archive does not "
                    "contain it." % (path, archive_name)
                )
                continue
            info = zip_file.getinfo(archive_name)
            declared_size = entry.get("size")
            if info.file_size > _MAX_FILE_BYTES:
                errors.append(
                    "'%s': %r declares %d bytes, exceeding the %d byte "
                    "limit; refused before decompressing."
                    % (path, archive_name, info.file_size, _MAX_FILE_BYTES)
                )
                continue
            try:
                data = zip_file.read(archive_name)
            except (zipfile.BadZipFile, EOFError, OSError) as exc:
                errors.append(
                    "'%s': %r could not be decompressed: %s" % (path, archive_name, exc)
                )
                continue
            if isinstance(declared_size, int) and len(data) != declared_size:
                errors.append(
                    "'%s': %r size mismatch (manifest says %d bytes, "
                    "archive has %d)." % (path, rel, declared_size, len(data))
                )
                continue
            actual_sha256 = hashlib.sha256(data).hexdigest()
            expected_sha256 = entry.get("sha256")
            if actual_sha256 != expected_sha256:
                errors.append(
                    "'%s': %r checksum mismatch (expected %s, got %s); the "
                    "backup is corrupt or was tampered with."
                    % (path, rel, expected_sha256, actual_sha256)
                )

        extra_members = {
            n
            for n in zip_file.namelist()
            if n.startswith(_FILES_PREFIX) and n not in declared_names
        }
        if extra_members:
            errors.append(
                "'%s' contains archive members not declared in the "
                "manifest: %s" % (path, sorted(extra_members))
            )
    finally:
        zip_file.close()

    return VerifyResult(not errors, manifest, errors)


def restore_backup(path, destination_dir, *, overwrite=False, dry_run=False):
    """Restore the backup archive at ``path`` into ``destination_dir``.

    Always runs the exact same integrity checks as :func:`verify_backup`
    before any mutation is attempted; an invalid backup raises
    :class:`BackupError` and nothing is written.

    Each file is restored at ``destination_dir/<manifest path>`` --
    verified during the pre-flight :func:`verify_backup` pass to never
    escape ``destination_dir``. An existing destination file is reported
    as a conflict and left untouched unless ``overwrite=True``.
    ``dry_run=True`` computes and returns the same plan (``restored``)
    without writing anything. Every actual write goes through the shared
    atomic-replace primitive, so a failure partway through never leaves a
    half-written destination file, only either the old file or the new
    one.
    """
    verify_result = verify_backup(path)
    if not verify_result.ok:
        raise BackupError(
            "Refusing to restore '%s': it failed verification:\n- %s"
            % (path, "\n- ".join(verify_result.errors))
        )
    manifest = verify_result.manifest

    destination_dir = os.path.abspath(destination_dir)
    restored = []
    conflicts = []
    errors = []

    zip_file = _open_zip(path)
    try:
        for entry in manifest["files"]:
            rel = entry["path"]
            dest = os.path.abspath(os.path.join(destination_dir, rel))
            if os.path.commonpath([destination_dir, dest]) != destination_dir:
                # Already refused by verify_backup's own path-safety check,
                # but re-checked here as defense in depth against any
                # future manifest shape this function did not anticipate.
                errors.append("Refusing unsafe restore path: %r" % rel)
                continue
            if os.path.exists(dest) and not overwrite:
                conflicts.append(dest)
                continue
            if dry_run:
                restored.append(dest)
                continue
            try:
                data = zip_file.read(entry["archive_name"])
                os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
                atomic_write_bytes(dest, data)
                restored.append(dest)
            except OSError as exc:
                errors.append("Failed to restore %r: %s" % (dest, exc))
    finally:
        zip_file.close()

    return RestoreResult(dry_run, restored, conflicts, errors)


def list_backups(backup_dir):
    """List every ``*.ltbackup`` file in ``backup_dir``, newest first by
    the manifest's own ``created_at`` (never filesystem mtime, which a
    copy/restore/clock change can disturb independently of when the
    backup was actually made).

    Returns a list of ``(filename, VerifyResult)`` pairs; a file that does
    not verify is still listed (with ``VerifyResult.ok is False``) so
    ``backup status``/``prune`` can report it rather than silently
    ignoring it, but it is never counted as a valid generation by
    :func:`prune_backups`.
    """
    if not os.path.isdir(backup_dir):
        return []
    rows = []
    for name in os.listdir(backup_dir):
        if not name.endswith(DEFAULT_BACKUP_SUFFIX):
            continue
        full = os.path.join(backup_dir, name)
        if not os.path.isfile(full):
            continue
        result = verify_backup(full)
        rows.append((name, result))

    def sort_key(row):
        name, result = row
        created_at = (result.manifest or {}).get("created_at") or ""
        return created_at, name

    rows.sort(key=sort_key, reverse=True)
    return rows


def prune_backups(backup_dir, *, keep_last, dry_run=False):
    """Delete completed backups beyond the newest ``keep_last`` under
    ``backup_dir``. Never touches anything outside ``backup_dir``, never
    touches a file that does not end in :data:`DEFAULT_BACKUP_SUFFIX`, and
    never counts a backup that fails :func:`verify_backup` (including an
    incomplete/interrupted one) as one of the generations being kept or
    pruned -- it is reported separately in ``ignored`` instead, and is
    never deleted by this function.

    ``keep_last`` must be a positive integer; retention is always
    explicit at the call site (see #842's/#847's CLI wiring for the
    "absent/disabled means no deletion" default).
    """
    if not isinstance(keep_last, int) or keep_last < 1:
        raise BackupError("keep_last must be a positive integer, got %r." % keep_last)

    rows = list_backups(backup_dir)
    valid = [(name, result) for name, result in rows if result.ok]
    ignored = [name for name, result in rows if not result.ok]

    kept = [name for name, _result in valid[:keep_last]]
    to_delete = [name for name, _result in valid[keep_last:]]

    deleted = []
    errors = []
    if not dry_run:
        for name in to_delete:
            full = os.path.join(backup_dir, name)
            try:
                os.unlink(full)
                deleted.append(name)
            except OSError as exc:
                errors.append("Failed to delete %r: %s" % (name, exc))
    else:
        deleted = list(to_delete)

    return PruneResult(dry_run, kept, deleted, errors, ignored)
