# Global Search

`find` は lifetxt が把握しているものを横断検索します。life.txt items と、そこから計算される projects、people、groups、areas、staged inbox proposals が対象です。results は entity type ごとに grouped され、matched field と short snippet を返します。benchmark で必要性が示されるまでは index を作らず直接 scan します。

item だけを field-scoped または regex で検索する場合は `search` を使います。`find` はより広い cross-entity view です。

`search` と `find` はどちらも opt-in fuzzy matching を support します。exact substring matches は常に先に rank され、fuzzy results は小さな typo や omission の fallback matches です。

## Usage

```console
$ lifetxt find web
$ lifetxt find alice --type person
$ lifetxt find example.com          # url: detail に match
$ lifetxt find roadmap              # item body に match
$ lifetxt find engineering --type group
$ lifetxt find widgets --json
$ lifetxt find Wrte_Report --fuzzy
```

## What it searches

| Entity | Matches on |
| --- | --- |
| `item` | title、body、任意の detail value (project、url、tag など) |
| `project` | name、display name、owner、area |
| `person` | assignees、senders、presence などから得た person name |
| `group` | group name、alias、member |
| `area` | area name |
| `proposal` | staged inbox proposal line と source |

`--type` は検索対象を 1 つ以上の entity type に制限します。flag を繰り返すか comma-separated list を渡せます。`--limit` は entity type ごとの result count を制限します。

`--fuzzy` は shared deterministic fuzzy matcher を使います。human-entered names や titles には便利ですが、IDs、URLs、正確に一致すべき values では exact search を優先してください。

## Item search

`search` は life.txt items 内に留まり、field-scoped matching、regular expressions、fuzzy text matching を support します。

```console
$ lifetxt search life.txt roadmap
$ lifetxt search life.txt project:web --field project
$ lifetxt search life.txt "login|auth" --regex
$ lifetxt search life.txt Wrte_Report --fuzzy
```

`--regex` と `--fuzzy` は同時に使えません。TUI row filter は別物です。すでに render 済みの rows を substring filter するだけで、cross-entity `find` view ではありません。

## MCP

AI clients は read-only `global_search` tool を使います。arguments は `term`、`types`、`limit`、`fuzzy` です。result は `global-search-v1.schema.json` に従います。
