# AI Reference Patterns

Choose only the relevant category among 68 fictional teaching patterns. Format 1.0 remains authoritative; this catalog adds no grammar or behavior. JA/EN share canonical code and retain each input in its original language to avoid changing its meaning through translation.

[Assistant Prompt Profile](../../prompts/lifetxt-assistant.md) / [Format 1.0](./life_txt_format_spec.md) / [Without MCP](./ai-integration.md#9-without-mcp)

## Read progressively

Normally give the AI your request and the repository URL. From README it reads the Profile, then this index, the relevant category, and the specification as needed. Reading every case or supplying multiple URLs is not required. Disclose unavailable/unverified retrieval; mechanical checks not executed are **not run**.

```text
「明日、草案を作る」をlifetxt形式に変換してください。
https://github.com/Eruhitsuji/lifetxt
```

This does not guarantee retrieval, understanding, correct answers, or delivery. Example baselines are for relative-date exercises, not the current time of supplied absolute-date history/status snapshots. Use the actual conversation date/timezone rather than treating an example date as today.

## Categories and coverage

| Category | IDs | Cases | Source / reuse |
| --- | --- | ---: | --- |
| [Types and purpose](./ai-patterns/types.md) | PAT-TYPE-001–009 | 9 | §2–3, §9, §13–14; tasks/events/habits_reminders/diary/messages/team_status/status_presence |
| [Status and lifecycle](./ai-patterns/statuses.md) | PAT-STATUS-001–007 | 7 | §2, §7.5, §10, §14; tasks/events/messages/status_presence |
| [Time and timezone](./ai-patterns/time.md) | PAT-TIME-001–010 | 10 | §7.4, §8, §9.8–9.9; recurrence_time/messages + conformance |
| [Recurrence and limits](./ai-patterns/recurrence.md) | PAT-REC-001–008 | 8 | §7.6, §8.1; habits_reminders/recurrence_time + tests/test_recurrence.py |
| [IDs, links, hierarchy](./ai-patterns/relationships.md) | PAT-REL-001–008 | 8 | §5.1, §7.1–7.2; linked/hierarchy/recurrence_time + tests/test_links.py |
| [Grammar, values, body](./ai-patterns/grammar.md) | PAT-GRAM-001–008 | 8 | §1.1, §4–7, §11–12, §15–16; json_roundtrip/markdown/attachments/hierarchy |
| [Composite workflows](./ai-patterns/composite.md) | PAT-COM-001–008 | 8 | §7–14 + owning feature docs; minimal/agenda/hierarchy/team_status/messages/diary/attachments |
| [AI semantic pitfalls A](./ai-patterns/pitfalls-a.md) / [B](./ai-patterns/pitfalls-b.md) | PAT-PIT-001–010 | 10 | Profile; AI guide §9; #1164; #1164 comments 6078516662/6078553354/6079794954/6080057300; AI guide contrasts |
| **Total** | Stable IDs; one meaning decision per case | **68** | Canonical fixtures + source comparisons |

Existing examples, Profile, and AI guide supply reused material; natural-language inputs, context, reasons, independent diagnostics, and language mappings are added here. The 68 cases count distinct decisions, not records or counterexample files. init presets are section-oriented starters, not a replacement for this catalog.

### All types and statuses

| Type | Pattern |
| --- | --- |
| `T` | [PAT-TYPE-001](./ai-patterns/types.md#pat-type-001) |
| `E` | [PAT-TYPE-002](./ai-patterns/types.md#pat-type-002) |
| `D` | [PAT-TYPE-003](./ai-patterns/types.md#pat-type-003) |
| `R` | [PAT-TYPE-004](./ai-patterns/types.md#pat-type-004) |
| `H` | [PAT-TYPE-005](./ai-patterns/types.md#pat-type-005) |
| `N` | [PAT-TYPE-006](./ai-patterns/types.md#pat-type-006) |
| `S` | [PAT-TYPE-007](./ai-patterns/types.md#pat-type-007) |
| `M` | [PAT-TYPE-008](./ai-patterns/types.md#pat-type-008) |
| `J` | [PAT-TYPE-009](./ai-patterns/types.md#pat-type-009) |

| Status | Pattern |
| --- | --- |
| `[ ]` | [PAT-STATUS-001](./ai-patterns/statuses.md#pat-status-001) |
| `[/]` | [PAT-STATUS-002](./ai-patterns/statuses.md#pat-status-002) |
| `[x]` | [PAT-STATUS-003](./ai-patterns/statuses.md#pat-status-003) |
| `[-]` | [PAT-STATUS-004](./ai-patterns/statuses.md#pat-status-004) |
| `[>]` | [PAT-STATUS-005](./ai-patterns/statuses.md#pat-status-005) |
| `[?]` | [PAT-STATUS-006](./ai-patterns/statuses.md#pat-status-006) |
| `[N]` | [PAT-STATUS-007](./ai-patterns/statuses.md#pat-status-007) |

### Main key groups

Each entry leads to related cases in its category; a group's keys are covered across cases rather than forced into one example. See Format §9 for type-specific recommendations. Adopt priority/context and similar metadata only when supplied, following PIT-006's non-invention rule.

| Specification group | Keys / boundary | Entry |
| --- | --- | --- |
| Common / §7.1 | `id, source, uid, project, tag, note, body, url, file, dir` | [PAT-GRAM-008](./ai-patterns/grammar.md#pat-gram-008) |
| Links / §7.2 | `parent, ref, depends_on, blocks, related, duplicate_of, replaced_by, follows, realizes` | [PAT-REL-001](./ai-patterns/relationships.md#pat-rel-001) |
| People / §7.3 | `user, owner, assignee, attendee, person, sender, recipient, team, group` | [PAT-COM-005](./ai-patterns/composite.md#pat-com-005) |
| Time / §7.4 | `from, to, on, at, due, do, done, notify_at, notify_from, notify_to, ack, snooze_until` | [PAT-TIME-001](./ai-patterns/time.md#pat-time-001) |
| Effort / §7.5 | `est, elapsed, progress` | [PAT-STATUS-002](./ai-patterns/statuses.md#pat-status-002) |
| Recurrence / §7.6 | `repeat, interval, until, count; RRULE storage/expansion limits` | [PAT-REC-001](./ai-patterns/recurrence.md#pat-rec-001) |
| Messages / §7.7 | `sender, recipient, body, notify_at, notify_from, notify_to, ack, snooze_until, channel` | [PAT-COM-006](./ai-patterns/composite.md#pat-com-006) |
| Journal / §7.8 | `on, at, from, to, mood, weather, loc, body` | [PAT-COM-004](./ai-patterns/composite.md#pat-com-004) |
| Workflow / §7.9 | `reason, moved_to` | [PAT-STATUS-004](./ai-patterns/statuses.md#pat-status-004) |
| System / §7.10 | `created, updated, record` | [PAT-COM-008](./ai-patterns/composite.md#pat-com-008) |

GRAM covers bodies, physical continuation, quotes, comments, headers, Markdown, and attachments; REL covers unresolved/cyclic/partially shared references; PIT covers candidates, requests versus completion, success conditions, retrieval evidence, and capability claims. Complete feature-specific record/audit-history systems belong to [projects](./projects.md), [tickets](./tickets.md), and their owning feature documents.

## Verification and review boundaries

68 cases and 92 independent fixtures (including a yearly variant and counterexamples) were executed against Core 1.0.3/source commit `97aa9b52c231f9aad5ba1403e8ed230d69f4d2a3`. Nine fixed-range agenda results are retained and compared. Commands, input hashes, exits, full diagnostics, and language mappings are in the [manifest](../../examples/ai-patterns/manifest.json); no planned slots remain.

| Class | Interpretation |
| --- | --- |
| A | Syntax error; expected nonzero exit and diagnostics |
| B | Validator warning; may have exit 0 |
| C | Source meaning differs even when syntax passes |
| D | Prose falsely claims a capability or evidence; code alone may pass |

Never invent done/IDs/times to remove warnings. Author source comparison is not independent approval. check does not guarantee source fidelity, successful approval, delivery, or confidential-data exclusion. No external LLM evaluation was run for this catalog; improved model accuracy is unverified.

### Current known limits

- [#1217](https://github.com/Eruhitsuji/lifetxt/issues/1217): The specification's narrow RRULE description differs from additional current Core support. The unsupported example uses measured BYSETPOS/W223, not monthly ordinal BYDAY.
- [#1218](https://github.com/Eruhitsuji/lifetxt/issues/1218): Split on/offset-time anchors and offset representation in RRULE expansion are separately investigated. Stored authored values and instant-comparison fidelity are distinct.
- Consult category observations for month-end/leap-day clamping, bounded floating-time queries, and custom-key/record preservation without promises of search, expansion, or external execution.

## Revalidation and maintenance

```sh
python scripts/check_ai_patterns.py --output .cache/ai-patterns-final.json
python -m unittest tests.test_ai_patterns tests.test_ai_prompt_profile
```

Follow [fixture maintenance](../../examples/ai-patterns/README.md) and update canonical files and JA/EN copies together. Do not recycle IDs; explain consolidation, retirement, or count changes. PRs, independent review, and human merge are tracked in [#1200](https://github.com/Eruhitsuji/lifetxt/issues/1200); complete the parent only after all children reach main. Optional URL-only/Profile-only/Profile+pattern observation belongs to [#1164](https://github.com/Eruhitsuji/lifetxt/issues/1164). [#823](https://github.com/Eruhitsuji/lifetxt/issues/823)'s API remains deferred.
