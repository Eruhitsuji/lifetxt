# Design

See `.kiro/specs/lifetxt-self-update/design.md` for the full cc-sdd design document (Overview, Boundary Commitments, File Structure Plan, Requirements Traceability, Security Considerations, Testing Strategy). Summary below per this change package's own format.

## Summary

`lifetxt update` is the only lifetxt command that mutates the git working tree the running install lives in. It resolves the running package's install root (`_lifetxt_install_root`), confirms it is a clean git working tree on a real branch (refusing loudly otherwise), resolves a target ref (explicit `--ref`, or reusing `update-check`'s repository-then-release-then-tag resolution), fetches it from the local git remote, and -- only with `--yes` -- fast-forwards onto it via `git merge --ff-only`. Without `--yes` it stops after the fetch and reports what would happen.

## Key design decisions

1. **Dry-run by default, `--yes` required for any real change.** The default invocation is read-only from the working tree's perspective (a `git fetch` only touches remote-tracking refs and the object database, never the working tree or branch pointer).
2. **Only `fetch` and `merge --ff-only`; nothing else.** No `reset --hard`, no `rebase`, no force-push, no branch switching, no detached-HEAD checkout. A non-fast-forward situation is refused by git itself, not forced.
3. **`--repo`/`update.repository` never selects the git remote.** It only selects which ref name is requested from the GitHub API (shared with `update-check`). The actual `git fetch` always uses the user's own already-configured `origin` (or `--remote`), so a malicious or misconfigured repository value can, at worst, cause a clean "unknown ref" failure against the user's own trusted remote -- never a fetch from an attacker-controlled URL.
4. **No code execution beyond git.** `update` never runs `pip install`, a build backend, or anything from the fetched commit. Picking up dependency changes is reported as a manual follow-up instruction, not automated -- automating it would mean executing arbitrary code from the commit `update` just fetched, a materially larger trust boundary than fetching and fast-forwarding.
5. **Argument-injection guard.** A ref or remote name beginning with `-` is rejected before it ever reaches a `git` argv, closing the class of bug where a maliciously-named tag could be misread as a git command-line option.
6. **UTF-8-safe, timeout-safe subprocess handling.** Found during live verification: the initial implementation used the platform locale codec to decode git's output, which crashed against a real Windows ja-JP-locale directory tree. Fixed to decode explicitly as UTF-8 with `errors="replace"`, and to translate `subprocess.TimeoutExpired` into the same clear-error shape as every other git failure.

## Verification note

Live, unmocked end-to-end verification (dry run, real `--yes` fast-forward confirmed via `git log`, a second run confirming already-up-to-date, dirty-working-tree refusal, and detached-HEAD refusal) was performed against a real disposable clone of this repository, checked out at an old commit on a real branch. This is recorded as manual verification in `verification.yml` since it is not part of the committed automated suite (which uses a mocked `subprocess.run` for speed and determinism).
