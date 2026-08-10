# Design: `archive-plan-v1` and `--apply-plan`

## Problem

Production incident #183 found all four of `life.txt`, its config, and two
pre-archive backups zero bytes after a `project archive` operation, with the
exact triggering command sequence unrecoverable from retained history.
`archive_safety_v3.py` (from the incident's initial follow-up, #184) already
hardened the ad-hoc `--revision`-flag path: exact-revision requirements,
zero-byte refusal, parser-error refusal, all preceding any write. What it
does not provide is a *reviewable* artifact -- an operator (or a script)
still has to hand-copy `--revision PATH=SHA256` tokens from dry-run text
output, with no way to review, diff, or hold "what will happen" as its own
object before deciding to apply it.

## Approach

`archive-plan-v1` freezes every input a live archive run needs into one JSON
document:

- resolved workspace/config identity and config revision
- exact source and destination revisions (SHA-256, matching
  `archive_safety_v3.py`'s existing revision computation)
- the frozen selected item-ID set (not just a filter description -- the
  literal list `command_archive`'s selection produced)
- external-reference effects, mirroring the existing dry-run warning content
- the archive parameters (statuses, before, max_items, mode,
  orphan_children, preserve_structure, block_on_external_refs) so
  `--apply-plan` never re-reads current CLI flags for them
- writer/process provenance (process name, PID, host, user) for audit
  correlation
- a `reserved_transaction_id` (a UUID, generated at emit time) for audit
  correlation across emit and apply
- a `plan_hash`: a SHA-256 over the canonical (sorted-key) JSON serialization
  of every other field, so any post-emission edit to the plan file is
  detectable

`--apply-plan` re-derives every one of those facts from current state and
compares. Any mismatch refuses loudly, before `command_archive` is ever
invoked -- mirroring the precede-side-effects discipline
`archive_safety_v3.py` already established. On success, execution reuses
`command_archive` unchanged, passing the plan's frozen parameters and the
now-reverified current revisions as `--revision` tokens (so the existing
`archive_safety_v3.py` revision-completeness check, layered underneath, is
still satisfied).

A verify-then-confirm gate (`--apply-plan` without `--yes` only reports;
`--yes` is required to actually write) was added beyond the minimum spec
during implementation, giving a second explicit confirmation step even for
an unmodified, unexpired plan -- consistent with this project's
`AI_HUMAN_INTERACTION.md` preference for explicit confirmation before
destructive operations.

## Components

| Component | File | Responsibility |
| --- | --- | --- |
| Plan schema | `lifetxt/schema_extensions_v23.py`, `dist/schemas/archive-plan-v1.schema.json` | Structural validation contract |
| Plan build/verify primitives | `lifetxt/archive_plan_v1.py` | `build_plan`, `write_plan`, `load_plan`, `verify_plan_version`, `verify_plan_hash`, `verify_revisions_unchanged`, `verify_workspace_revision_unchanged`, `verify_selection_unchanged`, `journal_directory_reachable`/`verify_recovery_evidence_reachable` |
| CLI wiring | `lifetxt/cli.py` (`command_project_archive`, `_project_archive_emit_plan`, `_project_archive_apply_plan`) | Argument parsing, mutual-exclusion checks, orchestration |

## Requirements Traceability

| Requirement | Design Element |
| --- | --- |
| req-archive-plan-v1-schema-and-emit | `archive_plan_v1.build_plan`/`write_plan`, `schema_extensions_v23.py`, `_project_archive_emit_plan` |
| req-archive-apply-plan-verification-execution | `archive_plan_v1.verify_*`, `_project_archive_apply_plan` |
| req-archive-plan-v1-operator-docs | `docs/en/projects.md`, `docs/ja/projects.md` |

## Alternatives Considered

See `decisions.md`.

## Known Gap Found During This Work

`project archive` itself (the base command, independent of this change) was
never documented in `docs/en/` or `docs/ja/` before this change -- confirmed
by search; `cap-project-archive-workflow`'s own `implementation_locations`
list only code and tests, no docs. This change adds a `## Archiving` section
to `docs/en/projects.md`/`docs/ja/projects.md` covering both the base command
and the plan workflow together, since documenting the plan workflow alone
with no base-command context would be confusing. This closes that
pre-existing documentation gap as a side effect; it was not itself a named
requirement of #254/#255/#256, so it is recorded here rather than silently
expanding the requirements list after the fact.
