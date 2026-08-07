# Design Document

## Overview

**Purpose**: This feature delivers an opt-in, overdue-aware ordering to lifetxt CLI users running `next`, so the items most in need of attention surface first without disturbing the command's current default output.

**Users**: Anyone running `lifetxt next` interactively or from a script. Interactive users opt in with `--rank` to triage a large open-item backlog; script authors who never pass `--rank` see no change at all.

**Impact**: Adds one new CLI flag and one new sort key implementation to the existing `next` command (`lifetxt/extra_core.py:40`). No other command, surface (TUI/Web/MCP), or file format changes. The pre-existing item-selection logic (which items `next` considers at all) is untouched.

### Goals
- `next --rank` orders open, unblocked Tasks with overdue items first, then by `next`'s existing priority/due/created/line keys.
- `next` without `--rank` is provably unchanged (same selection, same order, same output bytes).
- The new sort key is a pure, deterministic function directly unit-testable without CLI plumbing.

### Non-Goals
- Ranking for `agenda` (separate future spec).
- `--explain`-style rationale output (separate future spec; see todo.md P1 "Workflow Follow-ups").
- Ticket-specific ranking factors (severity, workflow status) — deferred until a ticket-aware ranking spec exists.
- Reconciling `command_next`'s item-selection logic with `lifetxt/nextaction.py` (tracked separately as #138). This design ranks exactly the item set `command_next` selects today.

## Boundary Commitments

### This Spec Owns
- The `--rank` CLI flag definition on the `next` subcommand.
- The overdue-aware sort key function and its use inside `command_next` when `--rank` is given.
- Test coverage proving both the ranked order (Requirement 2) and the unchanged default (Requirement 1).

### Out of Boundary
- Any change to which items `next` selects (status/kind/blocked/user/project/context filtering in `command_next` stays exactly as-is).
- `agenda` (`lifetxt/agenda.py`) — not touched.
- `lifetxt/nextaction.py` and its consumers (TUI, MCP) — not touched; #138 tracks their convergence separately.
- Ticket (`record:ticket`) priority/severity/workflow fields — not read by this feature.

### Allowed Dependencies
- `lifetxt.timezone_policy.today()` — the project's existing deterministic "today" resolution, already imported and used by `command_workload` and `command_someday` in the same module (`lifetxt/extra_core.py:8,290,392`). This design must call it the same way (no arguments), not read the host clock directly.
- `lifetxt.extra_common._priority_key` and `lifetxt.extra_common._date_value` — the existing helpers `command_next` already uses for its default sort; reused, not reimplemented.

### Revalidation Triggers
- A change to `_priority_key`'s bucket ordering or `_date_value`'s parsing rules changes ranked output too, since both are reused directly.
- A change to `timezone_policy.today()`'s signature or timezone resolution changes what counts as "overdue".
- Any future spec that changes `command_next`'s item-selection filters must re-check that ranked mode still ranks the same (now different) item set correctly — the sort key itself does not need to change, but its inputs would.

## Architecture

### Existing Architecture Analysis
`command_next` (`lifetxt/extra_core.py:40`) is a single function: load items, filter, sort with a fixed `key=lambda item: (...)`, optionally truncate to `--limit`, then render via `--format`. There is no existing strategy/plugin seam for alternate sort orders — `next` has always had exactly one order. This design adds the first branch point (`if args.rank: ... else: ...`) rather than introducing a general sort-strategy abstraction, per the Simplification lens: one boolean flag with two literal sort keys is sufficient for two orders, and a pluggable sort-strategy interface would be speculative for a feature that owns exactly one alternate order today.

### Technology Stack

| Layer | Choice / Version | Role in Feature | Notes |
|-------|------------------|------------------|-------|
| CLI | Python 3.10+ `argparse`, `lifetxt/extra_cli.py` | Adds `--rank` as a boolean flag on the existing `next` subparser | Matches the existing `--pretty` flag's `action="store_true"` pattern in the same file |
| Core logic | Pure Python, `lifetxt/extra_common.py` | New `_rank_key(item, today)` function | No new runtime dependency |

No data/storage, messaging, or infrastructure layers are affected.

## File Structure Plan

### Modified Files
- `lifetxt/extra_common.py` — add `_rank_key(item, today)`, a pure function returning the Requirement 2 tuple key. Placed beside the existing `_priority_key` (line 287) and `_date_value` (line 136) it composes.
- `lifetxt/extra_cli.py` — add `parser.add_argument("--rank", action="store_true")` to the `next` subparser block (`lifetxt/extra_cli.py:67-77`), alongside the existing `--limit`/`--format`/`--pretty` arguments.
- `lifetxt/extra_core.py` — in `command_next` (line 40), after building `selected` and before `if args.limit:`, branch the `selected.sort(key=...)` call on `args.rank`: `False`/absent keeps today's existing lambda unchanged; `True` calls `_rank_key` with `timezone_today()` bound once per invocation.
- `tests/test_extra_cli.py` — extend `ExtraCliTests` (existing harness at line 22, reusing the `SAMPLE` fixture and `run_extra` helper) with cases for `--rank` ordering and for default-output non-regression. Add focused unit tests for `_rank_key` itself (import from `lifetxt.extra_common`) covering each tie-break level from Requirement 2 directly, without going through the CLI.

No new files are needed; this is a two-function, one-flag extension of an existing command.

## Components and Interfaces

| Component | Domain/Layer | Intent | Req Coverage | Key Dependencies (P0/P1) | Contracts |
|-----------|---------------|--------|---------------|---------------------------|-----------|
| `_rank_key` | Core logic (`extra_common.py`) | Compute the Requirement 2 sort tuple for one item | 2.1–2.8 | `_priority_key` (P0), `_date_value` (P0) | Service |
| `command_next` `--rank` branch | CLI (`extra_core.py`) | Select the ranked vs. default sort key at invocation time | 1.1–1.4, 3.1–3.2 | `_rank_key` (P0), `timezone_today` (P0) | Service |

### Core Logic

#### `_rank_key`

| Field | Detail |
|-------|--------|
| Intent | Pure function: one item plus "today" in, one deterministic, totally-ordered sort key out |
| Requirements | 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8 |

**Responsibilities & Constraints**
- Computes overdue status per 2.2–2.4 (earlier than `today` = overdue; due-today or missing-due = not overdue) as the leading key element.
- Delegates priority ordering to the existing `_priority_key` unchanged (2.5).
- Delegates due/created date comparison to the existing `_date_value` unchanged, with the same "missing = far future" convention `command_next`'s current default key already uses (2.6, 2.7).
- Terminates with the item's source `line` for a total order (2.8), matching the current default key's final tie-break.
- Pure function: no I/O, no mutation of `item`. Same inputs always produce the same output, making it directly unit-testable without constructing a CLI invocation.

**Dependencies**
- Outbound: `_priority_key` (`lifetxt/extra_common.py:287`) — priority bucket ordering (P0)
- Outbound: `_date_value` (`lifetxt/extra_common.py:136`) — due/created date parsing (P0)

**Contracts**: Service [x] / API [ ] / Event [ ] / Batch [ ] / State [ ]

##### Service Interface
```python
def _rank_key(item: Item, today: datetime.date) -> tuple:
    """Requirement 2 sort key: (is_overdue, priority_key, due, created, line).

    is_overdue is 0 when item's due date is earlier than `today`, else 1
    (so overdue items sort first under ascending order). priority_key reuses
    _priority_key(_first(item, "priority")) unchanged. due/created reuse
    _date_value, each defaulting to datetime.date.max when absent, matching
    the existing default sort's convention. line falls back to 0 when unset.
    """
```
- Preconditions: `item` is an `Item` as already produced by `_load_items` inside `command_next`; `today` is a `datetime.date`.
- Postconditions: returns a 5-tuple that Python can total-order via `<`; equal inputs (including two distinct `Item`s with identical field values) produce equal keys, which is what drives the Requirement 2 tie-break chain when used as `list.sort(key=...)` (Python's sort is stable, so equal keys preserve `selected`'s incoming order up to the explicit `line` tiebreak already inside the key).
- Invariants: never raises for any `Item` that already passed `command_next`'s existing filter chain (mirrors the total-function contract `_priority_key`/`_date_value` already have today).

**Implementation Notes**
- Integration: `command_next` calls `_rank_key(item, today)` only when `args.rank` is true; `today = timezone_today()` is computed once per invocation, not once per item, so a command that runs across a UTC midnight boundary still ranks every item consistently within that one run.
- Validation: unit tests exercise `_rank_key` directly for each Requirement 2 criterion (overdue-before-not-overdue, due-today-not-overdue, missing-due-not-overdue, tie-breaks cascading through priority → due → created → line) plus CLI-level tests confirming Requirement 1 (default output byte-identical without `--rank`) and Requirement 3 (composition with `--format`/`--limit`/`--user`/`--project`/`--context`/`-o`).
- Risks: none identified beyond the Revalidation Triggers above; the function has no side effects and no new dependency.

## Testing Strategy

- **Unit Tests** (`tests/test_extra_cli.py`, new tests alongside `_rank_key` import):
  1. An overdue item ranks ahead of a higher-priority, not-yet-due item (Requirement 2.1, 2.5 ordering precedence).
  2. An item due exactly today is not treated as overdue (2.3).
  3. An item with no `due` value is not treated as overdue and sorts after items with a present due date at equal priority/overdue status (2.4, 2.6).
  4. Two overdue items with equal priority and due date break the tie by created date, then by line, matching 2.6–2.8.
- **Integration Tests** (`tests/test_extra_cli.py`, `ExtraCliTests`, extending the existing `SAMPLE` fixture and `run_extra` harness):
  5. `next` without `--rank` produces output identical to the current baseline (byte-for-byte, reusing `test_next_excludes_blocked_and_someday_items`'s assertions as a non-regression check) — Requirement 1.2, 1.3.
  6. `next --rank` on the existing `SAMPLE` fixture (extended with at least one overdue item) returns the same item set as plain `next`, only reordered — Requirement 1.3, 1.4.
  7. `next --rank --format json` and `next --rank --format life` reflect the same ranked order as `--format text` — Requirement 3.1.
  8. `next --rank --limit 1` / `--user` / `--project` / `--context` / `-o` each compose correctly with ranked ordering — Requirement 3.2.
