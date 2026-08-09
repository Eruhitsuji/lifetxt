"""Atomic compatibility helpers backed by the shared mutation contract.

Historically this module exposed the project's lowest-level text and JSON write
helpers.  Many callers still import those names directly, so removing them
would force every CLI, TUI, Web, MCP, timer, and notification path to migrate in
one breaking change.

``atomic_write_text`` and ``atomic_write_json`` now act as compatibility
facades: they route replacement writes through :mod:`lifetxt.mutation`, which
adds the shared sidecar lock, in-lock reread, conflict detection during the
transform, and post-write verification.  ``atomic_write_bytes`` intentionally
remains the private low-level commit primitive used by that mutation layer; it
must not call back into it or the two modules would recurse.
"""

import json
import os
import stat
import tempfile
import time

#: Platforms where a transient PermissionError during os.replace is retried.
#: The single shared definition for this policy: lifetxt.transaction_journal
#: imports these two constants rather than defining its own copy (see the
#: replace-retry-policy-dedup change). Its own retry *loop* stays separate --
#: it interleaves a fault_point() hook per attempt for the incident-hardened,
#: fault-injection-tested crash-recovery test matrix, which this module's
#: replace_with_retry() does not (and should not) provide.
_REPLACE_PERMISSION_RETRY_OS_NAMES = frozenset(("nt",))

#: Delay in seconds before each retry, in order. Matches the bounded budget
#: already established by lifetxt.transaction_journal (#86 / #94).
_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS = (0.01, 0.05, 0.1, 0.25)


def replace_with_retry(source, destination):
    """Replace destination with source, retrying a transient Windows PermissionError.

    On Windows, antivirus, an indexer, a backup agent, or cloud sync can hold a
    transient handle on the destination path, making ``os.replace`` fail with
    ``WinError 5`` for a few milliseconds. This retries only that specific,
    transient condition: a bounded number of attempts with short delays
    between them, on platforms in ``_REPLACE_PERMISSION_RETRY_OS_NAMES`` only.
    Any other exception, or exhausting the retry budget, propagates unchanged.
    """
    retry_enabled = os.name in _REPLACE_PERMISSION_RETRY_OS_NAMES
    retry_delays = (
        tuple(_REPLACE_PERMISSION_RETRY_DELAYS_SECONDS) if retry_enabled else ()
    )
    attempts = len(retry_delays) + 1
    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt >= len(retry_delays):
                raise
            time.sleep(float(retry_delays[attempt]))


def atomic_write_text(path, text, encoding="utf-8", newline="\n"):
    """Replace a text file through the shared mutation layer.

    The public signature is retained for compatibility.  ``newline`` keeps the
    previous ``open(..., newline=...)`` write semantics before the resulting
    text is handed to the conflict-aware writer.
    """
    if not isinstance(text, str):
        raise TypeError("atomic_write_text expects text.")
    translated = _translate_newlines(text, newline)

    # Import lazily to avoid a module cycle: mutation imports only
    # atomic_write_bytes, the deliberately unlocked commit primitive below.
    from .mutation import write_text as shared_write_text

    return shared_write_text(
        path,
        translated,
        operation="atomic_write_text",
        create=True,
        encoding=encoding,
    )


def atomic_write_bytes(path, data):
    """Commit exact bytes with an atomic replace.

    This is the low-level primitive used *inside* the shared mutation lock.  New
    application code should use ``lifetxt.mutation`` (or the text/JSON
    compatibility helpers above) rather than calling this function directly.
    """
    if not isinstance(data, bytes):
        raise TypeError("atomic_write_bytes expects bytes.")
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    handle = None
    temp_path = None
    try:
        handle = tempfile.NamedTemporaryFile(
            "wb",
            delete=False,
            dir=directory,
            prefix=".lifetxt-",
            suffix=".tmp",
        )
        temp_path = handle.name
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        _preserve_mode(path, temp_path)
        replace_with_retry(temp_path, path)
        _fsync_directory(directory)
    finally:
        if handle is not None and not handle.closed:
            handle.close()
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def atomic_write_json(path, data, pretty=True):
    """Replace a JSON file through the shared mutation layer."""
    indent = 2 if pretty else None
    separators = None if pretty else (",", ":")
    text = json.dumps(data, ensure_ascii=False, indent=indent, separators=separators)
    return atomic_write_text(path, text + "\n")


def _translate_newlines(text, newline):
    """Match TextIO's write-time newline translation without opening a file."""
    if newline is None:
        replacement = os.linesep
    elif newline in ("", "\n"):
        return text
    elif newline in ("\r", "\r\n"):
        replacement = newline
    else:
        raise ValueError("illegal newline value: %r" % (newline,))
    if replacement == "\n":
        return text
    return text.replace("\n", replacement)


def _preserve_mode(path, temp_path):
    """Keep existing permission bits when replacing a file."""
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        return
    try:
        os.chmod(temp_path, mode)
    except OSError:
        pass


def _fsync_directory(directory):
    """Persist the directory entry after os.replace where the platform permits."""
    if os.name == "nt":
        return
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = None
    try:
        descriptor = os.open(directory, flags)
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        if descriptor is not None:
            os.close(descriptor)
