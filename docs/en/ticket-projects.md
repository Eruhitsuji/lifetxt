# Ticket and Project Reports

`lifetxt.ticket_projects` provides a shared, read-only aggregation layer for development tickets (`T` records with `record: ticket`). It is designed to be reused by Project Hub, Portfolio, CLI, MCP, Web, TUI, and command-center surfaces so those surfaces do not calculate different ticket totals.

The report contract is published as `schemas/ticket-project-report-v1.schema.json`.

## Commands

Run the report directly against one or more life.txt files:

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

## Metrics

The report includes global and per-project totals for:

- total, open, and terminal tickets;
- status, priority, severity, tracker, assignee, and component distributions;
- blocked, dependency-unknown, overdue, unassigned, high-severity, and stale attention counts;
- estimate and elapsed hours with coverage counts;
- paired elapsed-minus-estimate variance only when both values are parseable.

Attention categories overlap. For example, one ticket may be blocked, overdue, unassigned, high severity, and stale simultaneously.

## Formula and missing-data rules

- **Open** means the normalized `ticket_status` is not in the configured terminal-status set.
- **Progress** is terminal ticket count divided by total ticket count. It is count-based and is not a delivery forecast.
- **Blocked** means an open ticket has `ticket_status: blocked` or depends on another open ticket present in the selected report.
- **Dependency unknown** means a `depends_on` identifier is absent from the selected report. The report does not guess whether that missing ticket is open or terminal.
- **Overdue** means an open ticket's due instant is at or before the reference time. A date-only value remains current through that UTC calendar date. A datetime with an offset uses its explicit offset.
- **Stale** means the newest available `updated`, `modified`, `changed`, `created`, or `opened` timestamp is older than the configured window. Missing timestamps are not called stale.
- Plain numeric duration values are hours. Compact values support `w`, `d`, `h`, and `m`, with one work day equal to 8 hours and one work week equal to 40 hours. Invalid or partially parsed values are excluded rather than guessed.

Every JSON report embeds its formulas, caveats, effective terminal statuses, and effective high severities.

## Board and attention ordering

Board columns follow a stable built-in status order, followed by unknown custom statuses in lexical order. Tickets are ordered by priority, due value, ticket ID, and title. Project and attention queues are also deterministic.

## Library use

```python
from lifetxt.ticket_projects import build_ticket_project_report

report = build_ticket_project_report(
    items,
    project="lifetxt",
    stale_after_days=14,
)
```

The input may contain normal lifetxt Item objects or mapping-shaped records. Non-ticket Tasks and records such as counter-machine Notes are ignored because discovery requires both item type `T` and `record: ticket`.
