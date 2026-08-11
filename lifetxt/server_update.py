"""Guarded update flow for a systemd-managed production lifetxt install.

Security/High: this is the second lifetxt surface (after `lifetxt update`,
see `command_update` in `cli.py`) that mutates the git working tree a
running install lives in, and the only one that additionally stops/starts
system services and reads (to hash and back up, never to write) configured
production data files. See docs/deployment/ubuntu-server.md for the
operator-facing runbook this module implements.

Design, matching the safety rails `lifetxt update` already established
(reused directly via lazy imports from `lifetxt.cli`, not reimplemented):

- Dry-run by default; a real run requires ``yes=True``.
- Exactly one fetch per run. The target commit is resolved once, then the
  same resolved SHA is used for the actual `git merge --ff-only` -- no
  second, unreviewed fetch between "here is what would change" and
  "apply it".
- Only ever runs `git fetch` and `git merge --ff-only`. Never resets,
  rebases, or force-pushes.
- Never rolls production data backward automatically. A failure after the
  code update (git merge succeeded) but before validation completes (hash
  verification + integrity checks) leaves services stopped rather than
  restarting a codebase that has not been proven safe, and the report
  names the exact backup directory and pre-update commit for manual
  recovery. A failure before the code update restores whatever service
  state existed before the attempt.
- A high-impact update (touches parser/config/atomic-write/schema/remote/
  ICS/deployment code, deletes a tracked file, or a commit message
  mentions "breaking"/"security"/"migration") stops before any mutation
  and reports a paste-friendly review block instead of proceeding. Only
  ``approve`` matching the exact resolved target commit unblocks it -- no
  other flag bypasses a fired trigger. See ``classify_risk``,
  ``gather_diff_summary``, and ``format_review_block``.
"""

import hashlib
import json
import os
import shutil
import subprocess
from collections import OrderedDict
from datetime import datetime, timezone


class ServerUpdateError(Exception):
    """A server-update step failed.

    ``step`` names which of the documented steps failed, for callers that
    want to react differently to different failure points.  ``report`` is
    the partial report accumulated before the failure, if any -- callers
    that only catch the exception (rather than reading the return value)
    can still recover it.
    """

    def __init__(self, message, step, report=None):
        super().__init__(message)
        self.step = step
        self.report = report


#: Config keys and their defaults. `python` has no default: it is the one
#: required key for pip/uv installs, since every validation step ultimately
#: runs through a Python interpreter. conda-pip may instead identify the
#: interpreter by conda environment name/prefix.
DEFAULT_CONFIG = {
    "install_root": None,
    "python": None,
    "remote": "origin",
    "branch": None,
    "ref": None,
    "repo": None,
    "life_txt_path": None,
    "backup_paths": [],
    "backup_dir": None,
    "lock_path": None,
    "services": [],
    "service_manager": "systemctl",
    "service_command": ["systemctl"],
    "service_preflight_commands": [],
    "integrity_checks": ["check"],
    "health_url": None,
    "health_timeout": 10,
    "git_timeout": 10,
    "service_timeout": 30,
    "installer": "pip",
    "pip_install_args": ["-e", "."],
    "uv_executable": "uv",
    "uv_install_args": ["-e", "."],
    "conda_executable": "conda",
    "conda_env_name": None,
    "conda_env_prefix": None,
    "conda_install_args": ["-e", "."],
    "application_config": None,
    "workspace": None,
    "validation_commands": [],
}

#: Recognized values for the `integrity_checks` config list, mapped to the
#: `lifetxt` CLI arguments each one runs. A check entry may be the historical
#: string form or an object with name/path/application_config/workspace.
_INTEGRITY_CHECK_BUILDERS = {
    "check": lambda entry: ["check"] + ([entry["path"]] if entry.get("path") else []),
    "workspace_validate": lambda entry: (
        ["workspace", "validate", entry["workspace"]]
        if entry.get("workspace")
        else ["workspace", "validate", "--all"]
    ),
    "ids": lambda entry: ["ids"] + ([entry["path"]] if entry.get("path") else []),
    "ticket_validate_history": lambda entry: (
        ["ticket", "validate-history"] + ([entry["path"]] if entry.get("path") else [])
    ),
}

#: Risk-trigger path categories for the high-impact review gate. Fixed
#: Python constants, not read from --server-config: acceptance criteria for
#: #273 require that no flag other than the exact-SHA --approve can bypass
#: a trigger, and a config-editable trigger list would blur that line.
#: Prefixes are matched against paths as git reports them (POSIX-style,
#: relative to the repo root).
DEFAULT_RISK_TRIGGER_PATHS = {
    "parser/model/serializer": (
        "lifetxt/parser.py",
        "lifetxt/model.py",
        "lifetxt/serializer.py",
        "lifetxt/validator.py",
    ),
    "config/workspace resolution": (
        "lifetxt/config.py",
        "lifetxt/config_registry.py",
        "lifetxt/config_writer.py",
        "lifetxt/config_layers.py",
        "lifetxt/config_migration.py",
        "lifetxt/config_validation.py",
        "lifetxt/workspace.py",
        "lifetxt/workspace_diagnostics.py",
    ),
    "atomic write/mutation/transaction/archive-safety": (
        "lifetxt/atomic.py",
        "lifetxt/mutation.py",
        "lifetxt/transaction_journal.py",
        "lifetxt/transaction_policy.py",
        "lifetxt/transaction_admin.py",
        "lifetxt/archive_safety_v3.py",
        "lifetxt/archive_plan_v1.py",
        "lifetxt/multi_target.py",
        "lifetxt/delegated_mutation.py",
        "lifetxt/write_operations.py",
    ),
    "schema/migration": (
        "lifetxt/schema_extensions_",
        "lifetxt/schema_validation_v2.py",
        "lifetxt/release_schema_extension.py",
        "dist/schemas/",
    ),
    "remote/authentication/authorization": ("lifetxt/remote_",),
    "calendar/ICS sync": ("lifetxt/ics.py",),
    "deployment files": ("contrib/systemd/", "contrib/nginx/"),
}

#: Commit-message substrings (case-insensitive) that trigger review on
#: their own, regardless of which files changed.
DEFAULT_RISK_TRIGGER_KEYWORDS = ("breaking", "security", "migration")

#: Paths excluded from the changed_line_count signal because they are bulk
#: generated output (a schema regeneration can rewrite thousands of lines
#: with no proportional review burden) -- still individually flagged via
#: the "schema/migration" category above, just not allowed to dominate the
#: line-count number the operator sees.
_LINE_COUNT_EXCLUDED_PREFIXES = ("dist/schemas/",)


def load_config(path):
    """Load and validate a server-update JSON config file.

    This is a deliberately separate file from the application's own
    `.lifetxt.json` -- it describes the deployment (paths, services,
    backup policy), not workspace content, and has no bearing on what
    `lifetxt check`/`serve`/etc. read.
    """
    with open(path, "r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except ValueError as exc:
            raise ServerUpdateError(
                "Config %s is not valid JSON: %s" % (path, exc), step="load_config"
            )
    if not isinstance(data, dict):
        raise ServerUpdateError(
            "Config %s must contain a JSON object at the top level." % path,
            step="load_config",
        )
    config = dict(DEFAULT_CONFIG)
    config.update(data)
    if not config.get("python") and config.get("installer") != "conda-pip":
        raise ServerUpdateError(
            'Config %s is missing required key "python" (path to the '
            "target environment's python executable)." % path,
            step="load_config",
        )
    _normalize_integrity_checks(config, source_path=path)
    if config.get("service_manager") not in ("systemctl", "none"):
        raise ServerUpdateError(
            'Config %s: service_manager must be "systemctl" or "none", got %r.'
            % (path, config.get("service_manager")),
            step="load_config",
        )
    if config.get("installer") not in ("pip", "uv", "conda-pip"):
        raise ServerUpdateError(
            'Config %s: installer must be "pip", "uv", or "conda-pip", got %r.'
            % (path, config.get("installer")),
            step="load_config",
        )
    if config.get("conda_env_name") and config.get("conda_env_prefix"):
        raise ServerUpdateError(
            "Config %s: conda_env_name and conda_env_prefix are mutually exclusive."
            % path,
            step="load_config",
        )
    if config.get("installer") == "conda-pip" and not (
        config.get("conda_env_name") or config.get("conda_env_prefix")
    ):
        raise ServerUpdateError(
            "Config %s: installer conda-pip requires conda_env_name or "
            "conda_env_prefix." % path,
            step="load_config",
        )
    _validate_argv(config.get("service_command"), "service_command", path)
    _validate_argv_list(
        config.get("service_preflight_commands"),
        "service_preflight_commands",
        path,
    )
    _validate_argv_list(config.get("validation_commands"), "validation_commands", path)
    _validate_string_list(config.get("pip_install_args"), "pip_install_args", path)
    _validate_string_list(config.get("uv_install_args"), "uv_install_args", path)
    _validate_string_list(config.get("conda_install_args"), "conda_install_args", path)
    _validate_optional_string(config.get("uv_executable"), "uv_executable", path)
    _validate_optional_string(config.get("conda_executable"), "conda_executable", path)
    _validate_optional_string(config.get("conda_env_name"), "conda_env_name", path)
    _validate_optional_string(config.get("conda_env_prefix"), "conda_env_prefix", path)
    _validate_optional_string(
        config.get("application_config"), "application_config", path
    )
    _validate_optional_string(config.get("workspace"), "workspace", path)
    _validate_optional_string(config.get("life_txt_path"), "life_txt_path", path)
    return config


def _validate_optional_string(value, key, source_path):
    if value is not None and not isinstance(value, str):
        raise ServerUpdateError(
            "Config %s: %s must be a string." % (source_path, key),
            step="load_config",
        )


def _validate_string_list(value, key, source_path):
    if value is None:
        return
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ServerUpdateError(
            "Config %s: %s must be a JSON array of strings." % (source_path, key),
            step="load_config",
        )


def _validate_argv(value, key, source_path):
    _validate_string_list(value, key, source_path)
    if value is not None and not value:
        raise ServerUpdateError(
            "Config %s: %s must not be empty." % (source_path, key),
            step="load_config",
        )


def _validate_argv_list(value, key, source_path):
    if value is None:
        return
    if not isinstance(value, list):
        raise ServerUpdateError(
            "Config %s: %s must be a JSON array." % (source_path, key),
            step="load_config",
        )
    for index, entry in enumerate(value):
        if isinstance(entry, list):
            _validate_argv(entry, "%s[%d]" % (key, index), source_path)
            continue
        if isinstance(entry, dict):
            _validate_argv(entry.get("argv"), "%s[%d].argv" % (key, index), source_path)
            if "timeout" in entry and not isinstance(entry["timeout"], (int, float)):
                raise ServerUpdateError(
                    "Config %s: %s[%d].timeout must be a number."
                    % (source_path, key, index),
                    step="load_config",
                )
            if "cwd" in entry and not isinstance(entry["cwd"], str):
                raise ServerUpdateError(
                    "Config %s: %s[%d].cwd must be a string."
                    % (source_path, key, index),
                    step="load_config",
                )
            if "name" in entry and not isinstance(entry["name"], str):
                raise ServerUpdateError(
                    "Config %s: %s[%d].name must be a string."
                    % (source_path, key, index),
                    step="load_config",
                )
            continue
        raise ServerUpdateError(
            "Config %s: %s[%d] must be an argv array or object."
            % (source_path, key, index),
            step="load_config",
        )


def _normalize_integrity_checks(config, source_path="<config>"):
    checks = config.get("integrity_checks") or []
    if not isinstance(checks, list):
        raise ServerUpdateError(
            "Config %s: integrity_checks must be a JSON array." % source_path,
            step="load_config",
        )
    normalized = []
    unknown = []
    for index, raw in enumerate(checks):
        if isinstance(raw, str):
            name = raw
            entry = {
                "name": name,
                "path": config.get("life_txt_path"),
                "application_config": config.get("application_config"),
                "workspace": config.get("workspace"),
            }
        elif isinstance(raw, dict):
            name = raw.get("name")
            entry = {
                "name": name,
                "path": raw.get("path", config.get("life_txt_path")),
                "application_config": raw.get(
                    "application_config", config.get("application_config")
                ),
                "workspace": raw.get("workspace", config.get("workspace")),
            }
            if "id" in raw:
                entry["id"] = raw["id"]
        else:
            raise ServerUpdateError(
                "Config %s: integrity_checks[%d] must be a string or object."
                % (source_path, index),
                step="load_config",
            )
        if name not in _INTEGRITY_CHECK_BUILDERS:
            unknown.append(str(name))
            continue
        for key in ("path", "application_config", "workspace", "id"):
            if (
                key in entry
                and entry[key] is not None
                and not isinstance(entry[key], str)
            ):
                raise ServerUpdateError(
                    "Config %s: integrity_checks[%d].%s must be a string."
                    % (source_path, index, key),
                    step="load_config",
                )
        normalized.append(entry)
    if unknown:
        raise ServerUpdateError(
            "Config %s names unknown integrity_checks: %s. Known checks: %s."
            % (
                source_path,
                ", ".join(sorted(unknown)),
                ", ".join(sorted(_INTEGRITY_CHECK_BUILDERS)),
            ),
            step="load_config",
        )
    return normalized


def _run(cmd, step, cwd=None, timeout=30):
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        raise ServerUpdateError("Command not found: %s" % cmd[0], step=step)
    except subprocess.TimeoutExpired:
        raise ServerUpdateError(
            "Command timed out after %ss: %s" % (timeout, " ".join(cmd)), step=step
        )
    except OSError as exc:
        raise ServerUpdateError(
            "Failed to run %s: %s" % (" ".join(cmd), exc), step=step
        )


def _sha256_file(path):
    if not path or not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_paths(paths):
    """Hash each configured production file. A missing file hashes to None
    (not an error) so the pre/post comparison can still catch "a file that
    existed before the update no longer does", which is exactly the kind of
    defect the #183 incident that motivated this module was about."""
    return OrderedDict((path, _sha256_file(path)) for path in paths)


def _timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_backup(paths, backup_dir, timestamp):
    """Copy every existing configured path into a fresh timestamped directory.

    Returns the backup directory path, or None if no `backup_dir` is
    configured (a deliberately supported "I am relying on external backups"
    escape hatch -- but then hash verification still runs, so a silent data
    change is still caught even without this module's own backup).

    Refuses to reuse or follow a pre-existing path at the destination
    directory or any per-file destination, mirroring UpdateLock's
    O_CREAT|O_EXCL pattern: a fresh, second-granularity-timestamped backup
    directory should never already exist, so if one does (including as a
    symlink), something is wrong and this must not silently write through it.
    """
    if not backup_dir:
        return None
    destination = os.path.join(backup_dir, timestamp)
    if os.path.lexists(destination):
        raise ServerUpdateError(
            "Refusing to back up into %s: it already exists." % destination,
            step="backup",
        )
    os.makedirs(destination)
    for path in paths:
        if not path or not os.path.isfile(path):
            continue
        flat_name = os.path.normpath(path).replace(os.sep, "__").lstrip("_")
        dest_path = os.path.join(destination, flat_name)
        fd = os.open(dest_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as dest_handle, open(path, "rb") as src_handle:
            shutil.copyfileobj(src_handle, dest_handle)
        shutil.copystat(path, dest_path, follow_symlinks=False)
    return destination


def _service_command(config):
    return list(config.get("service_command") or ["systemctl"])


def _service_action(manager, service_command, action, unit, timeout):
    """Run one systemctl action. Returns (ok, message); never raises."""
    if manager == "none":
        return True, "service_manager=none (no-op)"
    result = _run(
        service_command + [action, unit], step="service_%s" % action, timeout=timeout
    )
    if result is None:
        return False, "no result"
    ok = result.returncode == 0
    message = (result.stderr or "").strip() or (result.stdout or "").strip() or "ok"
    return ok, message


def _service_is_active(manager, service_command, unit, timeout):
    """True only if systemctl reports this unit as currently active.

    Deliberately conservative: a unit that is already stopped, failed, or in
    any other non-"active" state is left alone entirely -- it is never
    stopped by this run and therefore never restarted by it either. Without
    this check, `systemctl stop` on an already-inactive unit still exits 0,
    so a unit an operator intentionally left disabled would silently get
    started by an update that is supposed to only restore prior state.
    """
    if manager == "none":
        return False
    result = _run(
        service_command + ["is-active", unit],
        step="service_is_active",
        timeout=timeout,
    )
    if result is None or result.returncode != 0:
        return False
    return (result.stdout or "").strip() == "active"


def _conda_run_prefix(config):
    cmd = [config.get("conda_executable") or "conda", "run"]
    if config.get("conda_env_prefix"):
        cmd.extend(["--prefix", config["conda_env_prefix"]])
    elif config.get("conda_env_name"):
        cmd.extend(["--name", config["conda_env_name"]])
    else:
        raise ServerUpdateError(
            "conda-pip requires conda_env_name or conda_env_prefix.",
            step="reinstall",
        )
    return cmd


def python_command_prefix(config):
    if config.get("installer") == "conda-pip":
        return _conda_run_prefix(config) + ["python"]
    return [config["python"]]


def install_command(config):
    installer = config.get("installer") or "pip"
    python = config.get("python")
    if installer == "pip":
        return [python, "-m", "pip", "install"] + list(
            config.get("pip_install_args") or ["-e", "."]
        )
    if installer == "uv":
        return [
            config.get("uv_executable") or "uv",
            "pip",
            "install",
            "--python",
            python,
        ] + list(config.get("uv_install_args") or ["-e", "."])
    if installer == "conda-pip":
        return (
            python_command_prefix(config)
            + ["-m", "pip", "install"]
            + list(config.get("conda_install_args") or ["-e", "."])
        )
    raise ServerUpdateError(
        "Unknown installer %r." % installer,
        step="reinstall",
    )


def reinstall_package(config, install_root, timeout):
    cmd = install_command(config)
    result = _run(cmd, step="reinstall", cwd=install_root, timeout=timeout)
    if result.returncode != 0:
        raise ServerUpdateError(
            "%s install failed: %s"
            % (
                config.get("installer") or "pip",
                (result.stderr or result.stdout or "").strip(),
            ),
            step="reinstall",
        )


def sanity_import_check(python_prefix, timeout):
    result = _run(
        python_prefix + ["-c", "import lifetxt"],
        step="sanity_import_check",
        timeout=timeout,
    )
    if result.returncode != 0:
        raise ServerUpdateError(
            "Sanity import check failed: %s"
            % ((result.stderr or result.stdout or "").strip()),
            step="sanity_import_check",
        )


def _lifetxt_command_prefix(python_prefix, application_config=None):
    cmd = list(python_prefix) + ["-m", "lifetxt"]
    if application_config:
        cmd.extend(["--config", application_config])
    return cmd


def _integrity_result_key(entry, index, used):
    key = entry.get("id") or entry["name"]
    if key not in used:
        used.add(key)
        return key
    key = "%s#%d" % (entry["name"], index + 1)
    used.add(key)
    return key


def run_integrity_checks(python_prefix, checks, timeout):
    results = OrderedDict()
    failed = []
    used_keys = set()
    for index, entry in enumerate(checks):
        name = entry["name"]
        builder = _INTEGRITY_CHECK_BUILDERS[name]
        cmd = _lifetxt_command_prefix(
            python_prefix, entry.get("application_config")
        ) + builder(entry)
        result = _run(cmd, step="integrity_checks", timeout=timeout)
        ok = result.returncode == 0
        output = (result.stdout or result.stderr or "").strip()
        key = _integrity_result_key(entry, index, used_keys)
        results[key] = OrderedDict(
            [
                ("ok", ok),
                ("name", name),
                ("command", cmd),
                ("path", entry.get("path")),
                ("application_config", entry.get("application_config")),
                ("workspace", entry.get("workspace")),
                ("output", output[-2000:]),
            ]
        )
        if not ok:
            failed.append(key)
    if failed:
        raise ServerUpdateError(
            "Integrity check(s) failed: %s" % ", ".join(failed),
            step="integrity_checks",
            report=OrderedDict([("integrity_checks", results)]),
        )
    return results


def _command_entry(entry, index):
    if isinstance(entry, list):
        return "validation_command_%d" % (index + 1), entry, None, None
    name = entry.get("name") or "validation_command_%d" % (index + 1)
    return name, list(entry["argv"]), entry.get("cwd"), entry.get("timeout")


def run_command_entries(entries, step, default_timeout):
    results = OrderedDict()
    failed = []
    for index, entry in enumerate(entries or []):
        name, argv, cwd, timeout = _command_entry(entry, index)
        result = _run(argv, step=step, cwd=cwd, timeout=timeout or default_timeout)
        ok = result.returncode == 0
        output = (result.stdout or result.stderr or "").strip()
        results[name] = OrderedDict(
            [("ok", ok), ("command", argv), ("cwd", cwd), ("output", output[-2000:])]
        )
        if not ok:
            failed.append(name)
    if failed:
        raise ServerUpdateError(
            "%s failed: %s" % (step.replace("_", " "), ", ".join(failed)),
            step=step,
            report=OrderedDict([(step, results)]),
        )
    return results


def check_health(url, timeout):
    if not url:
        return None
    from urllib.error import HTTPError, URLError
    from urllib.request import urlopen

    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return OrderedDict(
                [("ok", True), ("status_code", response.status), ("body", body[:500])]
            )
    except HTTPError as exc:
        return OrderedDict([("ok", False), ("error", "HTTP %s" % exc.code)])
    except URLError as exc:
        return OrderedDict([("ok", False), ("error", str(exc.reason))])
    except (OSError, ValueError) as exc:
        return OrderedDict([("ok", False), ("error", str(exc))])


class UpdateLock:
    """A single-update lock: refuses to run two `server-update`s at once.

    Uses O_CREAT|O_EXCL so acquisition is atomic even against a concurrent
    process, unlike a check-then-create race. Not configuring `lock_path`
    disables locking entirely -- an explicit opt-out, not a silent gap.
    """

    def __init__(self, path):
        self.path = path
        self._fd = None

    def acquire(self):
        if not self.path:
            return
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        try:
            self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise ServerUpdateError(
                "Another server-update appears to be in progress (lock file "
                "%s already exists). If you are certain no update is "
                "running, remove it manually before retrying." % self.path,
                step="acquire_lock",
            )
        os.write(self._fd, str(os.getpid()).encode("ascii"))

    def release(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        if self.path:
            try:
                os.remove(self.path)
            except OSError:
                pass


def _parse_numstat(text):
    """Parse `git diff --numstat` output into [{"path", "added", "removed"}].

    `added`/`removed` are `None` for a binary file (git prints "-" for
    both), which is how binary files are distinguished from text files
    below rather than a separate git call.
    """
    files = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added_text, removed_text, path = parts
        added = None if added_text == "-" else int(added_text)
        removed = None if removed_text == "-" else int(removed_text)
        files.append({"path": path, "added": added, "removed": removed})
    return files


def _parse_name_status(text):
    """Parse `git diff --name-status` output into {path: status_char}."""
    statuses = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        statuses[parts[-1]] = parts[0]
    return statuses


def gather_diff_summary(run_git, repo_root, current, target, timeout):
    """Gather the raw material `classify_risk()` needs, via three git calls.

    The only impure part of risk classification -- everything downstream
    (`classify_risk`) is a pure function over the dict this returns, so it
    can be unit-tested with fixture data instead of a real git repo.
    `--no-renames` on both diff calls avoids parsing git's `{old => new}`
    rename syntax entirely: a rename shows as a plain delete+add pair,
    which the existing per-file logic already handles correctly.
    """
    range_spec = "%s..%s" % (current, target)

    numstat = run_git(
        ["diff", "--no-renames", "--numstat", range_spec],
        cwd=repo_root,
        timeout=timeout,
    )
    if numstat.returncode != 0:
        raise ServerUpdateError(
            "git diff --numstat failed: %s"
            % ((numstat.stderr or numstat.stdout).strip()),
            step="risk_classification",
        )
    name_status = run_git(
        ["diff", "--no-renames", "--name-status", range_spec],
        cwd=repo_root,
        timeout=timeout,
    )
    if name_status.returncode != 0:
        raise ServerUpdateError(
            "git diff --name-status failed: %s"
            % ((name_status.stderr or name_status.stdout).strip()),
            step="risk_classification",
        )
    # \x1e (record separator) prefixes each commit's body so multi-line
    # messages -- which may themselves contain blank lines -- can be split
    # back apart reliably; plain blank-line splitting cannot do that.
    log = run_git(
        ["log", "--format=%x1e%B", range_spec], cwd=repo_root, timeout=timeout
    )
    if log.returncode != 0:
        raise ServerUpdateError(
            "git log failed: %s" % ((log.stderr or log.stdout).strip()),
            step="risk_classification",
        )

    statuses = _parse_name_status(name_status.stdout)
    files = [
        {
            "path": entry["path"],
            "added": entry["added"],
            "removed": entry["removed"],
            "deleted": statuses.get(entry["path"]) == "D",
        }
        for entry in _parse_numstat(numstat.stdout)
    ]
    commit_messages = [
        msg.rstrip("\n") for msg in log.stdout.split("\x1e") if msg.strip()
    ]
    return {"files": files, "commit_messages": commit_messages}


def classify_risk(
    diff_summary,
    trigger_paths=DEFAULT_RISK_TRIGGER_PATHS,
    trigger_keywords=DEFAULT_RISK_TRIGGER_KEYWORDS,
):
    """Pure function: diff_summary in, risk assessment out.

    `diff_summary` is the dict `gather_diff_summary()` returns (or an
    equivalent hand-built fixture in tests). An empty `reasons` list means
    no review is required.
    """
    files = diff_summary.get("files") or []
    commit_messages = diff_summary.get("commit_messages") or []

    changed_file_count = len(files)
    binary_file_count = sum(1 for entry in files if entry["added"] is None)
    changed_line_count = sum(
        (entry["added"] or 0) + (entry["removed"] or 0)
        for entry in files
        if entry["added"] is not None
        and not entry["path"].startswith(_LINE_COUNT_EXCLUDED_PREFIXES)
    )

    reasons = []
    for category, prefixes in trigger_paths.items():
        matched = sorted(
            entry["path"] for entry in files if entry["path"].startswith(prefixes)
        )
        if matched:
            reasons.append("touches %s: %s" % (category, ", ".join(matched)))

    deleted = sorted(entry["path"] for entry in files if entry["deleted"])
    if deleted:
        reasons.append("deletes tracked file(s): %s" % ", ".join(deleted))

    for keyword in trigger_keywords:
        if any(keyword.lower() in message.lower() for message in commit_messages):
            reasons.append("commit message contains %r" % keyword)

    return {
        "changed_file_count": changed_file_count,
        "changed_line_count": changed_line_count,
        "binary_file_count": binary_file_count,
        "reasons": reasons,
    }


def format_review_block(report, server_config_path):
    """Render the paste-friendly LIFETXT_UPDATE_REVIEW block from `report`.

    `report` must already carry current_commit/target_commit/commit_count/
    changed_file_count/changed_line_count/binary_file_count/review_reasons/
    commits/changed_files, as `run_server_update` sets them before calling
    this. Pure formatting -- no git or filesystem access.
    """
    lines = [
        "===== LIFETXT_UPDATE_REVIEW_BEGIN =====",
        "status=REVIEW_REQUIRED",
        "current=%s" % report["current_commit"],
        "target=%s" % report["target_commit"],
        "commit_count=%s" % report["commit_count"],
        "changed_file_count=%s" % report["changed_file_count"],
        "changed_line_count=%s" % report["changed_line_count"],
        "binary_file_count=%s" % report["binary_file_count"],
        "--- reasons ---",
    ]
    lines.extend(report["review_reasons"] or ["(none)"])
    lines.append("--- commits ---")
    lines.extend(report["commits"] or ["(none)"])
    lines.append("--- changed files ---")
    lines.extend(report["changed_files"] or ["(none)"])
    lines.append("--- diff stat ---")
    lines.append(
        "%d file(s) changed, %d line(s) changed (%d binary file(s) excluded)"
        % (
            report["changed_file_count"],
            report["changed_line_count"],
            report["binary_file_count"],
        )
    )
    lines.append("--- execution plan ---")
    lines.append("installer=%s" % report.get("installer", "pip"))
    lines.append("install_command=%s" % " ".join(report.get("install_command") or []))
    if report.get("service_manager") == "none":
        lines.append("service_manager=none")
    else:
        lines.append(
            "service_command=%s" % " ".join(report.get("service_command") or [])
        )
    lines.append(
        "approved_command=lifetxt server-update --server-config %s --approve %s"
        % (server_config_path or "<server-config-path>", report["target_commit"])
    )
    lines.append("===== LIFETXT_UPDATE_REVIEW_END =====")
    return "\n".join(lines)


def _git_helpers():
    # Deferred import: `cli.py` wires this module's orchestrator into its
    # own argparse subcommand, so importing `cli` at module load time here
    # would be circular. By the time any function in this module actually
    # runs, `cli.py` has already finished importing.
    from .cli import (
        _git_commit_summary,
        _github_latest_release_or_tag,
        _lifetxt_install_root,
        _reject_option_like_git_arg,
        _run_git_for_update,
    )

    return (
        _lifetxt_install_root,
        _run_git_for_update,
        _reject_option_like_git_arg,
        _git_commit_summary,
        _github_latest_release_or_tag,
    )


def run_server_update(config, yes=False, approve=None, server_config_path=None):
    """Run the guarded update flow. Returns a report dict; raises
    ``ServerUpdateError`` on any failure (with a partial report attached).

    ``approve``, when given, must equal the freshly-resolved target commit
    exactly (see the review-gate block below) -- it is how an operator
    confirms they reviewed the specific commit this run is about to apply,
    not a general "skip review" switch.
    """
    (
        lifetxt_install_root,
        run_git,
        reject_option_like_git_arg,
        git_commit_summary,
        github_latest_release_or_tag,
    ) = _git_helpers()

    git_timeout = config.get("git_timeout", 10)
    service_timeout = config.get("service_timeout", 30)
    health_timeout = config.get("health_timeout", 10)
    manager = config.get("service_manager", "systemctl")
    service_command = _service_command(config)
    services = list(config.get("services") or [])
    backup_paths = list(config.get("backup_paths") or [])
    integrity_checks = _normalize_integrity_checks(config)
    validation_commands = list(config.get("validation_commands") or [])
    python_prefix = python_command_prefix(config)

    install_root = config.get("install_root") or lifetxt_install_root()

    # -- preflight: same checks `lifetxt update` already makes --
    toplevel = run_git(
        ["rev-parse", "--show-toplevel"], cwd=install_root, timeout=git_timeout
    )
    if toplevel.returncode != 0:
        raise ServerUpdateError(
            "server-update requires a git-based install. %s does not "
            "appear to be inside a git working tree." % install_root,
            step="preflight",
        )
    repo_root = toplevel.stdout.strip()

    status = run_git(["status", "--porcelain"], cwd=repo_root, timeout=git_timeout)
    if status.returncode != 0:
        raise ServerUpdateError(
            "git status failed: %s" % ((status.stderr or status.stdout).strip()),
            step="preflight",
        )
    if status.stdout.strip():
        raise ServerUpdateError(
            "Refusing to update: %s has uncommitted changes. Commit, "
            "stash, or discard them first." % repo_root,
            step="preflight",
        )

    branch_result = run_git(
        ["symbolic-ref", "-q", "--short", "HEAD"], cwd=repo_root, timeout=git_timeout
    )
    if branch_result.returncode != 0:
        raise ServerUpdateError(
            "Refusing to update: %s is not on a branch (detached HEAD). "
            "Check out a branch first." % repo_root,
            step="preflight",
        )
    branch_name = branch_result.stdout.strip()

    expected_branch = config.get("branch")
    if expected_branch and branch_name != expected_branch:
        raise ServerUpdateError(
            "Refusing to update: on branch %r, but the config requires "
            "%r." % (branch_name, expected_branch),
            step="preflight",
        )

    remote = reject_option_like_git_arg(config.get("remote") or "origin", "remote")
    ref = config.get("ref")
    if not ref:
        repo = config.get("repo") or "Eruhitsuji/lifetxt"
        latest_text, _kind, _url = github_latest_release_or_tag(
            repo, timeout=git_timeout
        )
        if latest_text is None:
            raise ServerUpdateError(
                'No published releases or tags found for %s; set "ref" '
                "in the config to update to a specific branch or commit." % repo,
                step="preflight",
            )
        ref = latest_text
    reject_option_like_git_arg(ref, "ref")

    # -- the one and only fetch this run makes --
    fetch = run_git(["fetch", remote, ref], cwd=repo_root, timeout=git_timeout)
    if fetch.returncode != 0:
        raise ServerUpdateError(
            "git fetch %s %s failed: %s"
            % (remote, ref, (fetch.stderr or fetch.stdout).strip()),
            step="fetch",
        )

    current = run_git(
        ["rev-parse", "HEAD"], cwd=repo_root, timeout=git_timeout
    ).stdout.strip()
    target = run_git(
        ["rev-parse", "FETCH_HEAD"], cwd=repo_root, timeout=git_timeout
    ).stdout.strip()

    report = OrderedDict(
        [
            ("install_root", repo_root),
            ("branch", branch_name),
            ("remote", remote),
            ("ref", ref),
            ("current_commit", current),
            ("target_commit", target),
            ("installer", config.get("installer") or "pip"),
            ("install_command", install_command(config)),
            ("python_command", python_prefix),
            ("service_manager", manager),
            ("service_command", service_command if manager != "none" else []),
        ]
    )

    already_merged = current == target
    if not already_merged:
        ancestor_check = run_git(
            ["merge-base", "--is-ancestor", target, current],
            cwd=repo_root,
            timeout=git_timeout,
        )
        already_merged = ancestor_check.returncode == 0

    if already_merged:
        report["status"] = "up_to_date"
        report["message"] = "Already up to date on %s (%s)." % (
            branch_name,
            current[:12],
        )
        return report

    commits, commit_count = git_commit_summary(repo_root, current, target, git_timeout)
    report["commits"] = commits
    report["commit_count"] = commit_count

    diff_summary = gather_diff_summary(run_git, repo_root, current, target, git_timeout)
    risk = classify_risk(diff_summary)
    report["changed_file_count"] = risk["changed_file_count"]
    report["changed_line_count"] = risk["changed_line_count"]
    report["binary_file_count"] = risk["binary_file_count"]
    report["review_reasons"] = risk["reasons"]
    report["changed_files"] = [entry["path"] for entry in diff_summary["files"]]

    if not yes:
        report["status"] = "update_available_dry_run"
        report["message"] = (
            "Update available on %s: %s -> %s (fetched %s from %s). Dry "
            "run: no changes made. Re-run with --yes to apply."
            % (branch_name, current[:12], target[:12], ref, remote)
        )
        report["would_backup_paths"] = backup_paths
        report["would_stop_services"] = services
        report["would_run_service_preflight_commands"] = list(
            config.get("service_preflight_commands") or []
        )
        report["would_run_integrity_checks"] = integrity_checks
        report["would_run_validation_commands"] = validation_commands
        return report

    # -- review gate: a risky update must be explicitly approved by exact
    # target commit before any mutation is even considered --
    if approve and approve != target:
        raise ServerUpdateError(
            "Refusing: --approve %s does not match the resolved target %s. "
            "The target moved since this commit was reviewed; re-run "
            "without --approve to generate a fresh review." % (approve, target),
            step="approve_mismatch",
        )
    if risk["reasons"] and not approve:
        report["status"] = "review_required"
        report["review_block"] = format_review_block(report, server_config_path)
        report["message"] = (
            "High-impact update detected (%d reason(s)); review required "
            "before applying. See review_block." % len(risk["reasons"])
        )
        return report

    if manager != "none" and config.get("service_preflight_commands"):
        try:
            report["service_preflight"] = run_command_entries(
                config.get("service_preflight_commands"),
                "service_preflight",
                service_timeout,
            )
        except ServerUpdateError as exc:
            if exc.report:
                report.update(exc.report)
            report["status"] = "failed_before_code_update"
            report["message"] = str(exc)
            raise ServerUpdateError(str(exc), step=exc.step, report=report)

    # -- mutating path: everything from here on can change service/data state --
    lock = UpdateLock(config.get("lock_path"))
    lock.acquire()
    stopped_services = []
    code_update_applied = False
    try:
        timestamp = _timestamp()
        backup_dir = create_backup(backup_paths, config.get("backup_dir"), timestamp)
        report["backup_dir"] = backup_dir
        pre_hashes = hash_paths(backup_paths)
        report["pre_update_hashes"] = pre_hashes

        active_services = [
            unit
            for unit in services
            if _service_is_active(manager, service_command, unit, service_timeout)
        ]
        report["services_active_before_update"] = active_services
        for unit in active_services:
            ok, message = _service_action(
                manager, service_command, "stop", unit, service_timeout
            )
            if not ok:
                raise ServerUpdateError(
                    "Failed to stop %s: %s" % (unit, message), step="stop_services"
                )
            stopped_services.append(unit)
        report["services_stopped"] = stopped_services

        merge = run_git(
            ["merge", "--ff-only", "FETCH_HEAD"], cwd=repo_root, timeout=git_timeout
        )
        if merge.returncode != 0:
            raise ServerUpdateError(
                "git merge --ff-only failed (not a fast-forward): %s"
                % ((merge.stderr or merge.stdout).strip()),
                step="merge",
            )
        code_update_applied = True

        reinstall_package(config, repo_root, service_timeout)
        sanity_import_check(python_prefix, service_timeout)

        post_hashes = hash_paths(backup_paths)
        report["post_update_hashes"] = post_hashes
        changed = [p for p in pre_hashes if pre_hashes.get(p) != post_hashes.get(p)]
        if changed:
            raise ServerUpdateError(
                "Production data changed during the code update, which "
                "should never happen for a code-only git update: %s"
                % ", ".join(changed),
                step="hash_verification",
            )

        report["integrity_checks"] = run_integrity_checks(
            python_prefix,
            integrity_checks,
            service_timeout,
        )
        report["validation_commands"] = run_command_entries(
            validation_commands,
            "validation_commands",
            service_timeout,
        )
    except ServerUpdateError as exc:
        if exc.report:
            report.update(exc.report)
        if code_update_applied:
            report["status"] = "failed_after_code_update"
            report["message"] = (
                "%s Services were left stopped rather than restarted with "
                "unvalidated code. Backup: %s. Pre-update commit: %s."
                % (exc, report.get("backup_dir"), current)
            )
        else:
            for unit in reversed(stopped_services):
                _service_action(
                    manager, service_command, "start", unit, service_timeout
                )
            report["status"] = "failed_before_code_update"
            report["message"] = str(exc)
        lock.release()
        raise ServerUpdateError(str(exc), step=exc.step, report=report)

    # -- validated: restart services and do the final health check --
    started = []
    restart_failures = OrderedDict()
    for unit in stopped_services:
        ok, message = _service_action(
            manager, service_command, "start", unit, service_timeout
        )
        if ok:
            started.append(unit)
        else:
            restart_failures[unit] = message
    report["services_restarted"] = started
    lock.release()

    if restart_failures:
        report["service_restart_failures"] = restart_failures
        report["status"] = "validated_restart_incomplete"
        report["message"] = (
            "Update applied and validated, but %d service(s) failed to "
            "restart: %s. Check them manually."
            % (len(restart_failures), ", ".join(restart_failures))
        )
        return report

    health = check_health(config.get("health_url"), health_timeout)
    report["health_check"] = health
    if health is not None and not health.get("ok"):
        report["status"] = "validated_health_check_failed"
        report["message"] = (
            "Update applied and validated, services restarted, but the "
            "health check failed: %s" % health.get("error")
        )
        return report

    report["status"] = "updated"
    report["message"] = "Updated %s: %s -> %s." % (
        branch_name,
        current[:12],
        target[:12],
    )
    return report
