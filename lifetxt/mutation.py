"""Conflict-aware, dependency-free mutation primitives for life.txt files.

The public operation contract is intentionally small:

1. capture a :class:`TextSnapshot` when a caller needs optimistic concurrency;
2. build a :class:`MutationOperation` containing a transform and optional validator;
3. call :func:`apply_text_mutation` with the snapshot hash;
4. handle :class:`MutationConflict` instead of overwriting a newer file.

Every write is serialized with a sidecar lock and committed through the existing
atomic replacement helpers. This module contains no life.txt-specific parsing
so CLI, TUI, Web API, MCP, notification, timer, archive, and undo code can share
it without creating import cycles.
"""

from __future__ import unicode_literals

import codecs
import datetime
import errno
import hashlib
import json
import os
import socket
import time
from collections import namedtuple

from .atomic import atomic_write_bytes


MISSING_HASH = "<missing>"
DEFAULT_LOCK_TIMEOUT = 5.0
DEFAULT_POLL_INTERVAL = 0.05
DEFAULT_STALE_LOCK_AFTER = 300.0


class MutationError(RuntimeError):
    """Base class for mutation failures that callers may present to users."""


class MutationConflict(MutationError):
    """Raised when the target no longer matches the caller's expected hash."""

    def __init__(self, path, expected_hash, actual_hash, operation="mutation"):
        self.path = os.path.abspath(path)
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        self.operation = operation
        message = (
            "%s conflict for %s: expected content hash %s, found %s. "
            "Reload the file and retry."
            % (operation, self.path, expected_hash, actual_hash)
        )
        MutationError.__init__(self, message)


class LockTimeout(MutationError):
    """Raised when another writer keeps the sidecar lock past the timeout."""

    def __init__(self, path, lock_path, timeout, owner=None):
        self.path = os.path.abspath(path)
        self.lock_path = lock_path
        self.timeout = timeout
        self.owner = owner or {}
        owner_text = ""
        if self.owner:
            owner_text = " Lock owner: %s." % json.dumps(
                self.owner, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        MutationError.__init__(
            self,
            "Timed out after %.3fs waiting for the mutation lock for %s.%s"
            % (timeout, self.path, owner_text),
        )


TextSnapshot = namedtuple(
    "TextSnapshot",
    "path text content_hash exists encoding bom newline size mtime_ns",
)
MutationResult = namedtuple(
    "MutationResult",
    "path operation before_hash after_hash changed created snapshot",
)


class MutationOperation(object):
    """A surface-neutral text mutation contract.

    ``transform`` receives the current decoded text and must return replacement
    text. ``validate`` receives replacement text and may raise ``ValueError`` or
    another exception to abort before any write. ``create`` controls whether a
    missing target may be initialized from ``default_text``.
    """

    def __init__(
        self,
        name,
        transform,
        validate=None,
        create=False,
        default_text="",
    ):
        if not name or not str(name).strip():
            raise ValueError("MutationOperation.name must not be empty.")
        if not callable(transform):
            raise TypeError("MutationOperation.transform must be callable.")
        if validate is not None and not callable(validate):
            raise TypeError("MutationOperation.validate must be callable or None.")
        if not isinstance(default_text, str):
            raise TypeError("MutationOperation.default_text must be text.")
        self.name = str(name)
        self.transform = transform
        self.validate = validate
        self.create = bool(create)
        self.default_text = default_text


def hash_bytes(data):
    """Return the lowercase SHA-256 digest for exact file bytes."""
    if not isinstance(data, bytes):
        raise TypeError("hash_bytes expects bytes.")
    return hashlib.sha256(data).hexdigest()


def hash_text(text, encoding="utf-8", bom=False):
    """Hash text using the same encoding rules as a subsequent mutation write."""
    return hash_bytes(_encode_text(text, encoding=encoding, bom=bom))


def read_text_snapshot(path, allow_missing=False, encoding="utf-8"):
    """Read text and return exact bytes metadata suitable for CAS."""
    absolute = os.path.abspath(path)
    try:
        with open(absolute, "rb") as handle:
            data = handle.read()
        stat_result = os.stat(absolute)
    except FileNotFoundError:
        if not allow_missing:
            raise
        return TextSnapshot(
            absolute,
            "",
            MISSING_HASH,
            False,
            encoding,
            False,
            "\n",
            0,
            None,
        )

    bom = data.startswith(codecs.BOM_UTF8)
    payload = data[len(codecs.BOM_UTF8) :] if bom else data
    try:
        text = payload.decode(encoding)
    except UnicodeDecodeError as exc:
        raise MutationError("Cannot decode %s as %s: %s" % (absolute, encoding, exc))
    return TextSnapshot(
        absolute,
        text,
        hash_bytes(data),
        True,
        encoding,
        bom,
        _detect_newline(text),
        len(data),
        getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1000000000)),
    )


class FileLock(object):
    """Cross-platform sidecar lock implemented with exclusive file creation."""

    def __init__(
        self,
        path,
        operation="mutation",
        timeout=DEFAULT_LOCK_TIMEOUT,
        poll_interval=DEFAULT_POLL_INTERVAL,
        stale_after=DEFAULT_STALE_LOCK_AFTER,
        lock_path=None,
        clock=None,
        sleeper=None,
    ):
        self.path = os.path.abspath(path)
        self.lock_path = lock_path or (self.path + ".lifetxt.lock")
        self.operation = str(operation or "mutation")
        self.timeout = max(0.0, float(timeout))
        self.poll_interval = max(0.001, float(poll_interval))
        self.stale_after = None if stale_after is None else max(0.0, float(stale_after))
        self._clock = clock or time.monotonic
        self._sleeper = sleeper or time.sleep
        self._owned = False
        self._token = None

    def acquire(self):
        directory = os.path.dirname(self.lock_path) or "."
        os.makedirs(directory, exist_ok=True)
        deadline = self._clock() + self.timeout
        while True:
            token = "%s-%s-%s" % (
                socket.gethostname(),
                os.getpid(),
                int(time.time() * 1000000000),
            )
            metadata = {
                "version": 1,
                "token": token,
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "operation": self.operation,
                "target": self.path,
                "created": datetime.datetime.now(datetime.timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
            }
            try:
                descriptor = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    raise
                if self._recover_stale_lock():
                    continue
                if self._clock() >= deadline:
                    raise LockTimeout(
                        self.path,
                        self.lock_path,
                        self.timeout,
                        owner=_read_lock_metadata(self.lock_path),
                    )
                self._sleeper(
                    min(self.poll_interval, max(0.0, deadline - self._clock()))
                )
                continue

            try:
                payload = (
                    json.dumps(metadata, ensure_ascii=False, sort_keys=True) + "\n"
                ).encode("utf-8")
                view = memoryview(payload)
                while view:
                    written = os.write(descriptor, view)
                    if written <= 0:
                        raise OSError("Could not write mutation lock metadata.")
                    view = view[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            self._owned = True
            self._token = token
            return self

    def release(self):
        if not self._owned:
            return
        metadata = _read_lock_metadata(self.lock_path)
        if metadata.get("token") == self._token:
            try:
                os.unlink(self.lock_path)
            except FileNotFoundError:
                pass
        self._owned = False
        self._token = None

    def _recover_stale_lock(self):
        if self.stale_after is None:
            return False
        try:
            first_stat = os.stat(self.lock_path)
        except FileNotFoundError:
            return True
        age = max(0.0, time.time() - first_stat.st_mtime)
        if age < self.stale_after:
            return False
        metadata = _read_lock_metadata(self.lock_path)
        if metadata.get("host") == socket.gethostname() and _pid_exists(
            metadata.get("pid")
        ):
            return False
        try:
            second_stat = os.stat(self.lock_path)
        except FileNotFoundError:
            return True
        if not _same_lock_stat(first_stat, second_stat):
            return False
        try:
            os.unlink(self.lock_path)
        except FileNotFoundError:
            return True
        return True

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        return False


def apply_text_mutation(
    path,
    operation,
    expected_hash=None,
    lock_timeout=DEFAULT_LOCK_TIMEOUT,
    poll_interval=DEFAULT_POLL_INTERVAL,
    stale_lock_after=DEFAULT_STALE_LOCK_AFTER,
    encoding="utf-8",
):
    """Apply one validated transform under a lock and optional hash precondition."""
    if not isinstance(operation, MutationOperation):
        raise TypeError("operation must be a MutationOperation.")
    absolute = os.path.abspath(path)
    with FileLock(
        absolute,
        operation=operation.name,
        timeout=lock_timeout,
        poll_interval=poll_interval,
        stale_after=stale_lock_after,
    ):
        before = read_text_snapshot(absolute, allow_missing=True, encoding=encoding)
        if not before.exists and not operation.create:
            raise FileNotFoundError(absolute)
        if expected_hash is not None and expected_hash != before.content_hash:
            raise MutationConflict(
                absolute,
                expected_hash,
                before.content_hash,
                operation=operation.name,
            )
        current_text = before.text if before.exists else operation.default_text
        replacement = operation.transform(current_text)
        if not isinstance(replacement, str):
            raise TypeError("Mutation transform %s must return text." % operation.name)
        if operation.validate is not None:
            validation_result = operation.validate(replacement)
            if validation_result is False:
                raise ValueError("Mutation validator rejected replacement text.")
        replacement_bytes = _encode_text(
            replacement,
            encoding=before.encoding if before.exists else encoding,
            bom=before.bom if before.exists else False,
        )
        after_hash = hash_bytes(replacement_bytes)
        latest = read_text_snapshot(absolute, allow_missing=True, encoding=encoding)
        if latest.content_hash != before.content_hash:
            raise MutationConflict(
                absolute,
                before.content_hash,
                latest.content_hash,
                operation=operation.name,
            )
        changed = (not before.exists) or after_hash != before.content_hash
        if changed:
            atomic_write_bytes(absolute, replacement_bytes)
        after = read_text_snapshot(absolute, allow_missing=False, encoding=encoding)
        if after.content_hash != after_hash:
            raise MutationConflict(
                absolute,
                after_hash,
                after.content_hash,
                operation=operation.name + " post-write verification",
            )
        return MutationResult(
            absolute,
            operation.name,
            before.content_hash,
            after.content_hash,
            changed,
            not before.exists,
            after,
        )


def mutate_text(
    path,
    transform,
    expected_hash=None,
    operation="mutation",
    validate=None,
    create=False,
    default_text="",
    **kwargs
):
    """Convenience wrapper around :class:`MutationOperation`."""
    contract = MutationOperation(
        operation,
        transform,
        validate=validate,
        create=create,
        default_text=default_text,
    )
    return apply_text_mutation(path, contract, expected_hash=expected_hash, **kwargs)


def write_text(
    path,
    text=None,
    expected_hash=None,
    operation="write",
    create=True,
    validate=None,
    transform=None,
    default_text="",
    **kwargs
):
    """Write text through the shared CAS and lock contract.

    ``transform`` keeps semantic mutations inside the acquired lock while still
    routing every authoritative text write through this public entry point.
    Callers must provide either replacement ``text`` or ``transform``, not both.
    """
    if transform is not None:
        if text is not None:
            raise TypeError("write_text accepts either text or transform, not both.")
        if not callable(transform):
            raise TypeError("write_text transform must be callable.")
        return mutate_text(
            path,
            transform,
            expected_hash=expected_hash,
            operation=operation,
            validate=validate,
            create=create,
            default_text=default_text,
            **kwargs
        )
    if not isinstance(text, str):
        raise TypeError("write_text expects text.")
    return mutate_text(
        path,
        lambda current: text,
        expected_hash=expected_hash,
        operation=operation,
        validate=validate,
        create=create,
        default_text=default_text,
        **kwargs
    )


def mutate_json(
    path,
    transform,
    expected_hash=None,
    operation="json mutation",
    create=False,
    default=None,
    pretty=True,
    sort_keys=True,
    **kwargs
):
    """Mutate a JSON document while retaining the same conflict contract."""

    def transform_text(current_text):
        if current_text.strip():
            try:
                value = json.loads(current_text)
            except ValueError as exc:
                raise MutationError(
                    "Cannot parse JSON mutation target %s: %s" % (path, exc)
                )
        else:
            value = default
        replacement = transform(value)
        indent = 2 if pretty else None
        separators = None if pretty else (",", ":")
        return json.dumps(
            replacement,
            ensure_ascii=False,
            indent=indent,
            separators=separators,
            sort_keys=sort_keys,
        ) + "\n"

    return mutate_text(
        path,
        transform_text,
        expected_hash=expected_hash,
        operation=operation,
        create=create,
        default_text=(
            "" if default is None else json.dumps(default, ensure_ascii=False) + "\n"
        ),
        **kwargs
    )


def _encode_text(text, encoding="utf-8", bom=False):
    if not isinstance(text, str):
        raise TypeError("Expected text, got %s." % type(text).__name__)
    payload = text.encode(encoding)
    if bom and encoding.lower().replace("_", "-") in ("utf-8", "utf8"):
        payload = codecs.BOM_UTF8 + payload
    return payload


def _detect_newline(text):
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    if crlf >= lf and crlf >= cr and crlf:
        return "\r\n"
    if cr > lf and cr:
        return "\r"
    return "\n"


def _read_lock_metadata(lock_path):
    try:
        with open(lock_path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _pid_exists(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes

            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                process_query_limited_information,
                False,
                pid,
            )
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except (AttributeError, OSError, ValueError):
            return False
    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM
    except (AttributeError, OverflowError, ValueError):
        return False
    return True


def _same_lock_stat(first, second):
    first_mtime = getattr(first, "st_mtime_ns", int(first.st_mtime * 1000000000))
    second_mtime = getattr(second, "st_mtime_ns", int(second.st_mtime * 1000000000))
    first_inode = getattr(first, "st_ino", 0)
    second_inode = getattr(second, "st_ino", 0)
    inode_matches = not first_inode or not second_inode or first_inode == second_inode
    return (
        inode_matches
        and first_mtime == second_mtime
        and first.st_size == second.st_size
    )
