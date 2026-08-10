# Ticket and Project Reports

`lifetxt.ticket_projects` provides a shared, read-only aggregation layer for development tickets (`T` records with `record: ticket`). Project Hub, Portfolio, the main CLI, MCP, and future surfaces reuse the same report object so they cannot silently calculate different ticket totals or attention queues.

The report contract is published as `schemas/ticket-project-report-v1.schema.json` and advertised through capability discovery as `ticket_project_report`.

See docs/en/tickets.md for the ticket record model, relation keys
(`depends_on`/`blocks`/`parent`/`related`/`duplicate_of`/`replaced_by`), typed
custom fields, and the `ticket validate`/`check` diagnostics that catch a
malformed or cyclic ticket before it reaches this report. See docs/en/cli.md's
`links` section (3.2) for the reference/cycle diagnostics (`W215`-`W229`) that
apply to ticket relation keys. See docs/en/projects.md's Archiving section for
how `lifetxt project archive` moves a done/canceled ticket (and its
`record:ticket_event`/`record:time_entry` history) out of this report's input
set.

## Main CLI commands

The shared report is available in the normal `lifetxt` command tree:

```console
lifetxt ticket summary life.txt
lifetxt ticket board life.txt
lifetxt ticket attention life.txt
lifetxt project tickets lifetxt life.txt
```

`project tickets` accepts `--view summary|board|attention`. All commands accept workspace-resolved input paths, `--project` where applicable, `--at`, `--stale-after`, repeated or comma-separated `--terminal-status` and `--high-severity`, plus `--format text|json` and `--pretty`.

JSON output always returns the complete `ticket-project-report-v1` document, even when the selected text view is `board` or `attention`.

Examples:

```console
lifetxt ticket attention life.txt \
  --project lifetxt \
  --at 2026-07-25T12:00:00+09:00 \
  --stale-after 21

lifetxt project tickets lifetxt life.txt \
  --view board \
  --format json \
  --pretty
```

Configured project aliases are normalized to the canonical project name before ticket aggregation. This keeps Project Hub, Portfolio, CLI, and MCP project totals aligned.

## Standalone diagnostic commands

The original standalone module remains available for scripts and diagnostics:

```console
python -m lifetxt.ticket_projects summary life.txt
python -m lifetxt.ticket_projects board life.txt
python -m lifetxt.ticket_projects attention life.txt
```

Limit the report to one project:

```console
python -m lifetxt.ticket_projects summary life.txt --project lifetxt
```

Use a reproducible reference time and stale window:

```console
python -m lifetxt.ticket_projects attention life.txt \
  --at 2026-07-25T12:00:00+09:00 \
  --stale-after 21
```

Emit the complete versioned report as JSON:

```console
python -m lifetxt.ticket_projects summary life.txt --format json --pretty
```

Override the default terminal-status and high-severity sets by repeating flags:

```console
python -m lifetxt.ticket_projects summary life.txt \
  --terminal-status shipped \
  --terminal-status rejected \
  --high-severity sev1 \
  --high-severity sev2
```

## Effective configuration

Integrated surfaces resolve one effective report configuration:

```json
{
  "ticketing": {
    "statuses": {
      "shipped": {"life_status": "[x]"},
      "wont_fix": {"life_status": "[-]"}
    },
    "high_severities": ["critical", "blocker"],
    "report": {
      "stale_after_days": 14
    }
  }
}
```

- A detailed status is terminal when its effective `life_status` is `[x]` or `[-]`.
- `ticketing.report.high_severities` takes precedence over `ticketing.high_severities` when present.
- `ticketing.report.stale_after_days` takes precedence over `ticketing.stale_after_days` and must be a non-negative integer.
- Explicit CLI or MCP overrides replace the corresponding configured set for that call.

Every report embeds the effective terminal statuses, high severities, stale window, formulas, and caveats.

## Project Hub and Portfolio

`project show`/Project Hub responses now include a project-scoped `ticket_report` object. Portfolio responses include:

- top-level `ticket_report`: the complete cross-project report;
- per-project `ticket_summary`: the exact matching project summary from that report, or `null` when a project has no development tickets.

Generic project `record:issue` records remain separate from development tickets and are not inserted into the ticket report.

## MCP

The following read-only MCP tools return the complete shared report contract:

- `get_ticket_project_report`
- `get_ticket_board`
- `get_ticket_attention`

They accept optional `project`, `at`, `stale_after`, `terminal_statuses`, and `high_severities` arguments. Existing `get_project` and `get_portfolio` responses also include the embedded report fields described above. MCP annotations mark all three report tools as read-only, non-destructive, and idempotent.

Clients can inspect the `ticket_project_report` section of `get_capabilities` or `lifetxt://capabilities` before depending on the schema version, CLI operations, MCP tools, or effective configuration.

## Metrics

The report includes global and per-project totals for:

- total, open, and terminal tickets;
- status, priority, severity, tracker, assignee, and component distributions;
- blocked, dependency-unknown, overdue, unassigned, high-severity, and stale attention counts;
- estimate and elapsed hours with coverage counts;
- paired elapsed-minus-estimate variance only when both values are parseable.

Attention categories overlap. For example, one ticket may be blocked, overdue, unassigned, high severity, and stale simultaneously.

## Ticket row fields

Every ticket in `tickets`, `board`, and `attention` is the same `ticket`-shaped
row (`schemas/ticket-project-report-v1.schema.json`'s `$defs.ticket`):

`id`, `title`, `project`, `status`, `tracker`, `priority`, `severity`,
`assignee`, `reporter`, `component`, `due`, `updated`, `estimate_hours`,
`elapsed_hours`, `depends_on`, `blocks`, `terminal`, `blocked`,
`dependency_unknown`, `unresolved_dependencies`, `unevaluated_dependencies`,
`unevaluated_dependency_reasons`, `overdue`, `unassigned`, `high_severity`,
`stale`, `variance_hours`.

`depends_on` and `blocks` are the ticket's own raw relation values (what it
depends on; what it blocks). `unresolved_dependencies` is different: it is the
computed set of *other open tickets holding this one back*, built from two
sources -- this ticket's own open `depends_on` targets, **and** every other
open ticket in scope whose `blocks:` names this ticket (`blocks:` is declared
on the blocker, so evaluating a ticket's own blockers requires scanning every
other ticket's outgoing `blocks:`, not just this ticket's own details).
`blocked` is `true` when `ticket_status` is `blocked` or
`unresolved_dependencies` is non-empty.

`unevaluated_dependencies`/`unevaluated_dependency_reasons` cover ids the
report could not resolve at all -- absent from the selected (post-project-filter)
read set. Each id maps to one reason:

- `out_of_scope`: the id is directly known to exist in the full read set (a
  ticket in a different, non-selected project, or the source of an open
  `blocks:` reference naming this ticket) -- the report already saw it, so
  disclosing that it exists but was filtered out is safe.
- `missing`: every other case -- genuinely absent, private, archived outside
  scope, or rejected by workspace resolution. The report deliberately does not
  distinguish these, since doing so would disclose whether an otherwise
  invisible ticket exists.

Worked example: filtering `ticket attention` to one project turns a
cross-project `depends_on` into `out_of_scope` rather than `blocked`, because
the target ticket is excluded from `by_id` (used to resolve open dependencies)
but still present in the unfiltered `all_ticket_ids` set used only for this
disclosure decision:

```console
$ lifetxt ticket attention life.txt --project mobile --format json --pretty
```

```json
{
  "id": "BUG-102",
  "project": "mobile",
  "depends_on": ["BUG-100"],
  "blocked": false,
  "dependency_unknown": true,
  "unresolved_dependencies": [],
  "unevaluated_dependency_reasons": {"BUG-100": "out_of_scope"},
  "unevaluated_dependencies": ["BUG-100"]
}
```

(`BUG-100` is a real ticket in project `web`; with no `--project` filter the
same row instead reports `blocked: true` with `BUG-100` in
`unresolved_dependencies`, since it is then resolvable.)

## Formula and missing-data rules

- **Open** means the normalized `ticket_status` is not in the effective terminal-status set.
- **Progress** is terminal ticket count divided by total ticket count. It is count-based and is not a delivery forecast.
- **Blocked** means an open ticket has `ticket_status: blocked`, depends on another open ticket present in the selected report, or is named by another open ticket's `blocks:` reference.
- **Dependency unknown** means a `depends_on` id, or an open `blocks:` reference naming this ticket, is absent from the selected report. See "Ticket row fields" above for the `out_of_scope`/`missing` reason split; the report does not otherwise guess whether a missing ticket is open or terminal.
- **Overdue** means an open ticket's due instant is at or before the reference time. A date-only value remains current through that UTC calendar date. A datetime with an offset uses its explicit offset.
- **Stale** means the newest available `updated`, `modified`, `changed`, `created`, or `opened` timestamp is older than the configured window. Missing timestamps are not called stale.
- Plain numeric duration values are hours. Compact values support `w`, `d`, `h`, and `m`, with one work day equal to 8 hours and one work week equal to 40 hours. Invalid or partially parsed values are excluded rather than guessed.

## Board and attention ordering

Board columns follow a stable built-in status order, followed by unknown custom statuses in lexical order. Tickets are ordered by priority, due value, ticket ID, and title. Project and attention queues are also deterministic.

## Library use

Use the configured surface-neutral adapter when results must match the public CLI and MCP:

```python
from lifetxt.ticket_project_surfaces import build_configured_ticket_project_report

report = build_configured_ticket_project_report(
    items,
    config=config,
    project="lifetxt",
)
```

The lower-level builder remains available when the caller supplies every setting explicitly:

```python
from lifetxt.ticket_projects import build_ticket_project_report

report = build_ticket_project_report(
    items,
    project="lifetxt",
    stale_after_days=14,
)
```

The input may contain normal lifetxt Item objects or mapping-shaped records. Non-ticket Tasks and records such as counter-machine Notes are ignored because discovery requires both item type `T` and `record: ticket`.
