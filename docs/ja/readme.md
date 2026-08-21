# lifetxt documentation

`life.txt` は tasks、events、deadlines、reminders、habits、status/presence records、messages、notes、journals、project work、remote-safe workflows を扱う plain-text format と toolset です。

最初に読む文書:

- [life_txt_format_spec.md](./life_txt_format_spec.md): file format
- [cli.md](./cli.md): command usage と compatibility
- [config.md](./config.md): configuration files と effective settings
- [web.md](./web.md): optional FastAPI/Web UI surface
- [ai-integration.md](./ai-integration.md): MCP と AI client usage
- [use-cases.md](./use-cases.md): practical setups

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

`docs/ja/` 配下の Markdown files に対応する docs index です。

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

sample files は [../../examples/](../../examples/) にあります。

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

install と minimal smoke check。`python -m pip install .`（`-e .`ではない）
は、lifetxtにはまだPyPI packageがないため、release artifactのinstallに
近い形です。`-e .`はlifetxt自体のsourceを編集する開発者向けで、
[readme.mdのDevelopment environmentセクション](../../readme.md#development-environment)
を参照してください:

```sh
python -m pip install .
python -m lifetxt check examples/minimal_life.txt
```
