"""Validated, atomic configuration writes with a bounded backup record.

Every configuration write (``config set``, ``config unset``, ``config migrate``)
routes through :func:`write_config`. It validates the proposed document before
committing, refuses unsupported-version or invalid documents, keeps a bounded
rotation of ``.bak`` backups next to the file, and writes atomically so an
interrupted write can never truncate a good configuration.
"""

from __future__ import unicode_literals

import json
import os
import shutil
from collections import OrderedDict

from .atomic import atomic_write_text
from .config_validation import is_supported_version, validate_config


class ConfigWriteError(ValueError):
    """Raised when a configuration write is refused."""


DEFAULT_MAX_BACKUPS = 3


def serialize_config(data):
    clean = OrderedDict(
        (key, value)
        for key, value in (data or {}).items()
        if key not in ("_path", "_active_workspace")
    )
    return json.dumps(clean, ensure_ascii=False, indent=2) + "\n"


def _rotate_backups(path, max_backups):
    if max_backups <= 0 or not os.path.exists(path):
        return None
    # Shift older backups: file.bak2 <- file.bak1 <- file.bak
    for index in range(max_backups - 1, 0, -1):
        older = "%s.bak%d" % (path, index)
        newer = "%s.bak%d" % (path, index + 1)
        if os.path.exists(older):
            try:
                if os.path.exists(newer):
                    os.remove(newer)
                os.replace(older, newer)
            except OSError:
                pass
    backup = "%s.bak1" % path
    try:
        if os.path.exists(backup):
            os.remove(backup)
        shutil.copy2(path, backup)
        return backup
    except OSError:
        return None


def write_config(path, data, validate=True, max_backups=DEFAULT_MAX_BACKUPS,
                 allow_unsupported=False):
    """Validate and atomically write ``data`` to ``path``.

    Returns a small report describing the write. Raises ``ConfigWriteError``
    when validation fails or the version is unsupported (unless
    ``allow_unsupported`` is set, which is reserved for recovery tooling).
    """
    if not path:
        raise ConfigWriteError("No configuration path to write.")

    diagnostics = []
    if validate:
        diagnostics = validate_config(data)
        errors = [row for row in diagnostics if row["severity"] == "error"]
        if errors:
            summary = "; ".join(row["message"] for row in errors[:5])
            raise ConfigWriteError("Refusing to write invalid configuration: %s" % summary)
    if not allow_unsupported and not is_supported_version(data):
        raise ConfigWriteError(
            "Refusing to write an unsupported config_version. Upgrade lifetxt first."
        )

    backup = _rotate_backups(path, max_backups)
    text = serialize_config(data)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    atomic_write_text(path, text)
    return OrderedDict(
        (
            ("path", os.path.abspath(path)),
            ("backup", os.path.abspath(backup) if backup else None),
            ("bytes", len(text.encode("utf-8"))),
            ("warnings", [row for row in diagnostics if row["severity"] != "error"]),
        )
    )
