# Design: lifecycle temporal consistency

## Shared comparison

`temporal_context.comparable_time_evidence()` exposes the existing
`due`/`do`/`on`/`from` priority and parser at calendar-date granularity.
`temporal_thread.temporal_consistency()` consumes only resolved link records.
No surface, diagnostic, or schema sample implements another comparison rule.

For `new follows:old`, `new` is the expected successor. For
`old replaced_by:new`, the stored target `new` is the expected successor. A
warning exists only when that successor date is strictly before its predecessor
date. Equality remains same-day and produces no warning. `realizes` is ignored.

## Result and bounds

`temporal-thread-v1.consistency` contains `warnings` and `truncated`. Each
warning names the stored relation endpoints, expected/observed order, raw field
values, successor/predecessor roles, and explicit plus derived provenance. The
thread evaluates visible resolved edges and caps warning output at `max_nodes`;
explicit traversal truncation also marks consistency evidence truncated.

## Diagnostic and surfaces

`reference_diagnostics()` converts the shared warning records to time-category
`W244` diagnostics. CLI text renders those same records. TUI and Web display
records already returned by `temporal_thread()`, while Web API and read-only MCP
return the additive result unchanged. No authoritative file write is added.

## Compatibility, security, and rollback

The public JSON object gains an additive section; existing relation and
`temporal-context-v1` semantics are unchanged. Inputs pass through existing ID
resolution and date parsing, and UI text remains escaped. There is no new
dependency, network boundary, write path, migration, or secret handling.
Rollback is a PR revert; no user data requires conversion.
