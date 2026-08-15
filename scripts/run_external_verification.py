#!/usr/bin/env python
"""Collect one sanitized external-verification evidence bundle.

The runner intentionally automates only mechanically verifiable host checks.
Interactive/external scenarios are retained as manual_required/blocked records
instead of being inferred as passed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import locale
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Required so `import verification_python_bootstrap` resolves both when this
# script is run directly (its own directory is already on sys.path in that
# case) and when tests load it via importlib.util.spec_from_file_location,
# which does not add the script's directory automatically.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verification_python_bootstrap  # noqa: E402

SCHEMA_VERSION = 1
SUPPORTED_HOSTS = {"windows", "wsl", "linux", "macos"}
# #437 (reopened): the prior 14400s (4h) default, itself raised from 7200s
# after real-host runs at commit b57aa84, was still not enough headroom.
# Real supported-host runs at commit 2d99fc2 observed WSL completing in
# ~7427s (up from ~4959s on an earlier run of the same host class -- real
# host performance genuinely varies run to run), macOS completing in
# ~14225s (barely inside the old 14400s boundary), and native Linux again
# hitting the collector's timeout at 14400s while still inside the test
# run itself, with its true completion time unknown. 28800s (8h) gives
# roughly 2x headroom over the highest confirmed near-miss (macOS's
# ~14225s) and substantial room for native Linux and further host-to-host
# variance, while still bounding a genuinely hung process within one
# collector invocation. See docs/en/external-environment-verification.md
# for the full rationale.
DEFAULT_RELEASE_TIMEOUT_SECONDS = 28800
SECRET_KEY_MARKERS = ("TOKEN", "PASSWORD", "PASSWD", "SECRET", "API_KEY", "APIKEY", "AUTH")
MANUAL_SCENARIOS = (
    {
        "scenario": "interactive-terminal-tui",
        "issues": [312, 313],
        "status": "manual_required",
        "reason": "A scripted subprocess is not a substitute for real interactive terminal evidence.",
    },
    {
        "scenario": "selector-actions",
        "issues": [314],
        "status": "manual_required",
        "reason": "fzf/peco action semantics require a real shell and interactive selection flow.",
    },
    {
        "scenario": "real-browser-engine",
        "issues": [317, 318],
        "status": "manual_required",
        "reason": "Browser networking, focus, accessibility, reload, and restart behavior require a real browser engine.",
    },
    {
        "scenario": "web-revision-cutover",
        "issues": [288, 289, 290, 291, 292],
        "status": "manual_required",
        "reason": "Observe-window, required-mode cutover, rollback, and operator approval require a supported deployment.",
    },
    {
        "scenario": "remote-attachment",
        "issues": [297, 298, 299],
        "status": "manual_required",
        "reason": "Real supported remote client/server and authorization boundaries are external infrastructure.",
    },
    {
        "scenario": "external-filesystems",
        "issues": [304],
        "status": "manual_required",
        "reason": "Cloud-sync, removable, network-share, and physical interruption evidence cannot be synthesized locally.",
    },
    {
        "scenario": "smtp-provider",
        "issues": [315, 316],
        "status": "manual_required",
        "reason": "Safe provider accounts and real STARTTLS/authentication behavior are external infrastructure.",
    },
)


def classify_platform(system=None, release=None, env=None):
    system = (system or platform.system()).strip().lower()
    release = (release or platform.release()).strip().lower()
    env = os.environ if env is None else env
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    if system == "linux":
        if env.get("WSL_INTEROP") or env.get("WSL_DISTRO_NAME") or "microsoft" in release:
            return "wsl"
        return "linux"
    return "other"


def _secret_values(env):
    values = []
    for key, value in env.items():
        upper = key.upper()
        if value and len(value) >= 4 and any(marker in upper for marker in SECRET_KEY_MARKERS):
            values.append(value)
    return sorted(set(values), key=len, reverse=True)


def _username_values(env):
    values = []
    for key in ("USER", "USERNAME", "LOGNAME"):
        value = env.get(key)
        if value and len(value) >= 2:
            values.append(value)
    return sorted(set(values), key=len, reverse=True)


def _home_value(env):
    return env.get("USERPROFILE") or env.get("HOME") or str(Path.home())


# macOS resolves several of its default temp/home roots through a
# "/private" symlink (e.g. "/tmp" -> "/private/tmp", and thus
# tempfile.gettempdir()'s "/var/folders/..." result -> "/private/var/
# folders/..."). A tool that reports the resolved form -- for example via
# realpath() -- produces a path this process's own unresolved
# os.environ/tempfile.gettempdir() value never textually matches (#438).
# Hardcoded rather than resolved via a live os.path.realpath() call so the
# mapping is deterministic and testable on any host, not only real macOS.
_MACOS_PRIVATE_ALIASES = ("/tmp", "/var", "/etc")


def _expanded_path_variants(value):
    """Slash-style and known symlink-aliased forms of one candidate path."""
    variants = {value, value.replace("\\", "/"), value.replace("/", "\\")}
    for alias in _MACOS_PRIVATE_ALIASES:
        if value == alias or value.startswith(alias + "/"):
            variants.add("/private" + value)
        elif value.startswith("/private" + alias) and (
            value == "/private" + alias or value[len("/private" + alias)] == "/"
        ):
            variants.add(value[len("/private") :])
    return variants


def _categorized_redaction_candidates(repo_root=None, env=None):
    """Raw ``(value, category)`` pairs that must never survive redaction
    (#430, #443). category is one of "repo", "home", "temp", "username" --
    used only for privacy-safe persistence-refusal diagnostics (#443),
    never to expose the value itself.
    """
    env = os.environ if env is None else env
    home = _home_value(env)
    temp = tempfile.gettempdir()
    candidates = []
    for value, category in (
        (str(repo_root) if repo_root else "", "repo"),
        (home, "home"),
        (temp, "temp"),
    ):
        if value and len(value) >= 3:
            candidates.append((value, category))
            candidates.extend(
                (v, category) for v in _expanded_path_variants(value) if v != value
            )
    candidates.extend((v, "username") for v in _username_values(env))
    return candidates


def _redaction_candidates(repo_root=None, env=None):
    """Flat raw values that must never survive redaction (#430).

    Shared by ``make_redactor`` (what gets replaced) and the
    persistence-time rescan in ``write_bundle`` (what must be *gone* before
    a bundle is written), so the two checks cannot silently drift apart.
    Derived from ``_categorized_redaction_candidates`` so both share one
    source of truth; kept as a flat list for existing callers/tests that
    don't need category information.
    """
    return [
        value for value, _category in _categorized_redaction_candidates(repo_root, env)
    ]


def _path_replacement_entries(repo_root, home, temp):
    """(path variant, marker) pairs, longest variant first.

    Sorting by length descending (rather than the previous fixed repo/home/
    temp order) means a longer, more specific path -- such as %TEMP% nested
    inside %USERPROFILE% on a normal Windows host -- is always matched and
    replaced before a shorter path that would otherwise consume its shared
    prefix and swallow its marker (#430).
    """
    entries = []
    seen = set()
    for value, marker in (
        (str(repo_root) if repo_root else "", "<repo>"),
        (home or "", "<home>"),
        (temp or "", "<temp>"),
    ):
        if not value or len(value) < 3:
            continue
        for variant in _expanded_path_variants(value):
            key = variant.lower()
            if key in seen:
                continue
            seen.add(key)
            entries.append((variant, marker))
    entries.sort(key=lambda pair: len(pair[0]), reverse=True)
    return entries


# #438: adjacent repeats of the *same* marker (e.g. from a raw temp value
# that recurs as a substring immediately next to itself, such as
# "/tmp/tmp/subdir") collapse to one. A redacted account name immediately
# followed by the well-known Windows temp-directory suffix collapses to
# <temp> even when the raw path didn't textually match this process's own
# home/tempfile.gettempdir() value -- for example a WSL "/mnt/c/Users/..."
# mount view of a Windows home directory that the collector's own HOME
# reports as a POSIX path, so only the generic username pattern (not the
# home/temp path pattern) catches the account name, leaving the surrounding
# structure unredacted.
#
# Separators use "[\\/]+" (one or more), not "[\\/]" (exactly one): a real
# Windows full-profile run showed the same structural-collapse gap for
# ResourceWarning messages, whose text is a Python repr() of a file object
# -- repr() escapes each backslash as two literal backslash characters, so
# the actual separator in that text is "\\\\", not "\\". The username
# lookaround in username_patterns still matches (it only checks the single
# adjacent character), so the account name is redacted either way, but the
# original exactly-one-separator pattern here missed the doubled form and
# left the surrounding "Users\\\\<redacted-user>\\\\AppData\\\\Local\\\\
# Temp" structure unredacted (reopened #438).
_MARKER_RUN_PATTERN = re.compile(r"(<repo>|<home>|<temp>)(?:[/\\]*\1)+")
_WINDOWS_USER_TEMP_PATTERN = re.compile(
    r"(?:/mnt/[A-Za-z]|[A-Za-z]:)?[\\/]+Users[\\/]+<redacted-user>[\\/]+AppData[\\/]+Local[\\/]+Temp",
    re.IGNORECASE,
)


def _canonicalize_markers(text):
    """Collapse repeated/structural redaction artifacts to one marker (#438).

    Applied as the final step of every ``redact()`` call so re-sanitizing
    already-redacted or nested/previously-sanitized subprocess output always
    converges to the same canonical placeholder instead of accumulating
    duplicates such as ``<temp><temp>...``.
    """
    text = _WINDOWS_USER_TEMP_PATTERN.sub("<temp>", text)
    text = _MARKER_RUN_PATTERN.sub(r"\1", text)
    return text


def make_redactor(repo_root=None, env=None):
    env = os.environ if env is None else env
    home = _home_value(env)
    temp = tempfile.gettempdir()
    path_entries = _path_replacement_entries(repo_root, home, temp)
    marker_by_lower_variant = {
        variant.lower(): marker for variant, marker in path_entries
    }
    path_pattern = None
    if path_entries:
        # A single case-insensitive alternation, longest branch first, so
        # Python's left-to-right "first alternative that matches" semantics
        # give the same longest-match-wins guarantee as the sort above, in
        # one pass rather than N sequential str.replace() calls (#430: the
        # old sequential design let a differently-cased path silently miss,
        # and let a shorter candidate consume a longer one's prefix).
        alternation = "|".join(re.escape(variant) for variant, _marker in path_entries)
        path_pattern = re.compile(alternation, re.IGNORECASE)

    secrets = _secret_values(env)
    usernames = _username_values(env)

    token_patterns = (
        re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([^\s]+)"),
        re.compile(r"(?i)\b(token|password|passwd|secret|api[_-]?key)\s*=\s*([^\s]+)"),
    )
    username_patterns = []
    for username in usernames:
        escaped = re.escape(username)
        username_patterns.extend(
            (
                re.compile(rf"(?i)(\b(?:user|username|login|owner)\s*[:=]\s*){escaped}\b"),
                re.compile(rf"(?i)(?<=[/\\]){escaped}(?=[/\\])"),
            )
        )

    def redact(value):
        if value is None:
            return None
        text = str(value)
        for secret in secrets:
            text = text.replace(secret, "<redacted-secret>")
        if path_pattern is not None:
            text = path_pattern.sub(
                lambda m: marker_by_lower_variant[m.group(0).lower()], text
            )
        for pattern in token_patterns:
            text = pattern.sub(lambda m: f"{m.group(1)}<redacted-secret>", text)
        for pattern in username_patterns:
            if pattern.groups:
                text = pattern.sub(lambda m: f"{m.group(1)}<redacted-user>", text)
            else:
                text = pattern.sub("<redacted-user>", text)
        return _canonicalize_markers(text)

    return redact


# #443: a real Windows full-profile run refused to persist evidence that
# make_redactor() had already fully and correctly sanitized. Root cause: the
# persistence-time scan below used an *unconditional* substring check for
# every candidate, including usernames as short as two characters
# (_username_values), while make_redactor()'s own username_patterns only
# ever redact a username in a *bounded* context (a labeled "user=" field, or
# a path segment between "/"/"\\"). Across a full release profile's
# stdout/stderr -- easily megabytes, the entire test suite's own output -- a
# short username coincidentally appears as a substring of ordinary words
# (e.g. "an" inside "handle", "plan", "scan"), which redact() correctly
# leaves untouched since it is not a real username occurrence, but the old
# unconditional scan still flagged and refused it: a false positive, not a
# true redaction miss. _username_leak_pattern mirrors username_patterns'
# exact two bounded contexts so the persistence-time scan and the redactor
# agree on what counts as a real leak.
def _username_leak_pattern(username):
    escaped = re.escape(username)
    return re.compile(
        rf"(?i)(?:\b(?:user|username|login|owner)\s*[:=]\s*{escaped}\b)"
        rf"|(?:(?<=[/\\]){escaped}(?=[/\\]))"
    )


def _unredacted_candidate_count(text, candidates):
    """Return a ``{category: count}`` mapping of raw redaction candidates
    still present in ``text``, so a caller can report which candidate
    categories remain without revealing the raw value (#443).

    ``text`` is expected to be JSON, where a path's backslashes are encoded
    as ``\\\\``, so each candidate is checked both as written and in its
    JSON-escaped form -- checking only the raw form would silently never
    match a leaked Windows path and defeat the whole safety net.

    Each item in ``candidates`` may be a bare string (checked with the
    original strict, unconditional substring match -- category "path") or a
    ``(value, category)`` pair. category "username" is matched only in the
    same bounded contexts ``redact()`` itself treats as a real occurrence
    (see ``_username_leak_pattern``); every other category keeps the
    original unconditional substring check, since repo/home/temp paths are
    long/specific enough that coincidental collision is not a realistic
    concern -- the defense-in-depth strictness #430 established for those
    categories is unchanged.
    """
    lowered_text = text.lower()
    hits = {}
    for item in candidates:
        if isinstance(item, tuple):
            value, category = item
        else:
            value, category = item, "path"
        if not value:
            continue
        if category == "username":
            if _username_leak_pattern(value).search(text):
                hits[category] = hits.get(category, 0) + 1
            continue
        if value.lower() in lowered_text:
            hits[category] = hits.get(category, 0) + 1
            continue
        escaped = value.replace("\\", "\\\\").lower()
        if escaped != value.lower() and escaped in lowered_text:
            hits[category] = hits.get(category, 0) + 1
    return hits


def _decode_timeout_output(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def run_command(command, cwd, redact, timeout):
    started = time.monotonic()
    record = {
        "command": [redact(part) for part in command],
        "status": "failed",
        "exit_code": None,
        "duration_seconds": None,
        "stdout": "",
        "stderr": "",
    }
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
        record["exit_code"] = completed.returncode
        record["status"] = "passed" if completed.returncode == 0 else "failed"
        record["stdout"] = redact(completed.stdout)
        record["stderr"] = redact(completed.stderr)
    except subprocess.TimeoutExpired as exc:
        # A distinct status from "failed": a timeout means the collector cut
        # the command off at a configured boundary, not that the command
        # itself reported a non-zero result. Never represented as passed.
        record["status"] = "timeout"
        record["timeout_seconds"] = timeout
        record["stdout"] = redact(_decode_timeout_output(exc.stdout))
        record["stderr"] = redact(_decode_timeout_output(exc.stderr))
        record["error"] = f"timeout after {timeout} seconds"
    except OSError as exc:
        record["status"] = "blocked"
        record["error"] = redact(f"{type(exc).__name__}: {exc}")
    finally:
        record["duration_seconds"] = round(time.monotonic() - started, 3)
    return record


def _read_git_sha(root, redact, timeout):
    record = run_command(["git", "rev-parse", "HEAD"], root, redact, timeout)
    sha = record["stdout"].strip() if record["status"] == "passed" else None
    if sha and not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        sha = None
    return sha, record


def _package_version(root):
    pyproject = Path(root) / "pyproject.toml"
    if pyproject.is_file():
        in_project = False
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_project = stripped == "[project]"
                continue
            if in_project:
                match = re.match(r"""version\s*=\s*["']([^"']+)["']""", stripped)
                if match:
                    return match.group(1)
    try:
        return importlib.metadata.version("lifetxt")
    except importlib.metadata.PackageNotFoundError:
        return None


def _filesystem_type(root, host_class):
    if host_class in {"linux", "wsl"}:
        return _linux_filesystem_type(root)
    if host_class == "macos":
        return _macos_filesystem_type(root)
    if host_class == "windows":
        return _windows_filesystem_type(root)
    return None


def _linux_filesystem_type(root):
    mounts = Path("/proc/mounts")
    if not mounts.is_file():
        return None
    resolved = os.path.realpath(root)
    best = None
    best_len = -1
    for line in mounts.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        mountpoint = parts[1].replace("\\040", " ")
        if resolved == mountpoint or resolved.startswith(mountpoint.rstrip("/") + "/"):
            if len(mountpoint) > best_len:
                best = parts[2]
                best_len = len(mountpoint)
    return best


# #439: matches a `mount` command output line such as
# "/dev/disk3s1s1 on / (apfs, sealed, local, read-only, journaled)" -- the
# well-documented, portable way to read the filesystem type on BSD/macOS,
# where "stat"'s "-f FORMAT" conversions describe *file* attributes, not
# filesystem attributes (unlike GNU coreutils' stat, whose "-f" flag has a
# different, filesystem-status meaning). Uses a greedy, anchored-at-the-end
# match so a mountpoint containing spaces or the literal substring " on "
# (e.g. an automount device name) is still captured correctly.
_MACOS_MOUNT_LINE_PATTERN = re.compile(
    r"\son\s(?P<mountpoint>.+)\s\((?P<opts>[^)]*)\)\s*$"
)


def _parse_macos_mount_type(mount_output, resolved_root):
    """Extract the filesystem type covering ``resolved_root`` from ``mount``
    output text, choosing the longest matching mountpoint so a nested mount
    (e.g. an external volume under a parent filesystem) wins over its
    shorter parent -- mirroring ``_linux_filesystem_type``'s algorithm.
    """
    best = None
    best_len = -1
    for line in mount_output.splitlines():
        match = _MACOS_MOUNT_LINE_PATTERN.search(line)
        if not match:
            continue
        mountpoint = match.group("mountpoint")
        if resolved_root == mountpoint or resolved_root.startswith(
            mountpoint.rstrip("/") + "/"
        ):
            if len(mountpoint) > best_len:
                opts = match.group("opts")
                fs_type = opts.split(",", 1)[0].strip() if opts else ""
                best = fs_type or None
                best_len = len(mountpoint)
    return best


def _macos_filesystem_type(root):
    mount_bin = shutil.which("mount")
    if not mount_bin:
        return None
    try:
        completed = subprocess.run(
            [mount_bin],
            text=True,
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    resolved = os.path.realpath(root)
    return _parse_macos_mount_type(completed.stdout, resolved)


def _windows_filesystem_type(root):
    if os.name != "nt":
        return None
    try:
        import ctypes

        resolved = os.path.abspath(root)
        drive, _ = os.path.splitdrive(resolved)
        volume_root = (drive + "\\") if drive else resolved
        fs_name = ctypes.create_unicode_buffer(256)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            volume_root,
            None,
            0,
            None,
            None,
            None,
            fs_name,
            len(fs_name),
        )
        return fs_name.value if ok else None
    except (AttributeError, OSError):
        return None


def _terminal_metadata(env=None):
    env = os.environ if env is None else env
    size = None
    try:
        dims = shutil.get_terminal_size(fallback=(0, 0))
        if dims.columns and dims.lines:
            size = {"columns": dims.columns, "lines": dims.lines}
    except OSError:
        pass
    return {
        "interactive": bool(sys.stdin.isatty() and sys.stdout.isatty()),
        "term": env.get("TERM"),
        "colorterm": env.get("COLORTERM"),
        "term_program": env.get("TERM_PROGRAM"),
        "windows_terminal": bool(env.get("WT_SESSION")),
        "wsl_distro": env.get("WSL_DISTRO_NAME"),
        "size": size,
    }


def _hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_records(paths, root, redact):
    records = []
    for raw in paths:
        path = Path(raw)
        if not path.is_absolute():
            path = Path(root) / path
        if not path.is_file():
            records.append(
                {
                    "path": redact(str(path)),
                    "status": "blocked",
                    "reason": "file not found",
                    "sha256": None,
                    "size_bytes": None,
                }
            )
            continue
        records.append(
            {
                "path": redact(str(path)),
                "status": "observed",
                "sha256": _hash_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return records


def _tool_records(root, redact, timeout):
    records = []
    for name in ("fzf", "peco"):
        executable = shutil.which(name)
        if not executable:
            records.append(
                {
                    "tool": name,
                    "status": "blocked",
                    "reason": f"{name} is not installed or not on PATH",
                }
            )
            continue
        result = run_command([executable, "--version"], root, redact, timeout)
        records.append({"tool": name, "status": result["status"], "probe": result})
    return records


def _manual_records(tool_records):
    records = [dict(item) for item in MANUAL_SCENARIOS]
    selector = next((item for item in records if item["scenario"] == "selector-actions"), None)
    if selector is not None:
        missing = [
            item["tool"]
            for item in tool_records
            if item["tool"] in {"fzf", "peco"} and item["status"] == "blocked"
        ]
        if missing:
            selector["status"] = "blocked"
            selector["reason"] += " Missing tool(s): " + ", ".join(missing) + "."
    return records


def default_output_path(root, host_class):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(root) / ".cache" / f"external-verification-{host_class}-{stamp}.json"


def _progress_artifact_paths(output_path):
    """Derive the shared progress-log/event-stream paths from the final
    JSON evidence path (#443), so the three artifacts from one run are
    deterministically associated by name, e.g.
    ".../external-verification-windows-<UTC>.json" ->
    ".../external-verification-windows-<UTC>.log" and
    ".../external-verification-windows-<UTC>.progress.jsonl".
    """
    output_path = Path(output_path)
    stem = output_path.name
    if stem.endswith(".json"):
        stem = stem[: -len(".json")]
    base = output_path.with_name(stem)
    return (
        base.with_name(base.name + ".log"),
        base.with_name(base.name + ".progress.jsonl"),
    )


class ProgressRecorder:
    """Incrementally writes sanitized human-readable (``.log``) and
    machine-readable (``.progress.jsonl``) lifecycle events for one
    external-verification run (#443).

    A multi-hour full-profile run has no durable progress record separate
    from the final JSON bundle today: a persistence-time refusal, a
    timeout, or a host interruption discards all diagnostic context. Every
    event payload is sanitized through the same ``redact()`` closure the
    final JSON bundle uses *before* it is ever written -- never write-then-
    sanitize. Each write is flushed and fsynced immediately so a process
    kill leaves the latest completed event durable on disk.
    """

    def __init__(self, log_path, jsonl_path, redact, run_id):
        self.log_path = Path(log_path)
        self.jsonl_path = Path(jsonl_path)
        self._redact = redact
        self._run_id = run_id
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _sanitize(self, value):
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, dict):
            return {str(key): self._sanitize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._sanitize(item) for item in value]
        return self._redact(str(value))

    def record(self, event, status, **fields):
        timestamp = (
            dt.datetime.now(dt.timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        safe_fields = {key: self._sanitize(value) for key, value in fields.items()}
        entry = {
            "run_id": self._run_id,
            "timestamp": timestamp,
            "event": event,
            "status": status,
            **safe_fields,
        }
        self._append_jsonl(entry)
        self._append_log(timestamp, event, status, safe_fields)

    def _append_jsonl(self, entry):
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        with open(self.jsonl_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _append_log(self, timestamp, event, status, safe_fields):
        extra = " ".join(
            f"{key}={value}" for key, value in safe_fields.items() if value is not None
        )
        line = f"{timestamp} {event} {status}"
        if extra:
            line += " " + extra
        with open(self.log_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())


class _NullProgressRecorder:
    """No-op stand-in so callers can invoke ``progress.record(...)``
    unconditionally without constructing a real ``ProgressRecorder``."""

    def record(self, *args, **kwargs):
        pass


_NULL_PROGRESS = _NullProgressRecorder()


def _locale_language():
    try:
        return locale.getlocale()[0]
    except ValueError:
        return None


def _redact_structure(value, redact):
    if isinstance(value, dict):
        return {key: _redact_structure(item, redact) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_structure(item, redact) for item in value]
    if isinstance(value, str):
        return redact(value)
    return value


def build_bundle(root, args, progress=None):
    if progress is None:
        progress = _NULL_PROGRESS
    root = Path(root).resolve()
    redact = make_redactor(root)
    host_class = classify_platform()
    progress.record("host_classification", "completed", host_class=host_class)
    progress.record("git_identity", "started")
    git_sha, git_record = _read_git_sha(root, redact, args.probe_timeout)
    progress.record(
        "git_identity",
        git_record.get("status", "unknown"),
        exit_code=git_record.get("exit_code"),
    )
    is_ci = bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))
    evidence_type = (
        "real_environment"
        if host_class in SUPPORTED_HOSTS and not is_ci
        else "simulated_or_subprocess"
    )
    metadata = {
        "host_class": host_class,
        "evidence_type": evidence_type,
        "evidence_scope": "host_execution_only",
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": redact(platform.version()),
            "machine": platform.machine(),
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": redact(sys.executable),
        },
        "package_version": _package_version(root),
        "git_sha": git_sha,
        "filesystem_type": _filesystem_type(root, host_class),
        "locale": {
            "preferred_encoding": locale.getpreferredencoding(False),
            "language": _locale_language(),
        },
        "terminal": _terminal_metadata(),
        "ci_detected": is_ci,
    }

    checks = [{"scenario": "git-identity", **git_record}]
    if args.skip_release:
        checks.append(
            {
                "scenario": "release-profile",
                "status": "skipped",
                "reason": "--skip-release was requested; this run is not release-profile evidence.",
            }
        )
    else:
        progress.record("python_bootstrap", "started")
        cache_dir = root / ".cache" / "lifetxt-verify-python"
        bootstrap = verification_python_bootstrap.ensure_verification_python(cache_dir)
        checks.append({"scenario": "python-bootstrap", **bootstrap})
        progress.record(
            "python_bootstrap",
            bootstrap.get("status", "unknown"),
            category=bootstrap.get("category"),
            version=bootstrap.get("version"),
        )
        if bootstrap["status"] != "passed":
            checks.append(
                {
                    "scenario": "release-profile",
                    "status": "blocked",
                    "reason": "No supported Python (3.10-3.12) available for the release "
                    "profile: " + bootstrap.get("reason", "bootstrap did not succeed."),
                }
            )
        else:
            try:
                venv_python = verification_python_bootstrap.create_verification_venv(
                    bootstrap["executable"], cache_dir
                )
            except (OSError, subprocess.SubprocessError) as exc:
                # A host can have a discoverable/provisioned interpreter
                # whose own `-m venv` still fails (e.g. a system missing
                # ensurepip support) -- record that as blocked rather than
                # crashing the whole collector before any evidence is
                # written.
                checks.append(
                    {
                        "scenario": "release-profile",
                        "status": "blocked",
                        "reason": redact(
                            "Failed to create the isolated verification environment: "
                            "%s: %s" % (type(exc).__name__, exc)
                        ),
                    }
                )
            else:
                command = [
                    sys.executable,
                    str(root / "scripts" / "run_ci_like.py"),
                    "--profile",
                    "release",
                    "--python",
                    venv_python,
                ]
                progress.record(
                    "release_profile", "started", timeout_seconds=args.release_timeout
                )
                result = run_command(command, root, redact, args.release_timeout)
                checks.append({"scenario": "release-profile", **result})
                progress.record(
                    "release_profile",
                    result.get("status", "unknown"),
                    exit_code=result.get("exit_code"),
                    duration_seconds=result.get("duration_seconds"),
                    timeout_seconds=result.get("timeout_seconds"),
                )

    tools = _tool_records(root, redact, args.probe_timeout)
    progress.record(
        "tool_probes",
        "completed",
        tools={item["tool"]: item["status"] for item in tools},
    )
    artifacts = _artifact_records(args.artifact, root, redact)
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "metadata": metadata,
        "checks": checks,
        "tools": tools,
        "artifacts": artifacts,
        "manual_or_external_scenarios": _manual_records(tools),
        "notes": [
            "This bundle aggregates observed host facts and automated subprocess checks.",
            "manual_required/blocked entries remain incomplete until their dedicated real-environment procedures are executed.",
            "A real_environment bundle does not by itself satisfy interactive terminal, browser, Remote, SMTP, filesystem, deployment, release, or rollback gates.",
        ],
    }
    return _redact_structure(bundle, redact)


def write_bundle(bundle, output_path, redaction_candidates=(), progress=None):
    """Serialize and persist a bundle, refusing to write if anything raw survived.

    ``redaction_candidates`` should be the same repo/home/temp/username
    values ``make_redactor`` was built from -- either the flat form from
    ``_redaction_candidates`` or the categorized ``(value, category)`` form
    from ``_categorized_redaction_candidates`` (#443). This is a
    persistence-time defense-in-depth check (#430): even if a future
    redaction-rule change misses a case, the fully-serialized JSON is
    rescanned immediately before the write, and the write is refused --
    loudly, but without repeating the raw value in the error -- rather than
    silently persisting a partially-redacted bundle.
    """
    if progress is None:
        progress = _NULL_PROGRESS
    progress.record("final_evidence_persistence", "started")
    text = json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    hits = _unredacted_candidate_count(text, redaction_candidates)
    if hits:
        total = sum(hits.values())
        categories = sorted(hits)
        progress.record(
            "final_evidence_persistence",
            "refused",
            candidate_categories=categories,
            total_hits=total,
        )
        raise RuntimeError(
            "Refusing to write external-verification evidence: %d raw "
            "redaction candidate value(s) are still present in the "
            "serialized bundle (candidate categories: %s). This bundle "
            "was not written." % (total, ", ".join(categories))
        )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    progress.record("final_evidence_persistence", "completed")


def bundle_exit_code(bundle):
    for check in bundle.get("checks", []):
        if check.get("scenario") == "release-profile" and check.get("status") in {
            "failed",
            "timeout",
        }:
            return 1
        if check.get("scenario") == "git-identity" and check.get("status") in {
            "failed",
            "blocked",
            "timeout",
        }:
            return 1
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run external host verification and write one sanitized JSON evidence bundle."
    )
    parser.add_argument(
        "--output",
        help="Evidence JSON path. Default: .cache/external-verification-<host>-<UTC>.json",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="Optional artifact/evidence file to hash. Repeat for multiple files.",
    )
    parser.add_argument(
        "--skip-release",
        action="store_true",
        help="Skip the expensive release profile. The bundle records this as skipped, never passed.",
    )
    parser.add_argument(
        "--release-timeout",
        type=int,
        default=DEFAULT_RELEASE_TIMEOUT_SECONDS,
        help="Timeout in seconds for scripts/run_ci_like.py --profile release "
        f"(default: {DEFAULT_RELEASE_TIMEOUT_SECONDS}). A run that exceeds this "
        'is recorded with status "timeout" and retained partial output, '
        "never as passed. Increase this for a slower real host, for example "
        "--release-timeout 43200.",
    )
    parser.add_argument(
        "--probe-timeout",
        type=int,
        default=30,
        help="Timeout in seconds for short metadata/tool probes (default: 30).",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    host_class = classify_platform()
    output = Path(args.output) if args.output else default_output_path(root, host_class)
    log_path, jsonl_path = _progress_artifact_paths(output)
    progress = ProgressRecorder(
        log_path, jsonl_path, make_redactor(root), run_id=output.stem
    )
    progress.record("collector_start", "started")
    bundle = build_bundle(root, args, progress=progress)
    try:
        write_bundle(
            bundle,
            output,
            redaction_candidates=_categorized_redaction_candidates(root),
            progress=progress,
        )
    except RuntimeError as exc:
        # Every progress event up to this point is already flushed and
        # fsynced (#443): a persistence refusal must not discard the whole
        # run's diagnostic context the way an uncaught traceback would.
        progress.record("collector_complete", "failed")
        print(f"progress_log={log_path}")
        print(f"progress_events={jsonl_path}")
        print(str(exc))
        return 1
    progress.record("collector_complete", "completed")
    code = bundle_exit_code(bundle)
    release_status = next(
        (item.get("status") for item in bundle["checks"] if item.get("scenario") == "release-profile"),
        "unknown",
    )
    print(f"evidence={output}")
    print(f"progress_log={log_path}")
    print(f"progress_events={jsonl_path}")
    print(
        f"host={bundle['metadata']['host_class']} release_profile={release_status} "
        f"release_timeout={args.release_timeout} exit={code}"
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
