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
# #437: real supported-host runs at commit b57aa84 observed release-profile
# durations of ~5316s (Windows) and ~4959s (WSL); native Linux and macOS both
# exceeded the prior 7200s boundary without a compatibility failure -- the
# collector itself cut them off. 14400s (4h) gives roughly 2.7x headroom over
# the highest confirmed real duration and room for the not-yet-measured
# Linux/macOS completion time, while still bounding a genuinely hung process
# within one collector invocation. See
# docs/en/external-environment-verification.md for the full rationale.
DEFAULT_RELEASE_TIMEOUT_SECONDS = 14400
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


def _redaction_candidates(repo_root=None, env=None):
    """Raw values that must never survive redaction (#430).

    Shared by ``make_redactor`` (what gets replaced) and the
    persistence-time rescan in ``write_bundle`` (what must be *gone* before
    a bundle is written), so the two checks cannot silently drift apart.
    """
    env = os.environ if env is None else env
    home = _home_value(env)
    temp = tempfile.gettempdir()
    candidates = []
    for value in (str(repo_root) if repo_root else "", home, temp):
        if value and len(value) >= 3:
            candidates.append(value)
            candidates.extend(v for v in _expanded_path_variants(value) if v != value)
    candidates.extend(_username_values(env))
    return candidates


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
_MARKER_RUN_PATTERN = re.compile(r"(<repo>|<home>|<temp>)(?:[/\\]*\1)+")
_WINDOWS_USER_TEMP_PATTERN = re.compile(
    r"(?:/mnt/[A-Za-z]|[A-Za-z]:)?[\\/]Users[\\/]<redacted-user>[\\/]AppData[\\/]Local[\\/]Temp",
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


def _unredacted_candidate_count(text, candidates):
    """Count how many raw redaction candidates still appear in ``text``.

    ``text`` is expected to be JSON, where a path's backslashes are encoded
    as ``\\\\``, so each candidate is checked both as written and in its
    JSON-escaped form -- checking only the raw form would silently never
    match a leaked Windows path and defeat the whole safety net. Returns a
    count rather than the matched values themselves, so a caller can refuse
    to persist without the refusal error itself leaking the raw value it is
    refusing over.
    """
    lowered_text = text.lower()
    hits = 0
    for value in candidates:
        if not value:
            continue
        if value.lower() in lowered_text:
            hits += 1
            continue
        escaped = value.replace("\\", "\\\\").lower()
        if escaped != value.lower() and escaped in lowered_text:
            hits += 1
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
        stat_bin = shutil.which("stat")
        if not stat_bin:
            return None
        completed = subprocess.run(
            [stat_bin, "-f", "%T", str(root)],
            text=True,
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode == 0:
            return completed.stdout.strip() or None
        return None
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


def build_bundle(root, args):
    root = Path(root).resolve()
    redact = make_redactor(root)
    host_class = classify_platform()
    git_sha, git_record = _read_git_sha(root, redact, args.probe_timeout)
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
        cache_dir = root / ".cache" / "lifetxt-verify-python"
        bootstrap = verification_python_bootstrap.ensure_verification_python(cache_dir)
        checks.append({"scenario": "python-bootstrap", **bootstrap})
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
                result = run_command(command, root, redact, args.release_timeout)
                checks.append({"scenario": "release-profile", **result})

    tools = _tool_records(root, redact, args.probe_timeout)
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


def write_bundle(bundle, output_path, redaction_candidates=()):
    """Serialize and persist a bundle, refusing to write if anything raw survived.

    ``redaction_candidates`` should be the same repo/home/temp/username
    values ``make_redactor`` was built from (see ``_redaction_candidates``).
    This is a persistence-time defense-in-depth check (#430): even if a
    future redaction-rule change misses a case, the fully-serialized JSON is
    rescanned case-insensitively immediately before the write, and the write
    is refused -- loudly, but without repeating the raw value in the error --
    rather than silently persisting a partially-redacted bundle.
    """
    text = json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    leaked = _unredacted_candidate_count(text, redaction_candidates)
    if leaked:
        raise RuntimeError(
            "Refusing to write external-verification evidence: %d raw "
            "redaction candidate value(s) are still present in the "
            "serialized bundle. This bundle was not written." % leaked
        )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


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
        "--release-timeout 21600.",
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
    bundle = build_bundle(root, args)
    write_bundle(bundle, output, redaction_candidates=_redaction_candidates(root))
    code = bundle_exit_code(bundle)
    release_status = next(
        (item.get("status") for item in bundle["checks"] if item.get("scenario") == "release-profile"),
        "unknown",
    )
    print(f"evidence={output}")
    print(
        f"host={bundle['metadata']['host_class']} release_profile={release_status} "
        f"release_timeout={args.release_timeout} exit={code}"
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
