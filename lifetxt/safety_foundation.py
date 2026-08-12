"""Release-safety and Format 1.0 foundation services.

The module is dependency-free so the same checks run in the minimal install,
normal CLI workflows, CI, and future remote capability negotiation.
"""

from __future__ import unicode_literals

import ast
import codecs
import datetime
import importlib
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import unicodedata
from collections import OrderedDict

from .model import Diagnostic
from .mutation import MutationConflict, read_text_snapshot, write_text
from .parser import FORMAT_VERSION, parse_text
from .timeutil import format_datetime, parse_datetime


CANON_VERSION = "LIFETXT_CANON_V1"
CAPABILITY_VERSION = "1"
SCHEMA_VERSION = "1"
FORMAT_DIRECTIVE_RE = re.compile(
    r"^#!\s*(?:format_version|format-version)\s*:\s*(\S+)\s*$", re.I
)
TIMEZONE_DIRECTIVE_RE = re.compile(r"^#!\s*timezone\s*:\s*(\S+)\s*$", re.I)
DETAIL_KEY_RE = re.compile(r"(?:^|\s)([A-Za-z][A-Za-z0-9_-]*):")


def read_text_exact(path):
    with open(path, "rb") as handle:
        data = handle.read()
    bom = data.startswith(codecs.BOM_UTF8)
    payload = data[len(codecs.BOM_UTF8) :] if bom else data
    return payload.decode("utf-8"), data, bom


def file_directives(text):
    values = OrderedDict()
    duplicates = []
    for number, line in enumerate(str(text).splitlines(), 1):
        if not line.startswith("#!"):
            continue
        body = line[2:].strip()
        if ":" not in body:
            continue
        key, value = body.split(":", 1)
        normalized = key.strip().lower().replace("-", "_")
        if normalized in values:
            duplicates.append((normalized, number))
        values[normalized] = value.strip()
    return values, duplicates


def format_version_report(text):
    directives, duplicates = file_directives(text)
    value = directives.get("format_version")
    if value is None:
        state = "unversioned"
        message = "No #! format_version: directive; parse using compatibility mode."
    elif value == FORMAT_VERSION:
        state = "current"
        message = "Format version is current."
    else:
        state = "unsupported"
        message = "Unsupported format version %s; migrate before writing." % value
    return OrderedDict(
        (
            ("current", FORMAT_VERSION),
            ("declared", value),
            ("state", state),
            ("message", message),
            ("duplicate_directives", [key for key, _line in duplicates]),
        )
    )


def canonicalize_text(text):
    """Return deterministic draft Format 1.0 canonical text."""
    value = unicodedata.normalize("NFC", str(text))
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip(" \t") for line in value.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + ("\n" if lines else "")


def canonical_issues(text, raw_bytes=None, bom=False, source=None):
    issues = []
    if bom or (raw_bytes is not None and raw_bytes.startswith(codecs.BOM_UTF8)):
        issues.append(
            _policy_diag(
                "warning",
                "F101",
                "UTF-8 BOM is not canonical.",
                source,
                1,
                1,
                "Remove the BOM.",
            )
        )
    if "\r\n" in text:
        issues.append(
            _policy_diag(
                "warning",
                "F102",
                "CRLF line endings are not canonical.",
                source,
                1,
                1,
                "Convert line endings to LF.",
            )
        )
    elif "\r" in text:
        issues.append(
            _policy_diag(
                "warning",
                "F103",
                "CR line endings are not canonical.",
                source,
                1,
                1,
                "Convert line endings to LF.",
            )
        )
    if unicodedata.normalize("NFC", text) != text:
        issues.append(
            _policy_diag(
                "warning",
                "F104",
                "Text is not NFC-normalized.",
                source,
                1,
                1,
                "Normalize Unicode to NFC.",
            )
        )
    for line_no, line in enumerate(text.splitlines(), 1):
        if line.rstrip(" \t") != line:
            issues.append(
                _policy_diag(
                    "warning",
                    "F105",
                    "Trailing whitespace is not canonical.",
                    source,
                    line_no,
                    len(line.rstrip(" \t")) + 1,
                    "Remove trailing spaces or tabs.",
                )
            )
        for match in DETAIL_KEY_RE.finditer(line):
            key = match.group(1)
            if key.lower() != key:
                issues.append(
                    _policy_diag(
                        "warning",
                        "F106",
                        "Detail keys are case-sensitive and canonical keys are lowercase: %s"
                        % key,
                        source,
                        line_no,
                        match.start(1) + 1,
                        "Use %s:." % key.lower(),
                    )
                )
    if text and not text.endswith(("\n", "\r")):
        issues.append(
            _policy_diag(
                "warning",
                "F107",
                "File does not end with a newline.",
                source,
                len(text.splitlines()) or 1,
                1,
                "Add one LF at end of file.",
            )
        )
    directives, duplicates = file_directives(text)
    for key, line_no in duplicates:
        issues.append(
            _policy_diag(
                "error",
                "F108",
                "Duplicate metadata directive: %s" % key,
                source,
                line_no,
                1,
                "Keep one authoritative directive.",
            )
        )
    report = format_version_report(text)
    if report["state"] == "unversioned":
        issues.append(
            _policy_diag(
                "info",
                "F109",
                report["message"],
                source,
                1,
                1,
                "Add #! format_version: %s when opting into Format 1.0."
                % FORMAT_VERSION,
            )
        )
    elif report["state"] == "unsupported":
        issues.append(
            _policy_diag(
                "error",
                "F110",
                report["message"],
                source,
                1,
                1,
                "Use a supported migration tool before writing.",
            )
        )
    return issues


def stable_diagnostics(path):
    text, raw, bom = read_text_exact(path)
    items, diagnostics = parse_text(text)
    result = []
    for diagnostic in diagnostics:
        data = diagnostic.to_dict()
        data.setdefault("source", path)
        data["span"] = {
            "start": {"line": data.get("line"), "column": data.get("column")},
            "end": {
                "line": getattr(diagnostic, "end_line", None) or data.get("line"),
                "column": getattr(diagnostic, "end_column", None) or data.get("column"),
            },
        }
        data["hint"] = ""
        result.append(data)
    for diagnostic in canonical_issues(text, raw_bytes=raw, bom=bom, source=path):
        result.append(diagnostic)
    return OrderedDict(
        (
            ("ok", not any(row["severity"] == "error" for row in result)),
            ("item_count", len(items)),
            ("diagnostics", result),
        )
    )


def resolve_timezone_policy(config=None, text="", cli_timezone=None):
    config = config or {}
    directives, _duplicates = file_directives(text)
    defaults = (
        config.get("defaults") if isinstance(config.get("defaults"), dict) else {}
    )
    candidates = (
        ("cli", cli_timezone),
        ("file", directives.get("timezone")),
        ("config", defaults.get("timezone")),
        ("host", _host_timezone_name()),
    )
    for source, value in candidates:
        if value:
            name = str(value).strip()
            valid, error = validate_timezone(name)
            if source == "host" and (not valid or not _is_ascii_header_value(name)):
                continue
            return OrderedDict(
                (
                    ("timezone", name),
                    ("source", source),
                    ("valid", valid),
                    ("error", error),
                    ("precedence", ["cli", "file", "config", "host"]),
                )
            )
    return OrderedDict(
        (
            ("timezone", "local"),
            ("source", "host"),
            ("valid", True),
            ("error", ""),
            ("precedence", ["cli", "file", "config", "host"]),
        )
    )


def validate_timezone(name):
    if name.lower() in ("local", "host") or name.upper() == "UTC":
        return True, ""
    try:
        _timezone_for_name(name)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _is_ascii_header_value(value):
    try:
        text = str(value)
        text.encode("ascii")
    except UnicodeError:
        return False
    return not any(ord(char) < 32 or ord(char) == 127 for char in text)


def _timezone_for_name(name):
    """Resolve a timezone through the one source the project declares.

    `dateutil` and `pytz` fallbacks lived here until #76. They were never
    declared, so they only ever resolved anything when an unrelated package
    happened to have installed one -- which is how #73 stayed hidden. Every
    supported platform now reaches `zoneinfo`: Linux and macOS through the
    system database, Windows through the declared `tzdata` dependency.
    """
    try:
        from zoneinfo import ZoneInfo
    except Exception as exc:
        raise ValueError(_no_database_message(exc))

    try:
        return ZoneInfo(name)
    except Exception as exc:
        # "Not found" means two very different things: an unknown zone name, or
        # no database to look in at all. Telling a user with a typo to install
        # tzdata sends them the wrong way, so probe a zone that must exist.
        try:
            ZoneInfo("UTC")
        except Exception:
            raise ValueError(_no_database_message(exc))
        raise ValueError("Unknown timezone %r: %s" % (name, exc))


def _no_database_message(exc):
    return (
        "No timezone database is available (%s). Install the `tzdata` package, "
        "or reinstall lifetxt so its platform dependencies are applied." % exc
    )


def serve_target_diagnostic(read_paths, write_path):
    reads = [
        os.path.abspath(path) for path in (read_paths or []) if path and path != "-"
    ]
    write_abs = os.path.abspath(write_path) if write_path else ""
    mismatch = bool(write_abs and reads and write_abs not in reads)
    windows_drive_relative = bool(re.match(r"^[A-Za-z]:[^\\/]", str(write_path or "")))
    severity = "warning" if mismatch or windows_drive_relative else "ok"
    messages = []
    if mismatch:
        messages.append(
            "The server reads %s but writes %s." % (", ".join(reads), write_abs)
        )
    if windows_drive_relative:
        messages.append(
            "The write target is Windows drive-relative; use an absolute path such as C:\\path\\life.txt."
        )
    return OrderedDict(
        (
            ("severity", severity),
            ("read_paths", reads),
            ("write_path", write_abs),
            ("mismatch", mismatch),
            ("windows_drive_relative", windows_drive_relative),
            ("messages", messages),
        )
    )


def inspect_locks(paths, stale_after=300.0, now=None):
    now = float(now if now is not None else datetime.datetime.now().timestamp())
    records = []
    seen = set()
    for path in paths or []:
        lock_path = (
            path if str(path).endswith(".lifetxt.lock") else str(path) + ".lifetxt.lock"
        )
        if lock_path in seen or not os.path.exists(lock_path):
            continue
        seen.add(lock_path)
        try:
            with open(lock_path, "r", encoding="utf-8") as handle:
                owner = json.load(handle)
        except Exception:
            owner = {}
        age = max(0.0, now - os.path.getmtime(lock_path))
        pid_alive = (
            _pid_alive(owner.get("pid"))
            if owner.get("host") == socket.gethostname()
            else None
        )
        stale = age >= float(stale_after) and pid_alive is not True
        records.append(
            OrderedDict(
                (
                    ("path", lock_path),
                    ("target", lock_path[: -len(".lifetxt.lock")]),
                    ("age_seconds", round(age, 3)),
                    ("stale", stale),
                    ("pid_alive", pid_alive),
                    ("owner", owner),
                )
            )
        )
    return records


def audit_python_writes(root):
    """Return authoritative write calls outside the documented commit boundary."""
    allowed = {"atomic.py", "mutation.py"}
    findings = []
    package = os.path.join(root, "lifetxt")
    if not os.path.isdir(package):
        return findings
    for name in sorted(os.listdir(package)):
        if not name.endswith(".py") or name in allowed:
            continue
        path = os.path.join(package, name)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=path)
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            label = _call_label(node.func)
            if label in ("os.replace", "atomic_write_bytes"):
                findings.append({"path": path, "line": node.lineno, "call": label})
            if label == "open" and len(node.args) >= 2:
                mode = _ast_string_value(node.args[1])
                if mode is None:
                    continue
                if any(flag in mode for flag in ("w", "a", "x")):
                    findings.append(
                        {"path": path, "line": node.lineno, "call": "open(%s)" % mode}
                    )
    return findings


def _module_available(name):
    try:
        return importlib.util.find_spec(str(name)) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _package_version():
    package = sys.modules.get("lifetxt")
    return str(getattr(package, "__version__", None) or "unknown")


def _configured_section(config, name):
    if not isinstance(config, dict):
        return {}
    section = config.get(name)
    return section if isinstance(section, dict) else {}


def _env_value(config_section, key, default):
    name = config_section.get(key) or default
    return bool(os.environ.get(str(name)))


def optional_feature_state(config=None):
    """Return install/configuration state without exposing local secrets."""
    config = config or {}
    web_modules = OrderedDict(
        (name, _module_available(name)) for name in ("fastapi", "uvicorn")
    )
    tui_modules = OrderedDict(
        (name, _module_available(name)) for name in ("textual", "watchdog")
    )
    email = _configured_section(_configured_section(config, "notifications"), "email")
    git = _configured_section(config, "git")
    api = _configured_section(config, "api")
    return OrderedDict(
        (
            (
                "web",
                OrderedDict(
                    (
                        ("installed", all(web_modules.values())),
                        (
                            "configured",
                            bool(
                                _configured_section(config, "web") or api.get("token")
                            ),
                        ),
                        ("modules", web_modules),
                    )
                ),
            ),
            (
                "tui",
                OrderedDict(
                    (
                        ("installed", all(tui_modules.values())),
                        ("configured", True),
                        ("modules", tui_modules),
                    )
                ),
            ),
            (
                "mcp",
                OrderedDict(
                    (
                        ("installed", True),
                        ("configured", True),
                        ("modules", OrderedDict()),
                    )
                ),
            ),
            (
                "git",
                OrderedDict(
                    (
                        ("installed", shutil.which("git") is not None),
                        ("configured", bool(git.get("enable_api") or git.get("repo"))),
                        ("modules", OrderedDict()),
                    )
                ),
            ),
            (
                "smtp",
                OrderedDict(
                    (
                        ("installed", True),
                        (
                            "configured",
                            _env_value(email, "smtp_host_env", "LIFETXT_SMTP_HOST")
                            and _env_value(email, "smtp_user_env", "LIFETXT_SMTP_USER")
                            and _env_value(email, "smtp_pass_env", "LIFETXT_SMTP_PASS"),
                        ),
                        ("modules", OrderedDict((("smtplib", True),))),
                    )
                ),
            ),
        )
    )


def capability_document(
    read_only=False, authentication="token", writable_targets=None, config=None
):
    return OrderedDict(
        (
            ("capability_version", CAPABILITY_VERSION),
            (
                "server",
                OrderedDict((("package", "lifetxt"), ("version", _package_version()))),
            ),
            ("format_versions", [FORMAT_VERSION]),
            ("canonical_versions", [CANON_VERSION]),
            ("schema_versions", [SCHEMA_VERSION]),
            ("authentication", authentication),
            ("read_only", bool(read_only)),
            ("writable_targets", list(writable_targets or [])),
            (
                "revision_preconditions",
                {
                    "supported": True,
                    "required_for_remote_writes": True,
                    "algorithm": "sha256",
                },
            ),
            (
                "operations",
                [
                    "query",
                    "create",
                    "update",
                    "delete",
                    "complete",
                    "timer",
                    "message",
                    "acknowledge",
                    "presence",
                    "agenda",
                    "review",
                    "links",
                    "attachments",
                ],
            ),
            (
                "optional_features",
                {"web": True, "mcp": True, "git": True, "smtp": True},
            ),
            ("optional_feature_state", optional_feature_state(config)),
        )
    )


def release_gate(root, paths=None):
    checks = []
    checks.append(_gate("mutation_cas", _cas_probe()))
    checks.append(_gate("timezone_roundtrip", _timezone_probe()))
    checks.append(
        _gate(
            "golden_corpus",
            os.path.exists(
                os.path.join(root, "tests", "golden", "roundtrip_cases.json")
            ),
        )
    )
    checks.append(
        _gate(
            "packaging_metadata",
            any(
                os.path.exists(os.path.join(root, name))
                for name in ("pyproject.toml", "setup.py", "setup.cfg")
            ),
        )
    )
    schema_dir = os.path.join(root, "dist", "schemas")
    checks.append(
        _gate(
            "published_schemas",
            os.path.isdir(schema_dir)
            and len([name for name in os.listdir(schema_dir) if name.endswith(".json")])
            >= 3,
        )
    )
    findings = audit_python_writes(root)
    checks.append(
        OrderedDict(
            (("name", "write_route_audit"), ("ok", not findings), ("detail", findings))
        )
    )
    for path in paths or []:
        try:
            report = stable_diagnostics(path)
            checks.append(
                OrderedDict(
                    (
                        ("name", "format:%s" % path),
                        ("ok", report["ok"]),
                        ("detail", report),
                    )
                )
            )
        except OSError as exc:
            checks.append(
                OrderedDict(
                    (("name", "format:%s" % path), ("ok", False), ("detail", str(exc)))
                )
            )
    return OrderedDict(
        (
            ("ok", all(check["ok"] for check in checks)),
            ("checks", checks),
            (
                "versions",
                {
                    "format": FORMAT_VERSION,
                    "canon": CANON_VERSION,
                    "schema": SCHEMA_VERSION,
                },
            ),
        )
    )


def write_schema_bundle(directory):
    if not os.path.isdir(directory):
        os.makedirs(directory)
    schemas = schema_bundle()
    for name, value in schemas.items():
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    return sorted(schemas)


def schema_bundle():
    base = "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/"
    item = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": base + "item-v1.schema.json",
        "title": "lifetxt item v1",
        "type": "object",
        "required": ["status", "type", "title", "details"],
        "properties": {
            "status": {"type": "string"},
            "type": {"type": "string"},
            "title": {"type": "string"},
            "details": {
                "type": "object",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": ["string", "number", "boolean"]},
                },
            },
        },
        "additionalProperties": True,
    }
    diagnostic = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": base + "diagnostic-v1.schema.json",
        "title": "lifetxt diagnostic v1",
        "type": "object",
        "required": [
            "severity",
            "code",
            "message",
            "source",
            "line",
            "column",
            "span",
            "hint",
        ],
        "properties": {
            "severity": {"enum": ["info", "warning", "error"]},
            "code": {"type": "string"},
            "message": {"type": "string"},
            "source": {"type": ["string", "null"]},
            "line": {"type": ["integer", "null"]},
            "column": {"type": ["integer", "null"]},
            "span": {"type": "object"},
            "hint": {"type": "string"},
        },
        "additionalProperties": False,
    }
    capability = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": base + "capability-v1.schema.json",
        "title": "lifetxt capability v1",
        "type": "object",
        "required": [
            "capability_version",
            "format_versions",
            "schema_versions",
            "operations",
            "revision_preconditions",
        ],
        "properties": {
            "capability_version": {"const": CAPABILITY_VERSION},
            "format_versions": {"type": "array", "items": {"type": "string"}},
            "schema_versions": {"type": "array", "items": {"type": "string"}},
            "operations": {"type": "array", "items": {"type": "string"}},
            "revision_preconditions": {"type": "object"},
        },
        "additionalProperties": True,
    }
    conflict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": base + "conflict-v1.schema.json",
        "title": "lifetxt conflict v1",
        "type": "object",
        "required": [
            "error",
            "expected_revision",
            "current_revision",
            "attempted_change",
        ],
        "properties": {
            "error": {"const": "CONFLICT"},
            "expected_revision": {"type": "string"},
            "current_revision": {"type": "string"},
            "current_item": {"type": ["object", "null"]},
            "attempted_change": {"type": "object"},
        },
        "additionalProperties": False,
    }
    return OrderedDict(
        (
            ("item-v1.schema.json", item),
            ("diagnostic-v1.schema.json", diagnostic),
            ("capability-v1.schema.json", capability),
            ("conflict-v1.schema.json", conflict),
        )
    )


def _policy_diag(severity, code, message, source, line, column, hint):
    return OrderedDict(
        (
            ("severity", severity),
            ("code", code),
            ("message", message),
            ("source", source),
            ("line", line),
            ("column", column),
            (
                "span",
                {
                    "start": {"line": line, "column": column},
                    "end": {"line": line, "column": column},
                },
            ),
            ("hint", hint),
        )
    )


def _call_label(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        prefix = _call_label(func.value)
        return (prefix + "." if prefix else "") + func.attr
    return ""


def _ast_string_value(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return str(node.value)
    return None


def _host_timezone_name():
    value = datetime.datetime.now().astimezone().tzinfo
    return getattr(value, "key", None) or str(value or "local")


def _pid_alive(pid):
    try:
        pid = int(pid)
        if pid <= 0:
            return False
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except (TypeError, ValueError, OverflowError, AttributeError):
        return False


def _gate(name, ok, detail=""):
    return OrderedDict((("name", name), ("ok", bool(ok)), ("detail", detail)))


def _cas_probe():
    directory = tempfile.mkdtemp(prefix="lifetxt-gate-")
    path = os.path.join(directory, "life.txt")
    try:
        first = write_text(path, "one\n", operation="release_gate.create", create=True)
        write_text(
            path,
            "two\n",
            expected_hash=first.after_hash,
            operation="release_gate.first",
        )
        try:
            write_text(
                path,
                "stale\n",
                expected_hash=first.after_hash,
                operation="release_gate.stale",
            )
        except MutationConflict:
            return True
        return False
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
        try:
            os.rmdir(directory)
        except OSError:
            pass


def _timezone_probe():
    value = parse_datetime("2026-07-22T12:34:56+09:00")
    return value is not None and format_datetime(value) == "2026-07-22T12:34:56+09:00"
