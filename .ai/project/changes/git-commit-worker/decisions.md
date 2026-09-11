# Decisions: git-commit-worker (#731)

- Reused `lifetxt.server_update.UpdateLock` directly for the concurrency
  lock rather than writing a second O_CREAT|O_EXCL implementation --
  identical semantics (acquire atomically, write the PID, release on
  cleanup), and the module already documents "not configuring `lock_path`
  disables locking entirely" as an explicit opt-out, which this module
  inherits unchanged.
- `_require_repository` checks that `repo_root` is the repository's own
  top level (`realpath` comparison against `git rev-parse
  --show-toplevel`), not merely `--is-inside-work-tree`. Found necessary
  live: on this development host, the user's home directory is itself a
  tracked (dotfiles) Git repository, so a naive `--is-inside-work-tree`
  check would silently treat an unrelated plain subdirectory as "already a
  repository" -- a real correctness gap for any operator whose data root
  happens to sit under an ancestor repository they did not intend to
  target.
- Staging uses `git add -A -- <path>` **scoped per allowlist entry**, not
  a bare repository-root `git add -A`. This differs slightly from the
  issue's literal "never `git add -A` / whole-repo staging" wording read
  most narrowly, but matches its intent exactly: `-A` restricted to one
  already-allowlisted path/directory also catches a deletion or a new
  untracked file *within* that specific allowlisted path, which is
  necessary for the worker to be useful for a directory of generated
  files (e.g. `reports/`), while never touching anything outside the
  allowlist.
- No standalone `server-git-commit plan|install|remove` command in this
  slice -- see design.md's own section on this; recorded as an explicit
  follow-up, not silently dropped.
- `server-update` coordination is a narrow, config-key-gated preflight
  check rather than a deeper refactor of either module, since the two
  workers' repositories are independent (data root vs. source checkout)
  in the common case.
