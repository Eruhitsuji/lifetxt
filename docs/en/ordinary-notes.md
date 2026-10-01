# Ordinary Notes

`N` is the storage kind, not a promise that a record is a reading memo.
Ordinary Notes are a shared, read-only projection of parsed `N` records.
No migration or `ordinary:true` / `planner:true` key is needed.

The shared classifier excludes Personal Context Notes for any `person:` (using
`is_personal_context_item(person=None)`), Native History `record:item_event`,
ticket audit `record:ticket_event`, ticket time tracking `record:time_entry`,
and progress audit `record:progress_event`, using their existing classifiers.
An unknown `record:` value or a title such as "History" does not exclude a
Note. `assignee:` alone does not classify a Note as Personal Context.

## Browse and search

| Surface | Ordinary Notes | Raw N records |
| --- | --- | --- |
| CLI | `lifetxt notes life.txt --limit 5 --offset 0 --date 2031-02-03` | `lifetxt to-json life.txt --type N`, existing query/show |
| CLI JSON/JSONL | `lifetxt notes life.txt --format json` / `--format jsonl` | existing converters |
| Export, Markdown, fzf/peco | existing item-filter command with `--ordinary-notes` | existing `--type N` filter |
| Web API | `GET /api/notes?date=2031-02-03&limit=5&offset=0` | `GET /api/items?type=N` |
| Existing Web UI | choose **Ordinary Notes** in the type dropdown; search/sort/detail work as usual | choose **Raw Notes (N)** |
| Planner | Notes section, five rows initially, **Load more** for five more | Full Web UI → Raw Notes (N) |
| Local/Remote TUI | `/view notes`; existing search, inspector and `/limit 20` to expand the display cap | `/view raw-notes` |
| Remote Safe Mode | `GET /api/remote/v1/resources/notes` / `lifetxt remote get PROFILE notes --param limit=5` | existing `items` resource |
| MCP | `list_notes` with date/text/offset/limit/sort/order | `list_items` with type N, existing get/search tools |

Use `--text QUERY` with `lifetxt notes`, or `text=QUERY` on `/api/notes` / MCP
`list_notes`. Classification and search occur before pagination. Generic
`/api/items?ordinary_notes=true` and MCP `list_items`'s `ordinary_notes: true`
also use the same shared classifier; their existing filters/sorts remain.
Raw query grammar and direct item lookup continue to work unchanged.

Remote TUI uses the server's projection and fetches bounded pages. It requires
a server supporting `/api/notes`. If unavailable/offline or changed while
paging, it reports an error and requires reload; it never reclassifies cached
raw Notes locally. Ordinary Note classification is identical across surfaces.

## Ordering and pages

The default `relevance` order prioritizes Notes associated with the selected
`date` by existing Agenda date semantics (including valid datetime intervals
and recurrence), then `updated:` descending, then `created:` descending.
Missing/invalid timestamps fall back to stable ID, title, content, source and
line. Existing datetime/offset comparison rules apply. Without a selected
date, only recency and the deterministic fallback are used. No relevance
score is computed. Alternate `sort=title|line|updated|created` and
`order=asc|desc` are available; relevance always uses descending recency.
The Existing Web UI/generic item queries retain their selected item sort.

CLI notes, `/api/notes` and MCP `list_notes` default to five rows per page;
`limit` must be 1–100 and `offset` nonnegative. JSON/API output contains
`items`, `count`, `total` (eligible Notes matching the search), `offset`,
`limit`, `has_more`, `next_offset`, `date`, `sort`, `order` and `revision`.
JSONL uses the existing per-item conversion format. Text output shows the
page count/total and the next offset. The projection fingerprint `revision`
changes when eligible records change. Offset clients should restart at zero
if it changes between pages.

Planner shows displayed/total counts and appends five-row pages. Its Load
more control remains available in read-only mode and disappears on the final
page. Editing/creation uses existing standard Note records. After creation,
editing, a date change, or a projection revision change, the list starts at
page one. This keeps the mobile Day Planner bounded and avoids mixed pages.
The headless browser tests cover English/Japanese and 320/360/390/430 CSS px;
physical device testing remains separate.

Remote Safe Mode applies visibility before classification/counts and preserves its existing path redaction.

The `/remote` browser provides **Ordinary Notes** and **Next Notes page** (20 rows per page) beside **Refresh snapshot** for raw data.
