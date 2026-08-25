# Periodic Markdown reports

`lifetxt report` turns existing `share --format markdown` reporting into named,
repeatable profiles. The generated files are derived artifacts: `life.txt`
remains authoritative.

## Configure a report

Add a top-level `reports` object to `.lifetxt.json` (or another active config):

```json
{
  "paths": ["life.txt"],
  "defaults": {"timezone": "Asia/Tokyo"},
  "reports": {
    "weekly": {
      "period": "weekly",
      "title": "Weekly Review",
      "output": "~/Documents/Obsidian/Life/Weekly/{iso_year}-W{iso_week}.md",
      "mode": "replace",
      "frontmatter": true
    }
  }
}
```

Supported profile settings:

| Setting | Type | Default | Meaning |
| --- | --- | --- | --- |
| `period` | `daily|weekly|monthly` | required | Calendar range rendered by the report. Weeks are Monday through Sunday. |
| `output` | string | none | Markdown path template. Required by `report run`; relative paths resolve from the config file directory. |
| `title` | string | share default | Optional report title. |
| `project` | string | none | Optional project filter. |
| `type` | string | none | Optional item-type filter. |
| `tag` | string | none | Optional tag filter. |
| `open` | boolean | `false` | Include only unfinished workflow items when true. |
| `mode` | `replace|create|append` | `replace` | Generated-file write behavior. |
| `frontmatter` | boolean | `true` | Add generated-report metadata before the Markdown body. |

Unknown profile settings fail loudly when the profile is read. The generated
body reuses the existing `share --format markdown` renderer and passes concrete
`--after` / `--before` bounds, so the selected period controls the report
contents rather than only its heading.

Output templates support these placeholders:

- `{date}` — period start date (`YYYY-MM-DD`)
- `{year}` — four-digit year of the period start
- `{month}` — two-digit month
- `{iso_year}` — ISO week year
- `{iso_week}` — two-digit ISO week number

No format specifiers or arbitrary expressions are accepted in placeholders.

## Commands

List configured profiles without rendering or writing anything:

```sh
python -m lifetxt report list
```

Preview a report on stdout. Preview never writes the configured target:

```sh
python -m lifetxt report preview weekly
```

Generate the configured target:

```sh
python -m lifetxt report run weekly
```

`replace` atomically replaces the derived file. `create` refuses to overwrite an
existing target. `append` reads the existing file and atomically writes the old
content plus one complete generated report. Parent directories are created as
needed.

## Generated metadata

With `frontmatter: true`, output starts with metadata such as:

```yaml
---
generator: lifetxt
report_schema: lifetxt-report-v1
report: "weekly"
period: weekly
period_start: 2026-08-24
period_end: 2026-08-30
generated_at: "2026-08-25T18:05:00+09:00"
timezone: "Asia/Tokyo"
---
```

For `append`, later metadata blocks are Markdown separators inside the file, not
one document-level YAML frontmatter section. Prefer `replace` or `create` for
one-file-per-period Obsidian notes.

## Obsidian

Obsidian can read the generated Markdown directly. Point `output` into your
Vault, for example:

```json
{
  "period": "daily",
  "output": "~/Documents/MyVault/Life/Daily/{date}.md",
  "mode": "replace"
}
```

No Obsidian plugin or API is required. lifetxt writes a normal Markdown file;
Obsidian remains a replaceable view over that derived artifact.

## Notion-compatible export

A generated `.md` file is suitable for normal Markdown import into Notion. This
feature does **not** call the Notion API, create/upsert pages, or provide automatic
Notion synchronization. Those network-side effects are intentionally outside
this CLI-first report contract.

## Scheduling

lifetxt defines **what** a named report generates. The operating system decides
**when** to invoke it. No resident scheduler daemon is added.

For example, a weekly cron entry can invoke:

```cron
0 0 * * 1 cd /path/to/workspace && python -m lifetxt report run weekly
```

Equivalent automation can use systemd timers, Windows Task Scheduler, or
`launchd`. Run the same `report run NAME` command from the scheduler so manual
and scheduled output share one contract.

## Compatibility and migration

This is additive configuration. When `reports` is absent, existing lifetxt
behavior is unchanged. No `life.txt` grammar migration is required. To downgrade
to a version without report profiles, remove or ignore the `reports` section;
`life.txt` itself needs no conversion because report files are derived output.

Use `lifetxt config explain reports.weekly.period` (replace `weekly` with your
profile name) to inspect the registered configuration metadata.
