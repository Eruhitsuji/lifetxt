# Design: git-commit-worker (#731)

## Core module

`lifetxt/git_commit_worker.py` exposes one function, `run_commit(repo_root,
paths, branch, lock_path=None, author_timestamp_fn=None, timeout=30)`,
returning a dict with `status` in `{"no_op", "committed", "refused"}`.
Environment-level failures (no `git` executable, `repo_root` not itself a
Git repository top level, no allowlist configured, a path escaping the
repository) raise `GitCommitWorkerError` instead, since they cannot be
represented as an ordinary run outcome.

## Sequence

1. Acquire `lifetxt.server_update.UpdateLock(lock_path)` (the exact same
   O_CREAT|O_EXCL primitive `server-update` already uses -- no second lock
   implementation). A held lock raises `GitCommitWorkerError(reason=
   "lock_held")`.
2. `_require_repository`: `git rev-parse --show-toplevel` must succeed and
   resolve (via `os.path.realpath`) to `repo_root` itself -- not merely an
   ancestor repository `repo_root` happens to sit inside. This was found
   necessary during testing on a host whose home directory is itself a
   tracked (dotfiles) repository: checking only
   `--is-inside-work-tree` would have silently accepted an unrelated plain
   directory as "a repository" by inheriting that ancestor.
3. Current branch via `git symbolic-ref -q --short HEAD`; `None` means
   detached HEAD (refused). A value not equal to the configured `branch`
   is refused.
4. `git config user.name`/`user.email` must both be non-empty (local or
   inherited from global/system config, matching ordinary Git resolution
   order) -- missing either refuses.
5. `git diff --cached --name-only` before touching anything: any
   pre-existing staged path at all refuses the run untouched.
6. For each allowlist path, resolved relative to `repo_root` and checked
   not to escape it, `git add -A -- <path>` (scoped to that one path/
   directory, never a bare `git add -A`).
7. `git diff --cached --name-only` again: empty means nothing in the
   allowlist changed -> `no_op`. Non-empty means commit with message
   `"lifetxt-auto-commit: <UTC ISO8601 timestamp>"` (the fixed prefix is
   `COMMIT_MESSAGE_PREFIX`). A commit failure resets the staged paths back
   out before reporting `refused`/`"commit_failed"`, so the worker never
   leaves a partial staged state on that failure path.
8. Release the lock in a `finally` block regardless of outcome.

## CLI

`lifetxt git-commit-worker run --repo-root PATH --path PATH [--path PATH...]
--branch NAME [--lock-file PATH] [--format text|json]` is the oneshot
action the generated systemd service's `ExecStart=` invokes. It is a thin
argument-parsing/rendering wrapper over `run_commit()`; exit code is 0 for
`committed`/`no_op` and 1 for `refused` (matching the shell convention
`server-report`'s CLI already uses for its own failure states).

## systemd unit generation

`server_init.py` gains `git_commit_worker_service_unit_text(config)` /
`git_commit_worker_timer_unit_text(config)`, following the exact structural
shape `report_service_unit_text()`/`report_timer_unit_text()` already
established (marker comment, `[Unit]`/`[Service]`/`[Timer]` sections, the
same `NoNewPrivileges=true`/`PrivateTmp=true`/`ProtectSystem=strict`/
`ProtectHome=true`/`ReadWritePaths=` hardening). The opt-in
`git_commit_worker` config section (disabled by default) is validated by
`_validate_git_commit_worker_config()`, mirroring
`_validate_reporting_config()`'s own validate-then-generate structure, and
wired into `build_plan()` immediately after the reporting-jobs block, so
the two generated unit files pick up the same generic idempotency/conflict
classification (`_classify_path`) every other `build_plan()` step already
gets -- no separate idempotency mechanism was written for this worker.

## `server-update` coordination

`server_update.run_server_update()` gained one opt-in preflight check: if
`config.get("git_commit_worker_lock_path")` is set and that file currently
exists, refuse to start (`step="preflight"`) rather than racing the
worker's own git operations. This is deliberately narrow: the worker's
repository is normally the deployment's *data* root, independent of
`server-update`'s own *source checkout* (`install_root`), so most
deployments need no coordination at all; the check only activates when an
operator explicitly configures the shared lock path, per the task's own
"if cheap, add a coordination check" instruction rather than a larger
`server_update` refactor.

## Why no standalone `server-git-commit` install command in this slice

`server-report`'s already-running-deployment install pattern
(`plan|install|remove`) was considered as the model to mirror, per the
task's own suggestion. It was not implemented in this first slice for time
reasons; `server-init`'s own opt-in section already satisfies the task's
core requirement ("generate the systemd oneshot + timer through the same
plan-first idempotent pattern `server_init.py` already uses"). A
standalone install command is recorded as an explicit, unimplemented
follow-up in requirements.yml's `open_questions` and in
docs/deployment/ubuntu-server.md, not silently dropped.
