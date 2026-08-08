# Requirements Document

> **Authoritative copy lives in the change package, not here.**
>
> For non-trivial work, and for anything at High or Regulated assurance, this content is distilled
> into `.ai/project/changes/<change-id>/requirements.yml`, which is what reviewers and the other
> executors read. See `.ai/project/changes/README.md` for when a change package is required at
> all — below that threshold, the issue and pull request carry the reasoning and no package is
> needed.
>
> The formats differ on purpose: this file is Markdown for drafting, the change package is YAML
> for the standard's traceability records. Distilling is a manual step, so this file and the
> package can drift. The package wins.
>
> See #101 for the decision behind this.

## Project Description (Input)

Add an automatic priority-ranking capability to lifetxt's item selection surfaces (starting with `next`, extending to `agenda`), covering all item kinds that carry a `priority`/`due` detail today -- ordinary Tasks and development tickets (`record:ticket`) alike, not development tickets only.

Current behavior (read from the code, not assumed):

- `command_next` (lifetxt/extra_core.py:40) already filters open, unblocked Tasks (kind "T", status in OPEN_STATUSES, `depends_on` targets closed) with optional user/project/context filters, then sorts by a fixed lexicographic key: `_priority_key(priority)` (lifetxt/extra_common.py:287, A-Z then numeric then other-string then blank, each bucketed before the next), then due date ascending (missing due = far future), then created date, then source line number. There is no score, no explanation output, and `agenda` (lifetxt/agenda.py) does not share this ordering at all.
- todo.md's P1 "Workflow Follow-ups" section already anticipates `next --explain` "showing selection reasons and exclusions caused by blockers, deferred state, someday classification, user/project/context filters, ticket workflow state, or missing capabilities" as unscheduled future work -- this spec should account for that direction rather than conflict with it.
- Project principle (.ai/project/RULES.md "Design Principles"): "Preserve old public CLI behavior when introducing richer reports; use explicit modes or unambiguous new flags." The existing `next` sort order is used by scripts today; this spec must not silently reorder default output for existing callers without an explicit opt-in flag/mode.
- Tickets (`record:ticket`) carry their own `priority`, `severity`, and workflow `status` metadata that a cross-kind ranking would need to normalize against Task's simpler `priority`/`due`/`status` model.

User-confirmed scope decisions (asked directly, not assumed):

- Ranking direction: automatic ranking for `next`/`agenda` selection.
- Item scope for this iteration: `next`'s current item universe only (Task, kind `"T"`), no change to which kinds/items are selected.
- Compatibility mechanism: new explicit opt-in flag on `next`; default (no-flag) output stays byte-for-byte unchanged.
- Ranking model: extend the existing deterministic multi-key sort (no weighted numeric score).
- Factor scope for this iteration: fields already common to `next`'s current selection (priority, due date, existing blocked exclusion) only -- no ticket-specific severity/workflow-state factors.
- Command scope for this iteration: `next` only. `agenda` support and an `--explain`-style rationale output are explicitly out of scope here and tracked as separate follow-up work.

A related, pre-existing discrepancy was found while scoping this feature: the CLI `next` command does not use the shared actionable-item definition in `lifetxt/nextaction.py` that the TUI `/next` view and the MCP `get_next_actions` tool both use (different kind coverage, no someday/maybe/waiting exclusion, a different priority-ordering scheme, file-local rather than workspace-wide blocking). This is filed separately as issue #138 and is explicitly out of scope here: this feature ranks the item set `command_next` selects today, unchanged.

## Boundary Context

- **In scope**: An opt-in `--rank` flag on the `next` CLI command that reorders (not re-selects) `next`'s current item set using overdue status plus the existing priority/due/created/line keys.
- **Out of scope**: `agenda` ranking, an `--explain`-style rationale output, ticket-specific ranking factors (severity, workflow status), and reconciling `next`'s item-selection logic with `lifetxt/nextaction.py` (tracked as #138). None of these are addressed by this feature; they remain candidates for later, separately scoped work.
- **Adjacent expectations**: This feature relies on the project's existing deterministic date resolution (the same "today" the rest of the codebase already uses, not a direct host-clock read) to decide whether an item is overdue, so ranked output stays consistent with other timezone-aware behavior in the project. It does not change what "today" means anywhere else.

## Requirements

### Requirement 1: Opt-in ranked ordering with unchanged default behavior

**Objective:** As a lifetxt CLI user or script author relying on `next`'s current output, I want ranking to be strictly opt-in, so that nothing I already depend on changes unless I ask for it.

#### Acceptance Criteria

1. The `next` command shall accept a new `--rank` flag.
2. While `--rank` is not given, the `next` command shall produce item selection and ordering identical to its current behavior.
3. The `next` command shall select the same set of items whether or not `--rank` is given; `--rank` shall change ordering only, never which items are included.
4. When `--rank` is given, the `next` command shall order the selected items using the ranking defined in Requirement 2 instead of the current default ordering.

### Requirement 2: Overdue-aware ranked ordering

**Objective:** As a lifetxt user with a large open-item backlog, I want `next --rank` to surface overdue work first and otherwise respect existing priority, so I do not have to scan due dates myself to find what is most urgent.

#### Acceptance Criteria

1. When `--rank` is given, the `next` command shall place every overdue item ahead of every item that is not overdue.
2. The `next` command shall treat an item as overdue when it has a `due` date earlier than the current date.
3. The `next` command shall treat an item due on the current date as not overdue.
4. The `next` command shall treat an item with no `due` date as not overdue.
5. Where two items have equal overdue status, the `next` command shall order them next by the same priority ordering `next` already uses today.
6. Where two items have equal overdue status and equal priority, the `next` command shall order them next by ascending due date, treating a missing due date as later than any present due date.
7. Where two items have equal overdue status, priority, and due date, the `next` command shall order them next by ascending created date, treating a missing created date as later than any present created date.
8. Where two items remain tied after every preceding criterion, the `next` command shall order them by ascending source line number, matching `next`'s current final tie-break.
9. If `--rank` is given and a selected item has a `due` value that cannot be parsed as a date, the `next` command shall report an error identifying the item and its invalid `due` value, and shall not produce ranked output for that invocation.
10. While `--rank` is not given, the `next` command shall tolerate an unparseable `due` value the same way it does today (treated as absent for sorting purposes), without reporting an error.

### Requirement 3: Ranked output works across existing `next` options

**Objective:** As a lifetxt user or script author, I want `--rank` to compose with every existing `next` option, so ranked output is usable everywhere plain `next` output is usable today.

#### Acceptance Criteria

1. When `--rank` is given together with `--format text`, `--format json`, or `--format life`, the `next` command shall apply the ranked order defined in Requirement 2 to that format's output.
2. When `--rank` is given together with `--limit`, `--user`, `--project`, `--context`, or `-o`/`--output`, the `next` command shall apply those options exactly as it does today, in addition to the ranked ordering.
