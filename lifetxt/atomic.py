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
        os.replace(temp_path, path)
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
