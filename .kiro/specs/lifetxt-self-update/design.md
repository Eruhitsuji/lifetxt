# Design Document

## Overview
Add `lifetxt update` to `lifetxt/cli.py`: `command_update(args)`, backed by
three small helpers -- `_lifetxt_install_root()` (locates the running
package's source tree), `_run_git_for_update(args_list, cwd, timeout)` (a
single, careful subprocess wrapper: explicit UTF-8 decoding with
`errors="replace"`, a bounded timeout, `FileNotFoundError`/`OSError`
translated into a clear `ValueError`), and `_reject_option_like_git_arg`
(argument-injection guard). Reuses `_resolve_update_check_repo` and
`_github_latest_release_or_tag` from the `cli-update-check` change
unmodified for target resolution.

## Boundary Commitments
### This Spec Owns
- `command_update`, its three helpers, and the `update` subparser.
### Out of Boundary
- `update-check` and its resolution helpers -- reused, not modified.
- Any package-manager-based update path (no PyPI distribution exists to
  update from; explicitly not attempted).
- Automatically running `pip install` or any build/setup code after a
  successful update -- deliberately not implemented; the command prints an
  instruction instead. Running arbitrary code from a freshly-fetched commit
  as part of `update` itself would be a materially larger trust boundary
  than fetching and fast-forwarding, and is out of scope for this change.
- Any non-git install path (wheel, sdist, a hypothetical future PyPI
  package) -- refused with a clear error, not attempted.
### Allowed Dependencies
- `subprocess` (stdlib), `lifetxt.__file__` (to locate the install root),
  `_resolve_update_check_repo`/`_github_latest_release_or_tag` (from the
  `cli-update-check` change).

## File Structure Plan
### Modified Files
- `lifetxt/cli.py` -- `update` subparser, `command_update`,
  `_run_git_for_update`, `_lifetxt_install_root`,
  `_reject_option_like_git_arg`.
- `tests/test_lifetxt.py` -- regression tests (git subprocess mocked).
- `docs/en/cli.md`, `docs/ja/cli.md` -- command documentation.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1 | `git rev-parse --show-toplevel` non-zero exit -> `ValueError` naming the install root |
| 1.2 | `git status --porcelain` non-empty output -> `ValueError`, checked before any fetch |
| 1.3 | `git symbolic-ref -q --short HEAD` non-zero exit (detached) -> `ValueError` |
| 1.4, 1.5 | Only `["fetch", ...]` and `["merge", "--ff-only", "FETCH_HEAD"]` are ever invoked; `--ff-only` is git's own non-forcing refusal mechanism for a non-fast-forward |
| 1.6 | No call to `pip`, `setup.py`, or any build backend anywhere in `command_update`; the "updated" message names the manual follow-up step instead |
| 2.1 | `getattr(args, "yes", False)` false -> report `update_available_dry_run` and `return 0` before any `merge` call |
| 2.2 | `--yes` true and merge succeeds -> report `updated` with the dependency-reinstall instruction |
| 2.3 | `current == target` (both from `git rev-parse`) short-circuits to `up_to_date` before the dry-run/`--yes` branch is even reached |
| 3.1, 3.2 | `ref = getattr(args, "ref", None)`; only when falsy does the function call `_resolve_update_check_repo`/`_github_latest_release_or_tag` at all |
| 3.3 | `latest_text is None` -> informational message, `return 0`, no fetch attempted |
| 3.4 | `remote` defaults to `"origin"` / `--remote`; `repo` is only ever passed to `_github_latest_release_or_tag` (a GitHub API call), never to any `git` subprocess argument |
| 4.1 | `_reject_option_like_git_arg` applied to both `remote` and `ref` before either reaches `_run_git_for_update` |
| 5.1 | `_run_git_for_update` catches `FileNotFoundError` and re-raises `ValueError` |
| 5.2 | Every git call site checks `.returncode` explicitly and raises `ValueError` naming the failed operation; `_run_git_for_update` also catches `subprocess.TimeoutExpired` (not a subclass of `OSError`, so it needs its own `except` clause) and re-raises it as the same clear `ValueError` shape, so a hang reports identically to any other git failure instead of an unhandled traceback |
| 5.3 | `subprocess.run(..., encoding="utf-8", errors="replace")` instead of the platform-locale default -- found and fixed during live verification: a bare `universal_newlines=True` crashed decoding git output against a real Windows ja-JP-locale directory tree before this fix |

## Security Considerations
- **Trust boundary**: `update` never fetches from a URL derived from
  `--repo`/`update.repository`; it only ever fetches from the git remote
  the user already configured (`origin` by default). `--repo` only affects
  which ref *name* the GitHub API is asked about. A malicious
  `update.repository` value can therefore, at worst, cause `update` to
  request a ref name from the user's own already-trusted remote that
  doesn't exist there (a clean `git fetch` failure) -- it cannot cause a
  fetch from an attacker-controlled remote.
- **Argument injection**: a ref or remote name beginning with `-` is
  refused before being placed in a `git` argv, closing the class of bug
  where a maliciously-named tag (e.g. `--upload-pack=...`) could be
  misread as a git option.
- **No code execution beyond git itself**: `update` never invokes `pip`,
  `python setup.py`, or any build backend. The commit's own code is not
  executed by `update`; the working tree is simply fast-forwarded to it,
  identical in effect to a user running `git pull` themselves.
- **No credential handling**: `git fetch` uses the user's own existing git
  credential configuration (SSH agent, credential helper, etc.), exactly as
  a manual `git fetch` would. No new secret storage or handling is
  introduced.
- **Destructive-operation avoidance**: no `reset --hard`, no `rebase`, no
  force-push, no branch switching, no detached-HEAD checkout. The only
  mutation is a fast-forward merge, which git itself refuses when unsafe.

## Testing Strategy
- Unit tests with `subprocess.run` mocked (a per-call dispatcher keyed on
  the git subcommand tail) covering: dry run reports without merging,
  `--yes` merges, already-up-to-date short-circuits before fetch/merge,
  dirty tree refused, detached HEAD refused, non-git install refused, fetch
  failure fails loudly, merge failure fails loudly, missing git executable
  fails loudly, option-like ref/remote rejected, no-ref-and-no-release does
  nothing, an explicit `--ref` never calls the GitHub API, and argparse
  wiring.
- Live, unmocked end-to-end verification against a real disposable clone of
  this repository (not part of the committed suite): checked out an old
  commit on a real branch, ran a dry run (correctly reported the pending
  fast-forward), ran with `--yes` (correctly fast-forwarded, confirmed via
  `git log`), ran again (correctly reported already up to date), confirmed
  the dirty-working-tree refusal and the detached-HEAD refusal each fire
  correctly against the same real clone, and confirmed the encoding fix
  against a real Windows ja-JP-locale directory that had triggered the
  original crash.
- Full suite re-run to confirm no regression elsewhere.
