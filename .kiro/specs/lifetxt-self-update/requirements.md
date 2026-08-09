# Requirements Document

## Project Description (Input)
lifetxt has `update-check` (read-only) but no way to actually update. The
project has no PyPI distribution -- the only documented install method is
`python -m pip install -e .` from a git clone -- so a self-update command
must be git-based, not a package-manager upgrade. This was explicitly
flagged as **not recommended** during scoping (no release pipeline, no
rollback story beyond git itself, and it is the only lifetxt command that
mutates the git working tree the running install lives in) but the user
selected it anyway. Implement it with mandatory, non-optional safety rails:
dry-run by default, explicit confirmation for any real change, refuse on
anything other than a clean git working tree on a real branch, and fail
loudly rather than silently on every error path. Security/High assurance,
full cc-sdd spec plus change package, mirroring the rigor applied to the
`remote-single-worker-guard` change earlier in this session.

## Requirements

### Requirement 1: Update only ever fast-forwards a clean, git-based install
**Objective:** As a lifetxt user, I want `update` to only ever move my
install forward safely, so that it can never lose work, corrupt history, or
silently do something other than what it reports.

#### Acceptance Criteria
1. WHEN the running install is not inside a git working tree, THE SYSTEM
   SHALL refuse with a clear error and make no change.
2. WHEN the git working tree has any uncommitted change, tracked or
   untracked, THE SYSTEM SHALL refuse with a clear error and make no
   change.
3. WHEN `HEAD` is detached (not on a branch), THE SYSTEM SHALL refuse with
   a clear error and make no change.
4. THE SYSTEM SHALL only ever execute `git fetch` and `git merge --ff-only`
   against the working tree -- never `reset --hard`, `rebase`, a force
   push, or any other history-rewriting or destructive operation.
5. WHEN the resolved target is not a fast-forward of the current branch,
   THE SYSTEM SHALL refuse (via `git merge --ff-only`'s own refusal) rather
   than forcing the change.
6. THE SYSTEM SHALL NOT execute `pip install`, a build backend, or any
   other code from the fetched commit as part of `update` -- if a
   dependency change may need picking up, THE SYSTEM SHALL say so as an
   instruction, not perform it.

### Requirement 2: Real changes require explicit confirmation
**Objective:** As a lifetxt user, I want `update` to default to a safe,
read-only preview, so that I cannot apply an update by accident.

#### Acceptance Criteria
1. WHEN `--yes` is not given, THE SYSTEM SHALL fetch (read-only against the
   configured git remote) and report what would change without merging.
2. WHEN `--yes` is given AND the fast-forward succeeds, THE SYSTEM SHALL
   report the new commit and that dependencies may need to be reinstalled
   manually.
3. WHEN the current commit already matches the resolved target, THE SYSTEM
   SHALL report that no update is needed and make no change, regardless of
   `--yes`.

### Requirement 3: The update target is resolved consistently with update-check
**Objective:** As a lifetxt user, I want `update`'s target resolution to
match `update-check`'s, so the two commands never disagree about what "the
latest version" means.

#### Acceptance Criteria
1. WHEN `--ref` is not given, THE SYSTEM SHALL resolve the target using the
   same repository-then-release-then-tag logic `update-check` uses
   (`--repo`, then `update.repository` config, then the built-in default).
2. WHEN `--ref` is given, THE SYSTEM SHALL use it directly as the git ref
   to fetch, without querying the GitHub API at all.
3. WHEN neither `--ref` nor any published release or tag exists for the
   resolved repository, THE SYSTEM SHALL report that there is nothing to
   update to and make no change, exiting successfully.
4. THE SYSTEM SHALL fetch from the local git remote's own already-
   configured URL (`origin` by default, or `--remote NAME`) -- the
   `--repo`/`update.repository` value SHALL only select which ref *name* is
   requested, never which remote URL is used for the actual `git fetch`.

### Requirement 4: Command-line arguments passed to git are validated
**Objective:** As a lifetxt user, I want a malformed or adversarial ref/
remote name to be rejected outright, so that it cannot be misinterpreted as
a git command-line option.

#### Acceptance Criteria
1. WHEN the resolved ref or remote name begins with `-`, THE SYSTEM SHALL
   refuse with a clear error before invoking git, rather than passing it
   through.

### Requirement 5: Every failure path fails loudly
**Objective:** As a lifetxt user, I want every error condition -- a missing
git executable, a network failure, a git command failure -- to be reported
clearly with a non-zero exit status, never silently treated as success.

#### Acceptance Criteria
1. WHEN the `git` executable cannot be found, THE SYSTEM SHALL raise a
   clear error rather than crashing with an unhandled exception.
2. WHEN any git subprocess call fails unexpectedly (non-zero exit where
   success was assumed) or times out, THE SYSTEM SHALL raise a clear error
   identifying which git operation failed and why.
3. THE SYSTEM SHALL decode git's subprocess output using an encoding that
   does not crash on non-ASCII bytes regardless of the host's console/locale
   codepage.
