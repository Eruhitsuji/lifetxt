# Global Search

`find` searches across everything lifetxt knows — life.txt items and the derived
entities it computes: projects, people, groups, areas, and staged inbox
proposals. Results are grouped by entity type, each with the field that matched
and a short snippet. It scans directly; no index is built until benchmarks
justify one.

For field-scoped or regex search within items only, use `search`. `find` is the
wider, cross-entity view.
Both `search` and `find` support opt-in fuzzy matching. Exact substring matches
still rank first; fuzzy results are fallback matches for small typos and
omissions.

## Usage

```console
$ lifetxt find web
$ lifetxt find alice --type person
$ lifetxt find example.com          # matches a url: detail
$ lifetxt find roadmap              # matches an item body
$ lifetxt find engineering --type group
$ lifetxt find widgets --json
$ lifetxt find Wrte_Report --fuzzy
```

## What it searches

| Entity      | Matches on                                              |
| ----------- | ------------------------------------------------------- |
| `item`      | title, body, and any detail value (project, url, tag, …) |
| `project`   | name, display name, owner, area                         |
| `person`    | person name (from assignees, senders, presence, …)      |
| `group`     | group name, alias, or member                            |
| `area`      | area name                                               |
| `proposal`  | staged inbox proposal line and source                   |

`--type` limits the search to one or more entity types (repeat the flag or pass
a comma-separated list). `--limit` caps results per entity type.
`--fuzzy` uses the shared deterministic fuzzy matcher. It is useful for
human-entered names and titles, but exact searches are still preferable when
you are matching IDs, URLs, or values that must not be broadened.

## Item search

`search` stays within life.txt items and supports field-scoped matching,
regular expressions, and fuzzy text matching:

```console
$ lifetxt search life.txt roadmap
$ lifetxt search life.txt project:web --field project
$ lifetxt search life.txt "login|auth" --regex
$ lifetxt search life.txt Wrte_Report --fuzzy
```

`--regex` and `--fuzzy` are mutually exclusive. The TUI row filter is different:
it filters already-rendered rows by substring and is not the cross-entity
`find` view.

## MCP

AI clients use the read-only `global_search` tool with the same `term`, `types`,
`limit`, and `fuzzy` arguments. The result follows
`global-search-v1.schema.json`.
