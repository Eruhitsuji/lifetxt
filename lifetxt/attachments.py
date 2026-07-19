"""Associating external files and directories with life.txt items.

An item can point at a file or a directory on disk:

    [ ] T Review spec id:t1 file:./docs/spec.md#sha256=1a2b3c4d5e6f7890
    [ ] T Sort assets id:t2 dir:./assets/images

The value is a path with an optional content hash appended as a fragment, so a
hash always travels with the path it belongs to even when one item references
several files.

Portability is the hard part, and it is handled here rather than at each call
site:

* Paths are stored with forward slashes. Windows accepts them in every API, so
  one canonical form works on every platform and in every shell.
* Relative paths resolve against the directory of the life.txt file that
  contains the item, not the process working directory. A file and the notes
  that reference it move together; the shell you happen to run from does not.
* `~` expands to the user's home directory.
* Absolute paths, drive letters, and UNC paths are accepted but reported as
  non-portable, because they only work on the machine that wrote them.
* Case differences are reported, because a path that opens on Windows or macOS
  can fail on Linux.
"""

import hashlib
import os
import posixpath
import re
import unicodedata


#: Detail keys that hold a filesystem path.
FILE_KEY = "file"
DIR_KEY = "dir"
ATTACHMENT_KEYS = (FILE_KEY, DIR_KEY)

#: Fragment that carries the content hash. The *last* occurrence is the
#: separator, so a path may itself contain "#".
HASH_MARKER = "#sha256="

#: Stored hash length. 16 hex characters is 64 bits, far more than enough to
#: notice that a file changed, and short enough to keep a line readable.
HASH_LENGTH = 16

#: Directories skipped when hashing a directory tree. Without this, `dir:.`
#: would hash .git and node_modules and never produce a stable value.
DEFAULT_IGNORES = (
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".DS_Store",
    "Thumbs.db",
)

#: Guards so a stray `dir:/` cannot hang the process.
DEFAULT_MAX_FILES = 2000
DEFAULT_MAX_BYTES = 200 * 1024 * 1024

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
_HEX = re.compile(r"^[0-9a-f]+$")


class AttachmentError(ValueError):
    """Raised when an attachment value or target cannot be handled."""


# ---------------------------------------------------------------------------
# value parsing and formatting
# ---------------------------------------------------------------------------


def split_value(value):
    """Split ``path#sha256=hash`` into ``(path, hash)``.

    The last marker wins so that a path containing "#" still parses. An empty
    or malformed hash is reported rather than silently dropped, because a
    truncated hash would otherwise look like "no hash recorded".
    """
    text = str(value if value is not None else "").strip()
    index = text.rfind(HASH_MARKER)
    if index < 0:
        return text, ""
    path = text[:index]
    digest = text[index + len(HASH_MARKER):].strip().lower()
    if not path:
        raise AttachmentError("Attachment value %r has no path before %s." % (value, HASH_MARKER))
    if digest and not _HEX.match(digest):
        raise AttachmentError(
            "Attachment hash %r is not hexadecimal. Expected %s<hex>." % (digest, HASH_MARKER)
        )
    return path, digest


def join_value(path, digest=""):
    """Build a detail value from a path and an optional hash."""
    path = normalize_stored_path(path)
    if not digest:
        return path
    return "%s%s%s" % (path, HASH_MARKER, str(digest).strip().lower())


def normalize_stored_path(path):
    """Canonical stored form: forward slashes, no redundant segments.

    Backslashes are treated as separators. A POSIX filename may legally
    contain one, but a life.txt is meant to be portable, and silently keeping a
    Windows-only separator breaks every other platform.
    """
    text = str(path if path is not None else "").strip()
    if not text:
        return ""
    text = text.replace("\\", "/")
    # Collapse "./a//b" without resolving ".." (which would need the filesystem).
    prefix = "./" if text.startswith("./") else ""
    collapsed = posixpath.normpath(text)
    if collapsed == ".":
        return "."
    if prefix and not collapsed.startswith(("../", "/")) and not _WINDOWS_DRIVE.match(collapsed):
        collapsed = "./" + collapsed
    return collapsed


def resolve_path(value, base_dir=None):
    """Absolute filesystem path for an attachment value.

    ``base_dir`` is the directory of the life.txt file that holds the item.
    """
    path, _digest = split_value(value)
    return resolve_raw_path(path, base_dir)


def resolve_raw_path(path, base_dir=None):
    text = normalize_stored_path(path)
    if not text:
        raise AttachmentError("Attachment path is empty.")
    expanded = os.path.expanduser(text)
    if os.path.isabs(expanded) or _WINDOWS_DRIVE.match(expanded):
        return os.path.normpath(expanded)
    base = base_dir or "."
    return os.path.normpath(os.path.join(base, expanded))


# ---------------------------------------------------------------------------
# hashing
# ---------------------------------------------------------------------------


def hash_file(path, length=HASH_LENGTH):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()[:length]


def hash_directory(path, length=HASH_LENGTH, ignores=None, max_files=DEFAULT_MAX_FILES,
                   max_bytes=DEFAULT_MAX_BYTES):
    """Recursive tree hash: every file's relative path and content.

    Entries are sorted by their POSIX-form relative path so the value does not
    depend on directory iteration order, which differs across filesystems.
    """
    ignores = set(ignores if ignores is not None else DEFAULT_IGNORES)
    entries = []
    total_bytes = 0
    for root, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(name for name in dirnames if name not in ignores)
        for name in sorted(filenames):
            if name in ignores:
                continue
            full = os.path.join(root, name)
            relative = os.path.relpath(full, path).replace(os.sep, "/")
            try:
                size = os.path.getsize(full)
            except OSError:
                # A file that vanished mid-walk is reported, not skipped, so the
                # hash never silently describes a different tree.
                raise AttachmentError("Could not read %s while hashing %s." % (full, path))
            total_bytes += size
            entries.append((relative, full))
            if len(entries) > max_files:
                raise AttachmentError(
                    "Directory %s has more than %d files. Raise attachments.max_files "
                    "or point dir: at a smaller directory." % (path, max_files)
                )
            if total_bytes > max_bytes:
                raise AttachmentError(
                    "Directory %s exceeds %d bytes. Raise attachments.max_bytes "
                    "or point dir: at a smaller directory." % (path, max_bytes)
                )

    digest = hashlib.sha256()
    for relative, full in sorted(entries):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hash_file(full, length=64).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()[:length]


def hash_target(path, is_dir=None, **kwargs):
    """Hash a file or directory, choosing by what is actually on disk."""
    if is_dir is None:
        is_dir = os.path.isdir(path)
    if is_dir:
        return hash_directory(path, **kwargs)
    return hash_file(path, length=kwargs.get("length", HASH_LENGTH))


# ---------------------------------------------------------------------------
# inspection
# ---------------------------------------------------------------------------


#: Status values reported for each attachment.
STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_CHANGED = "changed"
STATUS_UNHASHED = "unhashed"
STATUS_WRONG_TYPE = "wrong_type"
STATUS_ERROR = "error"


def attachment_records(item, base_dir=None, config=None, verify=True):
    """Describe every file:/dir: value on one item.

    Each record carries the stored value, the resolved path, the status, and
    any portability notes, so callers can render or act on it without touching
    the filesystem again.
    """
    settings = _settings(config)
    records = []
    for key in ATTACHMENT_KEYS:
        for value in item.details.get(key, []):
            records.append(_describe(key, value, base_dir, settings, verify))
    return records


def _describe(key, value, base_dir, settings, verify):
    record = {
        "key": key,
        "value": str(value),
        "path": "",
        "resolved": "",
        "hash": "",
        "actual_hash": "",
        "status": STATUS_OK,
        "notes": [],
        "exists": False,
        "is_dir": False,
    }
    try:
        path, digest = split_value(value)
    except AttachmentError as exc:
        record["status"] = STATUS_ERROR
        record["notes"].append(str(exc))
        return record

    record["path"] = normalize_stored_path(path)
    record["hash"] = digest
    record["notes"].extend(portability_notes(path))

    try:
        resolved = resolve_raw_path(path, base_dir)
    except AttachmentError as exc:
        record["status"] = STATUS_ERROR
        record["notes"].append(str(exc))
        return record
    record["resolved"] = resolved

    exists = os.path.exists(resolved)
    record["exists"] = exists
    if not exists:
        record["status"] = STATUS_MISSING
        return record

    record["is_dir"] = os.path.isdir(resolved)
    if key == FILE_KEY and record["is_dir"]:
        record["status"] = STATUS_WRONG_TYPE
        record["notes"].append("Target is a directory; use dir: instead of file:.")
        return record
    if key == DIR_KEY and not record["is_dir"]:
        record["status"] = STATUS_WRONG_TYPE
        record["notes"].append("Target is a file; use file: instead of dir:.")
        return record

    case_note = case_mismatch_note(resolved)
    if case_note:
        record["notes"].append(case_note)

    if not digest:
        record["status"] = STATUS_UNHASHED
        return record

    if not verify:
        return record

    try:
        actual = hash_target(
            resolved,
            is_dir=record["is_dir"],
            length=max(len(digest), HASH_LENGTH),
            ignores=settings["ignores"],
            max_files=settings["max_files"],
            max_bytes=settings["max_bytes"],
        )
    except (AttachmentError, OSError) as exc:
        record["status"] = STATUS_ERROR
        record["notes"].append(str(exc))
        return record

    record["actual_hash"] = actual[: len(digest)]
    if record["actual_hash"] != digest:
        record["status"] = STATUS_CHANGED
    return record


def portability_notes(path):
    """Report anything that would break on another machine or platform."""
    notes = []
    raw = str(path or "")
    if "\\" in raw:
        notes.append("Backslash separators are Windows-only; stored as forward slashes.")
    if _WINDOWS_DRIVE.match(raw):
        notes.append("Drive letters only resolve on the machine that has that drive.")
    elif raw.startswith("//") or raw.startswith("\\\\"):
        notes.append("UNC paths only resolve on a network with that share mounted.")
    elif os.path.isabs(os.path.expanduser(raw)) and not raw.startswith("~"):
        notes.append("Absolute paths are machine-specific; prefer a path relative to the life.txt file.")
    if raw != unicodedata.normalize("NFC", raw):
        notes.append("Path is not NFC-normalized; macOS and Linux may disagree on the name.")
    tail = posixpath.basename(normalize_stored_path(raw))
    if tail != tail.rstrip(" .") and tail not in (".", ".."):
        notes.append("Trailing spaces or dots in a name are invalid on Windows.")
    return notes


def case_mismatch_note(resolved):
    """Detect a path that only opens because the filesystem ignores case.

    Windows and macOS resolve `README.md` for `readme.md`; Linux does not. A
    file that works locally but breaks for a colleague is worth a warning.
    """
    directory, name = os.path.split(resolved)
    if not name:
        return ""
    try:
        entries = os.listdir(directory or ".")
    except OSError:
        return ""
    if name in entries:
        return ""
    lowered = name.lower()
    for entry in entries:
        if entry.lower() == lowered:
            return "On-disk name is %r but the path says %r; this fails on case-sensitive filesystems." % (
                entry,
                name,
            )
    return ""


def _settings(config):
    from .config import config_section

    section = config_section(config or {}, "attachments")
    ignores = section.get("ignore")
    if isinstance(ignores, str):
        ignores = [part.strip() for part in ignores.split(",") if part.strip()]
    return {
        "ignores": list(ignores) if ignores else list(DEFAULT_IGNORES),
        "max_files": _positive(section.get("max_files"), DEFAULT_MAX_FILES),
        "max_bytes": _positive(section.get("max_bytes"), DEFAULT_MAX_BYTES),
    }


def _positive(value, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


# ---------------------------------------------------------------------------
# updating
# ---------------------------------------------------------------------------


def refreshed_value(record, settings=None):
    """The value this attachment should have once its hash is current."""
    if record["status"] in (STATUS_MISSING, STATUS_ERROR, STATUS_WRONG_TYPE):
        return None
    settings = settings or _settings(None)
    digest = record.get("actual_hash")
    if not digest:
        digest = hash_target(
            record["resolved"],
            is_dir=record["is_dir"],
            length=HASH_LENGTH,
            ignores=settings["ignores"],
            max_files=settings["max_files"],
            max_bytes=settings["max_bytes"],
        )
    digest = digest[:HASH_LENGTH]
    return join_value(record["path"], digest)


def update_item_hashes(item, base_dir=None, config=None):
    """Rewrite file:/dir: values with current hashes.

    Returns a list of ``(key, old_value, new_value)`` for what changed.
    """
    settings = _settings(config)
    changes = []
    for key in ATTACHMENT_KEYS:
        values = item.details.get(key)
        if not values:
            continue
        updated = []
        for value in values:
            record = _describe(key, value, base_dir, settings, verify=True)
            new_value = refreshed_value(record, settings)
            if new_value is None or new_value == str(value):
                updated.append(str(value))
                continue
            updated.append(new_value)
            changes.append((key, str(value), new_value))
        item.details[key] = updated
    return changes


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------

#: W401 missing, W402 changed, W403 wrong type, W404 non-portable,
#: W405 case mismatch, W407 malformed value.
DIAGNOSTIC_CODES = {
    STATUS_MISSING: "W401",
    STATUS_CHANGED: "W402",
    STATUS_WRONG_TYPE: "W403",
    STATUS_ERROR: "W407",
}


def attachment_diagnostics(items, config=None, verify=True):
    """Warnings for every file:/dir: value across the given items.

    Each item is resolved against its own source file's directory, so a
    multi-file load checks each life.txt against its own neighbours.
    """
    from .model import Diagnostic

    diagnostics = []
    for item in items:
        base_dir = item_base_dir(item)
        for record in attachment_records(item, base_dir=base_dir, config=config, verify=verify):
            diagnostics.extend(_record_diagnostics(record, item, Diagnostic))
    return diagnostics


def _record_diagnostics(record, item, Diagnostic):
    line = item.line
    out = []
    status = record["status"]
    code = DIAGNOSTIC_CODES.get(status)
    if code == "W401":
        out.append(
            Diagnostic(
                "warning",
                "W401",
                "%s:%s does not exist (looked in %s)."
                % (record["key"], record["path"], record["resolved"]),
                line,
            )
        )
    elif code == "W402":
        out.append(
            Diagnostic(
                "warning",
                "W402",
                "%s:%s changed since its hash was recorded (%s -> %s). Run `lifetxt files --update`."
                % (record["key"], record["path"], record["hash"], record["actual_hash"]),
                line,
            )
        )
    elif code == "W403":
        out.append(
            Diagnostic(
                "warning",
                "W403",
                "%s:%s has the wrong kind of target. %s"
                % (record["key"], record["path"], " ".join(record["notes"])),
                line,
            )
        )
    elif code == "W407":
        out.append(
            Diagnostic(
                "warning",
                "W407",
                "%s:%s could not be read. %s"
                % (record["key"], record["value"], " ".join(record["notes"])),
                line,
            )
        )

    for note in record["notes"]:
        if status == STATUS_WRONG_TYPE or status == STATUS_ERROR:
            continue
        if note.startswith("On-disk name is"):
            out.append(
                Diagnostic("warning", "W405", "%s:%s %s" % (record["key"], record["path"], note), line)
            )
        else:
            out.append(
                Diagnostic("warning", "W404", "%s:%s %s" % (record["key"], record["path"], note), line)
            )
    return out


def item_base_dir(item, default_path=None):
    """Directory a relative attachment path is resolved against.

    ``item.source`` is only populated when several files were loaded at once,
    so callers that know which file they read must pass ``default_path``.
    Falling back to the working directory would make the same life.txt resolve
    differently depending on where the command was run, which is exactly what
    storing relative paths is meant to avoid.
    """
    source = getattr(item, "source", None) or default_path
    if not source or source == "stdin" or source == "-":
        return "."
    return os.path.dirname(os.path.abspath(source)) or "."


def has_attachments(item):
    return any(item.details.get(key) for key in ATTACHMENT_KEYS)
