# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-08-08 | Fix at the read/filter path (`remote_backend.py`), not at Note construction (`ticket_activity.py`) | Claude Code (design phase) | Copy the parent's visibility/owner into the Note's own details when `build_ticket_event`/`build_time_entry` create it | Copying at write time creates a second, independently-driftable copy of privacy state (a later visibility change on the ticket would not retroactively update already-written history Notes); resolving from the parent at read time is always current and keeps this a pure read-path fix | None |
| 2026-08-08 | One-hop, non-recursive inheritance, with a strict "resolves to exactly one item or falls back" rule | Claude Code (design phase) | Recursive parent-chain resolution; best-effort "first match wins" on an ambiguous id | The documented data model has history Notes reference a ticket directly, never another history Note, so one hop is sufficient; recursion would add unbounded-cost risk for no benefit. Falling back only on an *exact* single match reuses the same "don't guess" discipline already established in `links.py`'s `_unique_reference_target` and `remote_ticket_write_core.py`'s `conflict_current_item`, rather than inventing a new ambiguity policy | None |
| 2026-08-08 | Escalate to assurance level High / change_type Security, with a change package | Claude Code (task decomposition) | Treat as an ordinary Standard-assurance task like the rest of this session's batch | `.ai/managed/core/ASSURANCE_LEVELS.md` requires escalation for security impact; this is a permission-filtering correctness fix in the Remote Safe Mode API, the project's only network-facing read surface | Human security/implementation review still required before merge to main, per `human_approvals_required` in `change.yml` |

## Scoping note

A broader research pass (recorded in the GitHub issue) covered every surface
`todo.md`'s original roadmap line named -- team views, integrations, exports,
AI context, notifications, duplicate project definitions, cross-file tasks,
archived/renamed projects. All of those were found to be either already
handled by the existing generic per-item filter, purely descriptive metadata
with no enforcement gap, or outside what a single well-bounded task should
attempt to verify without evidence of an actual leak. This change addresses
the one concrete, evidence-backed gap the research found (ticket history not
inheriting its parent's privacy); the rest are recorded as unexamined, not as
verified-safe, and are candidates for their own future tasks if a concrete
gap is found.
