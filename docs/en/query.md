# Query Language and Saved Views

lifetxt has one query language, shared by the CLI `query` command, saved views,
and the MCP `run_query` tool. A filter written once behaves identically on every
surface, and every query returns typed diagnostics for mistakes instead of
silently returning the wrong set.

## Grammar

A query is whitespace-separated terms. Values may be quoted.

| Term                     | Meaning                                             |
| ------------------------ | --------------------------------------------------- |
| `field:value`            | membership or detail equality                       |
| `field:a,b`              | OR of values within the field                       |
| `field=value`            | same as `:`                                         |
| `field<DATE` `field>DATE`| date comparison (`<`, `>`, `<=`, `>=`, `!=`)        |
| `progress<50%` `progress>=3/4` | [`progress:`](life_txt_format_spec.md#75-effort-keys) ratio comparison (`<`, `>`, `<=`, `>=`, `!=`) |
| `-tag:value`             | exclude (also `exclude_tag:value`)                  |
| `open`                   | only open workflow statuses                         |
| `text:"free text"`       | substring match on the title (bare words also work) |

Multiple different fields are ANDed together; multiple values of one field are
ORed.

### Fields

- **Membership**: `status`, `type`/`kind`, `project`, `tag`, `tag_all`, `user`,
  `person`, `owner`, `assignee`, `attendee`, `sender`, `recipient`, `team`
- **Dates**: `due`, `do`, `from`, `to`, `on`, `at`, `done`, `created`, `updated`
- **Progress** (ratio comparison): `progress`, e.g. `progress<50%` or
  `progress>=3/4` -- both percentage and fraction values are normalized to a
  ratio via the same [`progress:`](life_txt_format_spec.md#75-effort-keys)
  parser used by validation, so either representation compares correctly
  regardless of which one an item actually uses. An invalid `progress:`
  value on an item, or a missing `progress:` detail, never matches any
  `progress` comparison -- a missing value is not implicitly `0%`.
- **Details** (equality): `area`, `context`, `loc`, `priority`, and any known key
- **Custom** (equality, opt-in): any [generic `custom_fields`](config.md#generic-custom-fields)
  definition with `filterable: true`
- **Text**: `text` / `q`, or bare words

Unknown fields produce a `Q001` warning and are ignored; invalid dates produce a
`Q002` error; an unparseable `progress` comparison value produces a `Q005`
error.
Warnings are returned with the result set; errors stop the query. This is why a
misspelled field does not silently narrow your result to zero, while a malformed
date or progress comparison cannot pretend to be valid.

### Custom fields

A field declared under the top-level [`custom_fields`](config.md#generic-custom-fields)
configuration becomes a recognized `field:value` / `field=value` equality
query field, but only when its definition sets `filterable: true`:

```console
$ lifetxt query "energy:high"
$ lifetxt view run energetic-notes
```

A field left `filterable: false` (the default) is still validated metadata
on matching items, but querying it reports `Q001` exactly like an
undeclared key -- declaring a field for validation does not silently make
it queryable too. Numeric/date comparison operators (`<`, `>`, and so on)
are not supported for custom fields yet; only equality/membership matching
is. Saved views built on a filterable custom field run through this same
grammar with no separate implementation, so `view validate`/`view run`
behave identically to an ad-hoc query.

## CLI

```console
$ lifetxt query "open project:web tag:urgent due<2026-08-01"
$ lifetxt query "area:work" --sort due --limit 10 --format table
$ lifetxt query "status:done project:web" --format json
$ lifetxt query "open text:\"release plan\""
$ lifetxt query "progress<50%" --sort progress
```

`--sort progress` (and the same `sort`/`order` query parameters on `GET
/api/items`) orders items by their `progress:` ratio; an item with no
`progress:` detail, or an unparseable one, always sorts after every item
that has a valid value, regardless of `--order asc`/`desc` -- the same
never-implicitly-`0%` rule the `progress` query field itself uses.

Use `--explain` to inspect the parser's interpretation without returning
matching items. The default output is intended for people; add `--format json`
for a stable machine-readable envelope (`lifetxt-query-explain-v1`). Diagnostics
are included in the explanation, and an invalid query still exits with status 1.

```console
$ lifetxt query 'open project:research due<2026-10-01' --explain
$ lifetxt query 'open project:research due<2026-10-01' --explain --format json
```

## Saved views

Save common queries under `saved_views` in configuration:

```json
{
  "saved_views": {
    "web_open":  { "query": "open project:web", "sort": "due", "limit": 10 },
    "overdue":   { "query": "open due<2026-07-25" },
    "urgent":    "tag:urgent"
  }
}
```

A view is either an object (`query` plus optional `sort`, `order`, `limit`) or a
plain query string. Run and inspect them:

```console
$ lifetxt view list
$ lifetxt view show web_open
$ lifetxt view validate
$ lifetxt view run web_open --format table
```

Saved views are validated against `saved-view-v1.schema.json`; `view validate`
reports empty (`V001`) or malformed (`V002`) queries.
`view run` applies the saved query first, then optional sort, order, and limit.
That keeps one saved definition reusable across table, JSON, and MCP output.

## MCP

AI clients use `run_query`, `list_saved_views`, and `run_saved_view` — the same
grammar and the same results a person sees, including the query diagnostics.
