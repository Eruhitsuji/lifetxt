# Global Search

`find` searches across everything lifetxt knows — life.txt items and the derived
entities it computes: projects, people, groups, areas, and staged inbox
proposals. Results are grouped by entity type, each with the field that matched
and a short snippet. It scans directly; no index is built until benchmarks
justify one.

For field-scoped or regex search within items only, use `search`. `find` is the
wider, cross-entity view.

## Usage

```console
$ lifetxt find web
$ lifetxt find alice --type person
$ lifetxt find example.com          # matches a url: detail
$ lifetxt find roadmap              # matches an item body
$ lifetxt find engineering --type group
$ lifetxt find widgets --json
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

## MCP

AI clients use the read-only `global_search` tool with the same `term`, `types`,
and `limit` arguments. The result follows `global-search-v1.schema.json`.
