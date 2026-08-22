# lifetxt documentation

`life.txt` is a plain-text format and toolset for tasks, events, deadlines,
reminders, habits, status/presence records, messages, notes, journals, project
work, and remote-safe workflows.

Start with:

- [philosophy.md](./philosophy.md) for why lifetxt exists and the
  principles behind it.
- [life_txt_format_spec.md](./life_txt_format_spec.md) for the file format.
- [cli.md](./cli.md) for command usage and compatibility.
- [config.md](./config.md) for configuration files and effective settings.
- [web.md](./web.md) for the optional FastAPI/Web UI surface.
- [ai-integration.md](./ai-integration.md) for MCP and AI client usage.
- [use-cases.md](./use-cases.md) for practical setups.

## Minimal life.txt

```txt
[ ] T Write_Report due:2026-06-12 project:university assignee:alice
[ ] E Seminar from:2026-06-08T13:00 to:2026-06-08T14:30 loc:university attendee:alice
[/] S Working from:2026-06-06T14:00 state:busy person:self
[ ] M "Review slides" sender:self recipient:alice notify_at:2026-06-06T09:00 channel:teams
[N] J "Research day" on:2026-06-23 mood:good tag:lab
| Read papers in the morning.
| Wrote parser tests in the afternoon.
[N] N Research_Memo project:research
```

## Topic index

Every Markdown file under `docs/en/` is listed here.

| Topic | Document |
| --- | --- |
| AI/MCP integration | [ai-integration.md](./ai-integration.md) |
| CLI reference | [cli.md](./cli.md) |
| Configuration | [config.md](./config.md) |
| Delegated mutations, remote attachments, recovery | [delegated-remote-attachments-and-recovery.md](./delegated-remote-attachments-and-recovery.md) |
| Editor setup and safe edit flow | [editor.md](./editor.md) |
| Inbox workflows | [inbox.md](./inbox.md) |
| Format specification | [life_txt_format_spec.md](./life_txt_format_spec.md) |
| Daily hub, areas, backlinks | [life-hub.md](./life-hub.md) |
| Messaging and notifications | [messaging.md](./messaging.md) |
| New CLI workflows | [new-cli-workflows.md](./new-cli-workflows.md) |
| People, teams, groups | [people.md](./people.md) |
| Philosophy and long-term vision | [philosophy.md](./philosophy.md) |
| Process boundaries and transaction admin | [process-boundaries-attachments-and-transaction-admin.md](./process-boundaries-attachments-and-transaction-admin.md) |
| Projects and portfolios | [projects.md](./projects.md) |
| Public surface revisions | [public-surface-revisions.md](./public-surface-revisions.md) |
| Query language and saved views | [query.md](./query.md) |
| Documentation index | [readme.md](./readme.md) |
| Release baselines | [release-baselines.md](./release-baselines.md) |
| Release policy gates | [release-policy-gates.md](./release-policy-gates.md) |
| Release safety foundations | [release-safety-foundations.md](./release-safety-foundations.md) |
| Remote Safe Mode | [remote.md](./remote.md) |
| Remote CLI write client | [remote-client-writes.md](./remote-client-writes.md) |
| Remote compatibility | [remote-compatibility.md](./remote-compatibility.md) |
| Remote ticket mutations | [remote-ticket-writes.md](./remote-ticket-writes.md) |
| Round-trip and multiline body rules | [roundtrip-and-body.md](./roundtrip-and-body.md) |
| Safe writes, attachments, work sessions | [safe-writes-attachments-and-work-sessions.md](./safe-writes-attachments-and-work-sessions.md) |
| Search and fuzzy matching | [search.md](./search.md) |
| Shared mutation routing | [shared-mutation-routing.md](./shared-mutation-routing.md) |
| Ticket projects | [ticket-projects.md](./ticket-projects.md) |
| Tickets and workflow history | [tickets.md](./tickets.md) |
| Timezone-aware datetimes | [timezone-aware-datetimes.md](./timezone-aware-datetimes.md) |
| Timezone, revisions, workspace safety | [timezone-revision-workspace-safety.md](./timezone-revision-workspace-safety.md) |
| Transaction recovery and strict timers | [transaction-recovery-and-strict-timers.md](./transaction-recovery-and-strict-timers.md) |
| Use-case guide | [use-cases.md](./use-cases.md) |
| Web API and UI | [web.md](./web.md) |

## Examples

Sample files are available in [../../examples/](../../examples/), including:

- [minimal_life.txt](../../examples/minimal_life.txt)
- [tasks_life.txt](../../examples/tasks_life.txt)
- [events_life.txt](../../examples/events_life.txt)
- [habits_reminders_life.txt](../../examples/habits_reminders_life.txt)
- [status_presence.txt](../../examples/status_presence.txt)
- [team_status_life.txt](../../examples/team_status_life.txt)
- [messages_life.txt](../../examples/messages_life.txt)
- [diary_life.txt](../../examples/diary_life.txt)
- [markdown_life.txt](../../examples/markdown_life.txt)
- [linked_life.txt](../../examples/linked_life.txt)
- [recurrence_time_life.txt](../../examples/recurrence_time_life.txt)
- [hierarchy_life.txt](../../examples/hierarchy_life.txt)
- [agenda_life.txt](../../examples/agenda_life.txt)
- [json_roundtrip_life.txt](../../examples/json_roundtrip_life.txt)
- [calendar_import.ics](../../examples/calendar_import.ics)

## Verification

Install and run the minimal smoke check. `python -m pip install .` (not
`-e .`) matches how a release artifact installs, since lifetxt has no PyPI
package yet; `-e .` is for editing lifetxt's own source, covered by
[readme.md's Development environment section](../../readme.md#development-environment):

```sh
python -m pip install .
python -m lifetxt check examples/minimal_life.txt
```
