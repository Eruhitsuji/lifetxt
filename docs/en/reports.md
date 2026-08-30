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

## Report v2: composing existing aggregations (`sections`)

A profile that declares a `sections` array opts into **Report v2**, a
composition layer over lifetxt's existing deterministic domain aggregations
(`review`, `stats`, `agenda`, `command_center`, `portfolio`, `health`, and
more) instead of the `share --format markdown` delegation described above. A
v2 profile never reimplements what those aggregations mean; it only selects,
orders, and renders them.

```json
{
  "reports": {
    "weekly-review": {
      "period": "weekly",
      "output": "reports/{iso_year}-W{iso_week}.md",
      "compare": "previous",
      "sections": [
        {"type": "review"},
        {"type": "stats", "group": "daily"},
        {"type": "agenda", "range": "next-period"},
        {"type": "command-center", "horizon": 3},
        {"type": "project-health"},
        {"type": "next-actions"},
        {"type": "inbox"},
        {"type": "ticket-attention"},
        {"type": "health"}
      ]
    }
  }
}
```

Each section is `{"type": "<name>", ...options}`. `title` is an optional
override for the rendered heading. Available types:

| Type | Reuses | Notable options |
| --- | --- | --- |
| `review` | `lifetxt.review.build_review()` | `project` |
| `stats` | `lifetxt.stats.build_stats()` | `group` (`daily`/`weekly`/`monthly`) |
| `agenda` | `lifetxt.agenda.agenda_records()` | `range` (`period` default, `next-period`, `previous-period`) |
| `command-center` | `lifetxt.command_center.command_center()` | `horizon`, `next_actions_limit`, `inbox_limit`, `ticket_stale_after_days` |
| `project-health` | `lifetxt.projects.portfolio()` | `include_archived` |
| `next-actions` | the shared actionable-item definition | `limit` |
| `inbox` | Unified Inbox summary | `limit` |
| `ticket-attention` | the Command Center ticket-attention rule | `stale_after_days` |
| `health` | `lifetxt.health.build_health()` (the same rules `lifetxt health` uses) | `since_days`, `lookahead_days`, `ignore_codes`, `kinds` |

An unknown `type`, or an option a provider does not understand, fails loudly
when the profile is read -- before any rendering happens.

### Output format

```json
{"format": "markdown", "sections": [...]}
```

`format` is `markdown` (default), `json`, or `html`. All three render the
same already-built Report Model; none re-parses `life.txt` or re-derives a
section. Override it for one call with `--format`:

```sh
python -m lifetxt report preview weekly-review --format json
```

`--format` is only valid for a `sections` profile; using it on a v1 profile
is rejected.

### Historical periods (`--date`, `--previous`)

```sh
python -m lifetxt report preview weekly-review --date 2026-07-15
python -m lifetxt report run weekly-review --previous
```

`--date YYYY-MM-DD` generates the configured period containing that date.
`--previous` generates the immediately completed previous period relative to
today -- the form a scheduler should use right after a period rolls over, so
the freshly completed period is what gets rendered rather than the new one
already in progress. `--date` and `--previous` are mutually exclusive. Both
also apply to v1 profiles.

### Comparing against the previous period (`compare`)

```json
{"compare": "previous", "sections": [{"type": "stats"}]}
```

When set, every section is also computed for the immediately preceding
period, and a generic numeric diff (`{"current": ..., "previous": ...,
"delta": ...}` per matching numeric field) is attached as that section's
`compare` value. No section's own comparison semantics are hand-written; the
diff walks whatever the provider already returned.

### External-safe reports (`audience`)

```json
{
  "audience": "external",
  "sections": [{"type": "stats"}, {"type": "health"}]
}
```

`audience` is `private` (default) or `external`. `external` is deliberately
conservative: only aggregate-only section types (`stats`, `health`,
`project-health`) are allowed -- a profile using `review`, `agenda`,
`command-center`, `next-actions`, `inbox`, or `ticket-attention` under
`audience: external` is rejected when the profile is read. Every allowed
section's data is also redacted before rendering: any field that could carry
a verbatim title, path, excerpt, or other personal text is dropped (a
dropped list becomes a `<field>_count` instead), and the result is passed
through the same path/token redaction `remote_access.redact_remote_value()`
already applies elsewhere in lifetxt as defense in depth. This is not a
general redaction switch over the v1 `share` renderer -- it is a distinct,
narrower contract for reports meant to leave your private lifetxt
environment.

### Emailing a report (`email`, `report send`)

```json
{
  "email": {
    "to": ["me@example.com"],
    "subject": "lifetxt weekly report {period_start} - {period_end}",
    "smtp_host_env": "LIFETXT_SMTP_HOST",
    "smtp_user_env": "LIFETXT_SMTP_USER",
    "smtp_pass_env": "LIFETXT_SMTP_PASS"
  }
}
```

```sh
python -m lifetxt report send weekly-review
python -m lifetxt report send weekly-review --date 2026-07-15
python -m lifetxt report send weekly-review --dry-run
```

`email` works on both v1 and v2 profiles. `to` is required; `subject`
supports `{period_start}`, `{period_end}`, and `{report}` placeholders and
defaults to `lifetxt report: <name>`. SMTP host/username/password are read
from the named environment variables (defaulting to `LIFETXT_SMTP_HOST`/
`LIFETXT_SMTP_USER`/`LIFETXT_SMTP_PASS`) via STARTTLS, the same delivery
primitive `digest --format email` uses -- `report send` does not add a
second SMTP implementation. `--dry-run` prints what would be sent without
opening a connection or requiring the environment variables to be set.

`lifetxt digest` can also use a report profile as its message source instead
of the built-in review summary, reusing digest's existing file/email/Slack
delivery channels:

```sh
lifetxt digest --report weekly-review --format email --to me@example.com
lifetxt digest --report weekly-review --format file --path weekly.md
lifetxt digest --report weekly-review --date 2026-07-15 --format slack-webhook --url-env LIFETXT_SLACK_WEBHOOK
```

`--week`/`--month`/`--project` are ignored when `--report` is given; the
profile's own period and filters apply instead.

## Scheduling on Ubuntu Server

See [`docs/deployment/ubuntu-server.md`](../deployment/ubuntu-server.md) for
`server-init`'s opt-in `reporting` section (new/regenerated deployments,
generates a systemd oneshot + `Persistent=true` timer per job running
`report run <profile> --previous`) and `lifetxt server-report plan|install|
remove` (adds or removes one such job on an already-running deployment
without re-running `server-init`).

## Compatibility and migration

This is additive configuration. When `reports` is absent, existing lifetxt
behavior is unchanged. No `life.txt` grammar migration is required. To downgrade
to a version without report profiles, remove or ignore the `reports` section;
`life.txt` itself needs no conversion because report files are derived output.
A profile without `sections` keeps behaving exactly as the v1 section above
describes; adding `sections` is the only way to opt into Report v2.

Use `lifetxt config explain reports.weekly.period` (replace `weekly` with your
profile name) to inspect the registered configuration metadata.
