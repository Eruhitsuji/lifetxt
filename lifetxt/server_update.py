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
#: required key, since every mutating step ultimately runs through it.
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
    "integrity_checks": ["check"],
    "health_url": None,
    "health_timeout": 10,
    "git_timeout": 10,
    "service_timeout": 30,
    "pip_install_args": ["-e", "."],
}

#: Recognized values for the `integrity_checks` config list, mapped to the
#: `lifetxt` CLI arguments each one runs. `life_txt_path` is threaded in at
#: call time; checks that do not need it (workspace validate reads the
#: active workspace instead) ignore the argument.
_INTEGRITY_CHECK_BUILDERS = {
    "check": lambda life_txt_path: (
        ["check"] + ([life_txt_path] if life_txt_path else [])
    ),
    "workspace_validate": lambda life_txt_path: ["workspace", "validate", "--all"],
    "ids": lambda life_txt_path: ["ids"] + ([life_txt_path] if life_txt_path else []),
    "ticket_validate_history": lambda life_txt_path: (
        ["ticket", "validate-history"] + ([life_txt_path] if life_txt_path else [])
    ),
}


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
    if not config.get("python"):
        raise ServerUpdateError(
            'Config %s is missing required key "python" (path to the '
            "target environment's python executable)." % path,
            step="load_config",
        )
    unknown_checks = sorted(
        set(config.get("integrity_checks") or []) - set(_INTEGRITY_CHECK_BUILDERS)
    )
    if unknown_checks:
        raise ServerUpdateError(
            "Config %s names unknown integrity_checks: %s. Known checks: %s."
            % (
                path,
                ", ".join(unknown_checks),
                ", ".join(sorted(_INTEGRITY_CHECK_BUILDERS)),
            ),
            step="load_config",
        )
    if config.get("service_manager") not in ("systemctl", "none"):
        raise ServerUpdateError(
            'Config %s: service_manager must be "systemctl" or "none", got %r.'
            % (path, config.get("service_manager")),
            step="load_config",
        )
    return config


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
    """
    if not backup_dir:
        return None
    destination = os.path.join(backup_dir, timestamp)
    os.makedirs(destination, exist_ok=True)
    for path in paths:
        if not path or not os.path.isfile(path):
            continue
        flat_name = os.path.normpath(path).replace(os.sep, "__").lstrip("_")
        shutil.copy2(path, os.path.join(destination, flat_name))
    return destination


def _service_action(manager, action, unit, timeout):
    """Run one systemctl action. Returns (ok, message); never raises."""
    if manager == "none":
        return True, "service_manager=none (no-op)"
    result = _run(
        ["systemctl", action, unit], step="service_%s" % action, timeout=timeout
    )
    if result is None:
        return False, "no result"
    ok = result.returncode == 0
    message = (result.stderr or "").strip() or (result.stdout or "").strip() or "ok"
    return ok, message


def reinstall_package(python, install_root, pip_install_args, timeout):
    cmd = [python, "-m", "pip", "install"] + list(pip_install_args)
    result = _run(cmd, step="reinstall", cwd=install_root, timeout=timeout)
    if result.returncode != 0:
        raise ServerUpdateError(
            "pip install failed: %s" % ((result.stderr or result.stdout or "").strip()),
            step="reinstall",
        )


def sanity_import_check(python, timeout):
    result = _run(
        [python, "-c", "import lifetxt"], step="sanity_import_check", timeout=timeout
    )
    if result.returncode != 0:
        raise ServerUpdateError(
            "Sanity import check failed: %s"
            % ((result.stderr or result.stdout or "").strip()),
            step="sanity_import_check",
        )


def run_integrity_checks(python, life_txt_path, checks, timeout):
    results = OrderedDict()
    failed = []
    for name in checks:
        builder = _INTEGRITY_CHECK_BUILDERS[name]
        cmd = [python, "-m", "lifetxt"] + builder(life_txt_path)
        result = _run(cmd, step="integrity_checks", timeout=timeout)
        ok = result.returncode == 0
        output = (result.stdout or result.stderr or "").strip()
        results[name] = OrderedDict([("ok", ok), ("output", output[-2000:])])
        if not ok:
            failed.append(name)
    if failed:
        raise ServerUpdateError(
            "Integrity check(s) failed: %s" % ", ".join(failed),
            step="integrity_checks",
            report=OrderedDict([("integrity_checks", results)]),
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


def run_server_update(config, yes=False):
    """Run the guarded update flow. Returns a report dict; raises
    ``ServerUpdateError`` on any failure (with a partial report attached).
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
    services = list(config.get("services") or [])
    backup_paths = list(config.get("backup_paths") or [])

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

    if not yes:
        report["status"] = "update_available_dry_run"
        report["message"] = (
            "Update available on %s: %s -> %s (fetched %s from %s). Dry "
            "run: no changes made. Re-run with --yes to apply."
            % (branch_name, current[:12], target[:12], ref, remote)
        )
        report["would_backup_paths"] = backup_paths
        report["would_stop_services"] = services
        report["would_run_integrity_checks"] = list(
            config.get("integrity_checks") or []
        )
        return report

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

        for unit in services:
            ok, message = _service_action(manager, "stop", unit, service_timeout)
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

        reinstall_package(
            config["python"],
            repo_root,
            config.get("pip_install_args") or ["-e", "."],
            service_timeout,
        )
        sanity_import_check(config["python"], service_timeout)

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
            config["python"],
            config.get("life_txt_path"),
            config.get("integrity_checks") or [],
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
                _service_action(manager, "start", unit, service_timeout)
            report["status"] = "failed_before_code_update"
            report["message"] = str(exc)
        lock.release()
        raise ServerUpdateError(str(exc), step=exc.step, report=report)

    # -- validated: restart services and do the final health check --
    started = []
    restart_failures = OrderedDict()
    for unit in stopped_services:
        ok, message = _service_action(manager, "start", unit, service_timeout)
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
