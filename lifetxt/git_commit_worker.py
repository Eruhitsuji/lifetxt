"""Opt-in periodic Git-commit worker for server-managed lifetxt data (#731).

Disabled unless explicitly configured. Requires an already-existing Git
repository at the data root: this module never runs ``git init``, never
creates a remote, and never configures a global ``user.name``/
``user.email``. It stages only the explicitly configured path allowlist
(never ``git add -A``/whole-repo staging) and commits only when those
allowlist paths actually changed since the previous commit -- a run with no
change to the allowlist is a successful no-op, not an error.

The concurrency lock reuses :class:`lifetxt.server_update.UpdateLock`
unmodified (the same O_CREAT|O_EXCL atomic-acquisition primitive
``server-update`` already uses) rather than a second lock implementation.
"""

from __future__ import annotations

import os
import subprocess
from collections import OrderedDict

from .server_update import ServerUpdateError, UpdateLock

COMMIT_MESSAGE_PREFIX = "lifetxt-auto-commit"


class GitCommitWorkerError(Exception):
    def __init__(self, message, reason):
        super().__init__(message)
        self.reason = reason


def _run(argv, cwd, timeout=30):
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        raise GitCommitWorkerError("git executable not found.", reason="git_missing")
    except subprocess.TimeoutExpired:
        raise GitCommitWorkerError(
            "git command timed out: %s" % " ".join(argv), reason="git_timeout"
        )
    except OSError as exc:
        raise GitCommitWorkerError(
            "Failed to run %s: %s" % (" ".join(argv), exc), reason="git_failed"
        )


def _git(repo_root, args, timeout=30):
    return _run(["git", "-C", repo_root] + list(args), cwd=repo_root, timeout=timeout)


def _refuse(reason, message):
    return OrderedDict(
        (("status", "refused"), ("reason", reason), ("message", message))
    )


def _require_repository(repo_root):
    """Refuse unless ``repo_root`` is itself a Git repository's own top level.

    Checking only ``--is-inside-work-tree`` would accept a plain directory
    that merely happens to sit underneath an unrelated ancestor repository
    (for example a dotfiles repo tracking a user's home directory) -- this
    also requires the resolved top level to equal ``repo_root`` itself, so a
    configured data root that is not its own repository is refused rather
    than silently committing into a repository the operator never intended.
    """
    if not os.path.isdir(repo_root):
        raise GitCommitWorkerError(
            "Data root %s does not exist." % repo_root, reason="data_root_missing"
        )
    result = _git(repo_root, ["rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        raise GitCommitWorkerError(
            "%s is not an existing Git repository. This worker never runs "
            "`git init`; create the repository first." % repo_root,
            reason="not_a_git_repository",
        )
    toplevel = os.path.realpath(result.stdout.strip())
    if toplevel != os.path.realpath(repo_root):
        raise GitCommitWorkerError(
            "%s is not itself a Git repository top level (found %s). "
            "Configure the worker's repo_root to the repository's own root."
            % (repo_root, toplevel),
            reason="not_a_git_repository",
        )


def _current_branch(repo_root):
    symbolic = _git(repo_root, ["symbolic-ref", "-q", "--short", "HEAD"])
    if symbolic.returncode != 0:
        return None
    return symbolic.stdout.strip()


def _identity_configured(repo_root):
    name = _git(repo_root, ["config", "user.name"])
    email = _git(repo_root, ["config", "user.email"])
    return bool(name.stdout.strip()) and bool(email.stdout.strip())


def _staged_paths(repo_root):
    result = _git(repo_root, ["diff", "--cached", "--name-only"])
    if result.returncode != 0:
        raise GitCommitWorkerError(
            "Could not inspect the Git index: %s" % (result.stderr or "").strip(),
            reason="git_failed",
        )
    return [line for line in result.stdout.splitlines() if line.strip()]


def run_commit(
    repo_root, paths, branch, lock_path=None, author_timestamp_fn=None, timeout=30
):
    """Run one periodic-commit attempt; never mutates outside the given repo.

    ``repo_root`` must already be an existing Git repository (never
    auto-created). ``paths`` is the explicit allowlist of paths (relative to
    ``repo_root`` or already-absolute) to ever stage -- nothing else is ever
    staged. ``branch`` is the exact branch name the repository must
    currently be on; a detached HEAD or a different branch refuses the run.

    Returns a dict with ``status`` one of ``"no_op"``, ``"committed"``, or
    ``"refused"``. Raises :class:`GitCommitWorkerError` only for
    environment-level failures (missing git executable, missing/foreign
    repository) that cannot be represented as an ordinary refusal.
    """
    repo_root = os.path.abspath(repo_root)
    paths = list(paths or [])
    if not paths:
        raise GitCommitWorkerError(
            "At least one allowlisted path is required.", reason="no_paths_configured"
        )

    lock = UpdateLock(lock_path)
    try:
        lock.acquire()
    except ServerUpdateError as exc:
        raise GitCommitWorkerError(str(exc), reason="lock_held")
    try:
        _require_repository(repo_root)

        current_branch = _current_branch(repo_root)
        if current_branch is None:
            return _refuse(
                "detached_head",
                "HEAD is detached; the commit worker requires an attached "
                "branch (expected %r)." % branch,
            )
        if current_branch != branch:
            return _refuse(
                "branch_mismatch",
                "Repository is on branch %r, not the configured %r."
                % (current_branch, branch),
            )

        if not _identity_configured(repo_root):
            return _refuse(
                "missing_git_identity",
                "Git user.name/user.email are not configured for this "
                "repository. This worker never configures global Git "
                "identity; set them explicitly first.",
            )

        pre_existing_staged = _staged_paths(repo_root)
        if pre_existing_staged:
            return _refuse(
                "unrelated_staged_changes",
                "The Git index already has staged change(s) unrelated to "
                "this worker: %s. Refusing to touch them."
                % ", ".join(pre_existing_staged),
            )

        for path in paths:
            resolved = path if os.path.isabs(path) else os.path.join(repo_root, path)
            relative = os.path.relpath(resolved, repo_root)
            if relative == os.pardir or relative.startswith(os.pardir + os.sep):
                raise GitCommitWorkerError(
                    "Configured path %r escapes the repository %r." % (path, repo_root),
                    reason="path_escapes_repository",
                )
            add_result = _git(repo_root, ["add", "-A", "--", relative], timeout=timeout)
            if add_result.returncode != 0:
                return _refuse(
                    "stage_failed",
                    "Staging %r failed: %s"
                    % (relative, (add_result.stderr or "").strip()),
                )

        staged = _staged_paths(repo_root)
        if not staged:
            return OrderedDict(
                (
                    ("status", "no_op"),
                    ("message", "No configured path changed; nothing to commit."),
                )
            )

        timestamp_fn = author_timestamp_fn
        if timestamp_fn is None:
            from .timezone_policy import utcnow

            timestamp_fn = utcnow
        message = "%s: %s" % (
            COMMIT_MESSAGE_PREFIX,
            timestamp_fn().strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        commit_result = _git(repo_root, ["commit", "-m", message], timeout=timeout)
        if commit_result.returncode != 0:
            _git(repo_root, ["reset", "--"] + staged, timeout=timeout)
            return _refuse(
                "commit_failed",
                "git commit failed: %s" % (commit_result.stderr or "").strip(),
            )
        sha = _git(repo_root, ["rev-parse", "HEAD"], timeout=timeout).stdout.strip()
        return OrderedDict(
            (
                ("status", "committed"),
                ("commit", sha),
                ("message", message),
                ("paths", staged),
            )
        )
    finally:
        lock.release()
