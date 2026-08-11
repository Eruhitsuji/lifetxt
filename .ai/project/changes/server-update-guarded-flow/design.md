# Design: guarded core update flow

## Components

- `lifetxt/server_update.py` (new module): `load_config`, `run_server_update`
  (orchestrator), `create_backup`, `hash_paths`, `UpdateLock`,
  `run_integrity_checks`, `check_health`, `reinstall_package`,
  `sanity_import_check`, and the git-helper indirection `_git_helpers()`.
- `lifetxt/cli.py`: `command_server_update` (thin CLI adapter: loads config,
  calls the orchestrator, formats the report) and the `server-update`
  argparse subcommand.
- `docs/deployment/ubuntu-server.md`, `docs/en/cli.md` §22: operator-facing
  documentation.

## Why a separate module instead of inline in `cli.py`

`command_update` and its ~10 helper functions already live in `cli.py`.
`server_update.py` is a new module rather than more inline `cli.py`
functions because its orchestration logic (16+ steps, multiple failure
branches, service/backup/hash state threading) is large enough to want its
own focused test module and because it is conceptually a distinct
capability (production deployment orchestration) built *on top of*
`command_update`'s git plumbing, not a variant of `update` itself.

## Why lazy imports for the git helpers

`server_update.py` needs `_run_git_for_update`, `_lifetxt_install_root`,
`_reject_option_like_git_arg`, `_git_commit_summary`, and
`_github_latest_release_or_tag` from `cli.py`. `cli.py` also needs to import
`server_update.run_server_update` to wire the `server-update` subcommand.
A module-level `from .cli import ...` in `server_update.py` would create a
real circular import (each module partially initialized when the other is
imported). Both directions use a deferred import instead: `cli.py`'s
`command_server_update` does `from .server_update import ...` inside the
function body (matching this file's existing pattern for other command
functions, e.g. `from .doctor import optional_dependency_report`), and
`server_update.py`'s `_git_helpers()` does `from .cli import ...` inside the
function body, called only once `run_server_update` actually executes --
by which point `cli.py` has always finished loading (it is the CLI entry
point). This is documented in `_git_helpers`'s own docstring.

## Why a separate `--server-config` file

The application's `.lifetxt.json` (global `--config`) describes workspace
content: source files, defaults, feature toggles. `server-update`'s
deployment config describes the *installation*: which Python environment to
reinstall into, which systemd units to manage, where to write backups. These
are different concerns with different operators potentially editing them
(an application config author is not necessarily the person who provisions
the systemd units). Reusing `--config` for both would also collide with the
global flag `main()` already extracts before argparse ever sees subcommand
flags -- confirmed live during independent review (see decisions.md).

## Failure-state state machine

```text
preflight (dirty tree / detached HEAD / branch mismatch / no target) -> refuse, no lock taken
  |
  v
acquire lock -> backup -> hash(pre) -> [stop only active services]
  |                                          |
  |                                     failure here -> restart what was
  |                                          |          stopped, release
  |                                          |          lock, status=
  |                                          |          failed_before_code_update
  v
git merge --ff-only  (code_update_applied = True from here on)
  |
  failure -> restart what was stopped (still "before" boundary: merge
  |          itself is the code-update line, so a merge failure is treated
  |          as before-code-update for restart purposes)
  v
reinstall -> sanity import -> hash(post) == hash(pre)? -> integrity checks
  |
  failure anywhere in this block -> leave services stopped, release lock,
  |                                 status=failed_after_code_update,
  |                                 report names backup_dir + pre-update SHA
  v
restart services that were stopped -> release lock
  |
  restart failure -> status=validated_restart_incomplete (no raise)
  v
health check
  |
  failure -> status=validated_health_check_failed (no raise)
  v
status=updated
```

Note the `git merge --ff-only` step is treated as the "before code update"
boundary for the restart-on-failure branch (a failed merge means no code
changed, so restoring stopped services is still correct), while
`code_update_applied` flips to `True` immediately after a *successful*
merge, so every subsequent failure (reinstall, sanity check, hash mismatch,
integrity checks) falls into the "leave stopped" branch.

## Service-state tracking (post-review correction)

Original design stopped every unit named in `services` unconditionally and
restarted whatever it had stopped. Independent review (CodeX) found this
loses information: `systemctl stop` on an already-inactive unit still exits
0, so a unit the operator had intentionally left stopped would be added to
`stopped_services` and then started again at the end of a successful run.
Design was corrected to call `systemctl is-active <unit>` first and build
`active_services` -- only units already active are stopped, and therefore
only they are ever restarted. See `decisions.md`.

## Backup write path hardening (post-review correction)

`create_backup()` originally used `os.makedirs(destination, exist_ok=True)`
and `shutil.copy2()`, both of which follow symlinks. `/security-review`
(this session's own pass) found this differs from `UpdateLock.acquire()`'s
existing `O_CREAT|O_EXCL` symlink-safe pattern for the same class of
privileged file write. The finding scored 3/10 under false-positive
filtering (requires a pre-existing directory-permission misconfiguration
outside this code to exploit) and was excluded from the formal report, but
fixed anyway: `create_backup()` now refuses a pre-existing destination
directory outright, and opens each backed-up file with
`os.O_CREAT | os.O_EXCL | os.O_WRONLY` instead of `shutil.copy2`, closing
the window a raced symlink could otherwise redirect a write through. See
`decisions.md`.
