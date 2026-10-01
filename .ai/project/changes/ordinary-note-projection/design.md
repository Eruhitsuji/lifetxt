# Ordinary Note projection (#1020)

Implementation phase; adaptive-default/Kanban/W-model. Feature, Standard
assurance as assigned in the issue. Additive read-only APIs require a change
package. Owner/integration authority: Eruhitsuji. One justified M change:
classification and its adapters must land together so parity is reviewable;
there is no independently useful migration or separate persistence change.

## Surface inventory (before implementation)

| Surface | Existing Note access | Planned ordinary access | Raw access retained |
| --- | --- | --- | --- |
| Core | parsed N Items | classifier, selector, bounded page | parsed Items |
| CLI | conversions, query, show | notes; shared filter --ordinary-notes | existing commands |
| Web API | /api/items type=N, item detail | /api/notes; ordinary_notes item filter | unchanged /api/items |
| Existing Web UI | type dropdown, search, detail | Ordinary Notes dropdown via API | Raw Notes dropdown |
| Planner | raw first 20 N | /api/notes date context, 5-row pages | full Web UI |
| local interactive TUI | dashboard, search, CLI commands | /view notes and /view raw-notes | /view raw-notes |
| Remote TUI | server item reads, search/detail | server-authoritative /api/notes | existing server items |
| Remote Safe Mode / browser | items/search resources and snapshot JSON | shared notes resource after visibility filtering; ordinary/next-page buttons | items resource / Refresh snapshot |
| MCP | list_items, search_items, get_item | list_notes and ordinary_notes filter | existing tools |
| fzf / peco | generic filtered item picker | shared --ordinary-notes filter | existing type filter |
| export / Markdown | generic item filters | shared --ordinary-notes filter | existing exports |
| query/saved views/editor | raw query language or record access | CLI/Web/TUI/MCP ordinary entry points above | no raw query grammar changes |

## Contracts and reuse

Reuse Personal Context's classifier with person=None (any named person),
Native History is_item_event, ticket is_ticket_event/is_time_entry, and
is_progress_event. The latter three are explicit audit/time-tracking records,
not freeform reading Notes. Unknown record markers and title prefixes are not
exclusions. No Format change, no new engine, no browser classification.

Filter before sorting/paging. Default: selected-date agenda association first,
then updated descending, created descending, then stable ID/title/content,
source/line last. Date association uses existing item_time_matches, not string
prefix heuristics. Use existing datetime comparison policy. Complexity:
O(n log n) time / O(n) memory; no index/cache/database is needed for normal
text workspaces. Default 5, max 100 per bounded API page; offset >=0.
Optional alternate sort uses existing shared Web sort helper.

Page response includes count, total, has_more, next_offset, date, sort, and a
projection revision fingerprint. Planner appends bounded pages only if date,
load generation and revision still match; changes reset to page one. This
prevents duplicates/reordering when notes change or navigation races a request.
Remote TUI retrieves server pages and fails explicitly if no projection is
available; it never reclassifies its raw/offline snapshot.

## Review / verification viewpoints

Domain boundary and classifier reuse; filter before limit; cross-surface
parity; offsets/date/order validation; mutation/read-only compatibility;
raw queries unchanged; page race/error/revision handling; EN/JA and mobile
320/360/390/430 geometry. Security: read middleware unchanged, untrusted
paging/date input validated, rendered text uses textContent, no new writes,
credentials/dependencies/configuration. Shared files (routing, CLI registry,
capabilities/traceability) integrated in one branch by the implementer, with
final independent human review and merge authority retained. Revert the PR
for rollback; no data migration is needed.
