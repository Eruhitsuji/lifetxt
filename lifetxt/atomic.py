import json
import os
import stat
import tempfile


def atomic_write_text(path, text, encoding="utf-8", newline="\n"):
    """Write text by replacing the target with a fully written temp file."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    handle = None
    temp_path = None
    try:
        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding=encoding,
            newline=newline,
            delete=False,
            dir=directory,
            prefix=".lifetxt-",
            suffix=".tmp",
        )
        temp_path = handle.name
        handle.write(text)
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


def atomic_write_bytes(path, data):
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
    indent = 2 if pretty else None
    separators = None if pretty else (",", ":")
    text = json.dumps(data, ensure_ascii=False, indent=indent, separators=separators)
    atomic_write_text(path, text + "\n")


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
