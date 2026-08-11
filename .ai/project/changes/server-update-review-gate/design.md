# Design: risk classification and high-impact review gate

## Where this inserts into `run_server_update`

```text
... (preflight, fetch, resolve current/target -- unchanged from #272)
commits, commit_count = git_commit_summary(...)          # unchanged
diff_summary = gather_diff_summary(run_git, ...)          # NEW
risk = classify_risk(diff_summary)                        # NEW
report[...] = risk fields                                 # NEW (also visible in dry-run)
if not yes: return report                                 # unchanged (dry-run branch)
if approve and approve != target: raise approve_mismatch  # NEW
if risk["reasons"] and not approve: return review_required # NEW
lock = UpdateLock(...)                                     # unchanged from here down
...
```

The gate sits entirely between the existing dry-run early-return and the
existing `lock = UpdateLock(...)` line -- no code below that line changed.

## Split: impure gathering vs. pure classification

`gather_diff_summary(run_git, repo_root, current, target, timeout)` is the
only part that touches git (three calls: `diff --no-renames --numstat`,
`diff --no-renames --name-status`, `log --format=%x1e%B`, all over the
`current..target` range). It returns a plain dict:

```python
{"files": [{"path", "added": int|None, "removed": int|None, "deleted": bool}, ...],
 "commit_messages": [str, ...]}
```

`classify_risk(diff_summary, trigger_paths=DEFAULT_RISK_TRIGGER_PATHS,
trigger_keywords=DEFAULT_RISK_TRIGGER_KEYWORDS)` takes that dict (or an
equivalent hand-built fixture) and returns the risk assessment with no I/O
at all. This split is what makes requirement
`req-server-update-review-gate`'s first acceptance criterion ("pure
function... independently unit-testable") literally true rather than
aspirational -- `tests/test_server_update.py`'s `ClassifyRiskTests` never
touches git.

`--no-renames` on both diff calls is deliberate: without it, a renamed
file appears as `{old => new}` in `--numstat`/`--name-status` output,
which would need its own parsing branch for no real benefit here (a
rename is adequately represented as a plain delete+add pair for risk
purposes -- both the old and new paths get evaluated against the trigger
categories, and the file still counts once toward `changed_file_count`
either way).

## Why `\x1e` (record separator) in the git log format

`git log --format=%B` alone, across a commit range, does not give a
machine-parseable boundary between one commit's full body and the next --
a body can itself contain blank lines, so naive blank-line splitting would
misparse it. Prefixing each commit's format output with `%x1e` (ASCII
0x1E, a control character no real commit message would contain) makes
`log.stdout.split("\x1e")` an exact, unambiguous split.

## Why `--approve` implies `--yes` rather than requiring both

The review block's own `approved_command` line, which operators are
expected to copy-paste verbatim, is specified by #260 as `... --approve
<exact-target-sha>` -- no `--yes`. Requiring `--yes` in addition would make
the printed line non-functional as written. `command_server_update`
computes `yes = args.yes or bool(args.approve)` so the printed command
works exactly as printed.

## Why the approve-mismatch check runs unconditionally (not only when a trigger fired)

Requirement `req-server-update-review-gate`'s acceptance criteria state
`--approve` must be validated "including no trigger having fired". If an
operator passes `--approve <stale-sha>` against an update that turns out
to have no risk triggers, silently ignoring the mismatch and proceeding
would be a more permissive contract than the operator's own command
expressed ("I reviewed and approved exactly this commit"). The mismatch
check therefore runs before the `if risk["reasons"]:` branch, not inside
it.

## Stateless approval (no persisted review record)

An earlier design considered writing the review block's target SHA to a
side file so a later `--approve` run could look it up. Rejected: the
target is already re-resolved from git on every invocation (the same
fetch+rev-parse `run_server_update` always does), so comparing the live
resolved target against the `--approve` argument gives the identical
correctness guarantee ("was this reviewed against what's about to be
applied, right now") with no additional state, no cleanup path, and no
new failure mode (a stale or corrupted state file).

## Trigger category file inventory

Categories and their path prefixes were built by listing the real
`lifetxt/*.py` module inventory at implementation time (not guessed), so
that e.g. "config/workspace resolution" names the actual
`config.py`/`config_registry.py`/`config_writer.py`/`config_layers.py`/
`config_migration.py`/`config_validation.py`/`workspace.py`/
`workspace_diagnostics.py` files that exist, not an approximation. See
`lifetxt/server_update.py`'s `DEFAULT_RISK_TRIGGER_PATHS` for the
authoritative list; this design note is not duplicated as a second source
of truth for it.

## Live verification (disposable git repository)

Beyond the fixture-based unit tests, this change was verified against a
real, disposable git repository (bare "origin" + a "checkout" clone,
outside this repository, deleted after verification) to confirm the
review block's real output matches the spec byte-for-byte and that
`--approve` genuinely drives a real `git merge --ff-only`:

1. A commit touching both `lifetxt/parser.py` and
   `contrib/systemd/lifetxt.service`, with commit message `"security:
   harden the systemd unit and parser"`, pushed to the disposable origin.
2. `lifetxt server-update --server-config ... --yes` against the
   disposable checkout printed the exact `LIFETXT_UPDATE_REVIEW_BEGIN/END`
   block, correctly naming both path-based reasons and the keyword
   reason, with accurate `changed_file_count`/`changed_line_count`/
   `binary_file_count`, and made no mutation (confirmed the checkout's
   `HEAD` was unchanged afterward).
3. `--approve <wrong-sha>` was refused with the exact designed message;
   the checkout was still unchanged afterward.
4. `--approve <the real target sha>` proceeded past the gate: the
   checkout's `HEAD` moved to the target commit and `lifetxt/parser.py`
   appeared on disk, confirming the real `git merge --ff-only` ran. It
   then failed at the `pip install` step as expected (no real Python
   package existed at that disposable path) -- this is `#272`'s existing,
   unmodified failure-after-code-update handling, not something this
   change touches.
