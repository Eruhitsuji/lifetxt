# lifetxt TODO / Roadmap

Last updated: 2026-07-07 (updated x56)

This roadmap tracks remaining work after the current prototype updates.
Completed prototype-only items are removed; items below are implementation,
validation, documentation, or design work that still matters.

Priority guide:

- `P0`: Stabilize features that are already implemented and likely to break in real use.
- `P1`: Implement or refine core features that affect the format, CLI, API, or daily workflow.
- `P2`: Improve usability, documentation, packaging, and long-term maintainability.
- `Deferred`: Useful ideas that should not block the next practical release.

---

## P0: Stabilization

Items in this section are already implemented but have not been verified in
real environments. Each item must be tested manually before the next release.

- [ ] Verify `tui` in real terminals across WSL, Windows Terminal, and native
  macOS/Linux: confirm Vim-like keymap, curses colors, and auto-reload with a
  human at a real TTY. Automated regression tests now cover the fallback
  logic itself (`textual` missing -> curses/plain, `curses` missing -> plain
  text, `cmd_tui` never raises) in `tests/test_cui_extensions.py`
  (`TuiFallbackTests`), so what remains is interactive verification, not the
  fallback code path.

- [ ] Verify `lifetxt fzf` and `inbox --fzf` with actual `fzf` and `peco`
  binaries on both Windows PowerShell and Unix-like shells: confirm `done`,
  `delete`, and `edit` (with `$EDITOR`) actions end-to-end. The preview
  command quoting bug for native Windows `cmd.exe` (vs. git-bash/WSL/POSIX
  shells, which set `$SHELL`) has been fixed in `fzf_helper._preview_command`
  and is regression-tested (`FzfPreviewQuotingTests`), and the
  no-selector-installed error path is also regression-tested
  (`FzfNotInstalledTests`). What remains is verifying the actual selector UI
  and its preview rendering with real `fzf`/`peco` installed.

---

## P1: Format Semantics

Design decisions that affect the file format, parser, and all downstream tools.
Resolve these before implementing features that depend on them.

- [ ] Finalize timezone-aware datetime round-trip rules: specify how naive
  datetimes (no timezone suffix) are stored and interpreted, how
  `#! timezone:` and config `defaults.timezone` affect display and filtering,
  and how `to-json`, `to-csv`, and `from-json` preserve or normalize timezone
  information without silent data loss.

- [ ] Decide which item types should recommend `elapsed:`: currently only
  task-like records use it; determine whether `E` events, `S` status records,
  and `J` journal entries should also record elapsed time, and add
  type-specific guidance to the spec.

- [ ] Finalize occurrence materialization rules for life.txt output files:
  CLI JSON/JSONL/CSV occurrence exports and Web agenda occurrence metadata are
  implemented, but the format still needs explicit guidance for writing
  generated occurrences back to `.life.txt` or `.generated/*.life.txt` files
  without confusing them with stored source items.

---

## P1: Configuration

Settings that affect how values are resolved across CLI, config file, and
file-level metadata. These must be consistent across all commands.

- [ ] Extend `#!` directive wiring to `timezone`: apply `timezone` directive
  to datetime display (agenda, summary, stats) and filtering. Currently `self`
  and `project` are wired for `quick` and `assist`; `timezone` remains unread.
  This needs care: `timeutil.parse_datetime` currently converts any
  timezone-suffixed value to naive system-local time on parse, so wiring a
  per-file `timezone` directive means deciding how it interacts with that
  existing conversion without silently changing already-correct displayed
  times (see the related P1 Format Semantics item below).

---

## P1: CLI — Core Improvements

Improvements to existing commands that affect daily workflow.

- [ ] Verify `tui` behavior in narrow terminals with a real curses TTY.
  `filter` now has a `--width N` flag and a `--format table` output (bordered
  table, or a compact one-line form below 80 columns, matching `agenda` and
  `stats`); this part is done and documented in CLI guide section 6.

- [ ] Add `--last-week` and `--last-month` convenience flags to `review` so
  the CLI matches the Web Review view's range presets without manual
  `--from`/`--to` date math. Implement the presets in
  `review.resolve_review_range` so `GET /api/review` and the MCP `get_review`
  tool can accept the same selector (e.g. `range=last-week`) instead of the
  browser computing dates client-side as it does today.

- [ ] Keep CLI help synchronized with docs: after every change to `tui`,
  `fzf`, `timer`, `stats`, `git-hook`, and `completion`, update
  `docs/en/cli.md`, `docs/ja/cli.md`, and shell completion scripts in the
  same commit.

---

## P1: CLI — New Commands (Onboarding & Safety)

New commands that reduce the initial setup cost and protect against data loss.
Implement before other new commands because they lower the barrier for all
subsequent use.

---

## P1: CLI — New Commands (Daily Operations)

New commands for the most frequent daily actions. Each delegates to an
existing command internally to reuse validation and atomic write behavior.

---

## P1: CLI — New Commands (Review & Health)

New commands that close the feedback loop: surfacing what is happening,
what is overdue, and what the week looked like.

- [ ] Extend `inbox --fzf` from selection-only output to optional follow-up
  actions (`show`, `assign`, `done`, `edit`) after real `fzf`/`peco`
  verification confirms quoting and selector behavior.

---

## P1: CLI — Archive

Commands and behaviors for moving old items out of active files.

---

## P1: CLI — Visualization

CLI-native charts without external dependencies.

---

## P1: Web API / Browser UI

### API Stability & Security

- [ ] Expand `docs/en/web.md` and `docs/ja/web.md` with full request and
  response examples for the remaining less-common routes, especially Git
  integration endpoints. Elapsed chart range examples are now documented.

### Statistics & Charts (Web UI)

- [ ] Verify weekly/monthly chart rendering in the browser: the `/api/chart/habits`
  now returns raw counts per bucket; confirm Chart.js renders bars correctly
  and the Y-axis label is meaningful (e.g., "completions / week").

### Record Display (Web UI)

- [ ] Preserve original line position when the Web UI Undo restores a deleted
  item: undo currently re-appends the raw line at the end of the writable file
  via `POST /api/items/raw`, so ordering and surrounding comments are not
  restored. Consider a dedicated restore endpoint that remembers the original
  line number.

### Dependency & Reference Graph (Web UI & CLI)

- [ ] Add a `force` (physics-based) layout preset to the browser graph panel:
  `ring`, `lr` (layered left-to-right), and `tb` (layered top-to-bottom) are
  implemented with per-user persistence and SVG/PNG export; a force layout
  would help non-hierarchical graphs but needs an iterative simulation.

- [ ] Add `links` tests for Mermaid/DOT: cross-file node references, special
  characters in IDs/titles (quotes, spaces), and `--id` + `--direction` scoping
  with mermaid/dot output (verify only reachable subgraph is rendered).

### Git Integration (Web API)

### Design System & App Shell (Web UI) — New

- [ ] Extract the Web UI design tokens (`--accent`, semantic soft colors,
  radii, shadows, spacing) into a documented theming hook: allow a config key
  such as `web.theme.accent` to override the accent color without editing
  `webapp.py`, and document the token list for custom deployments.

- [ ] Audit the redesigned UI for WCAG AA contrast in both themes (badge
  soft-background/foreground pairs, muted text on `--panel-2`, kiosk header)
  and adjust token values where they fall below 4.5:1 for body-size text.

- [ ] Consider persisting UI preferences (density, graph layout, dark mode)
  server-side per user instead of `localStorage`, so settings follow the user
  across browsers. Density toggle, theme, and graph layout currently persist
  locally; the active view is part of the URL by design.

### Views: Dashboard, Focus & Review (Web UI)

The Review view is now implemented: a read-only tab backed by the new
`GET /api/review` endpoint (shared `lifetxt/review.py` aggregation, also used
by the CLI `review` command and the MCP `get_review` tool) with
This week / Last week / This month / Last month presets, KPI tiles, a
completed-task list, habit completion bars, journal entries with mood trend,
and elapsed-by-project totals. The Focus view gained a quick-add input
(appends `due:` today through `POST /api/items/raw`), a "Today's schedule"
group for due-today `E` events, `at:`/`on:`-today Reminders, and an
"Anytime reminders" group for undated `R` items. Remaining and follow-up
work:

- [ ] Make Dashboard cards configurable: a config key such as
  `web.dashboard.cards` choosing which cards render (today, needs-attention,
  completions chart, projects) and their order, plus per-card limits. The
  fixed four-card layout with KPI tiles is implemented.

- [ ] Make Review view completed-task rows clickable: entries returned by
  `GET /api/review` include the item `id`, so a click should resolve the
  record via `/api/items/id/{id}` and open the detail modal; the view is
  currently display-only.

- [ ] Add a project filter and a custom from/to date picker to the Review
  view: `GET /api/review` already accepts `project`, `from`, and `to`, but
  the UI exposes only the four range presets.

- [ ] Add an export/copy action to the Review view that produces the same
  Markdown as `review --format markdown` for pasting into chat or a weekly
  report; consider a shared server-side renderer so `digest` can reuse it.

- [ ] Compute real habit streaks (longest and current consecutive-day runs)
  in `lifetxt/review.py` from per-day `done:` dates, and show them in the
  Review view's Habits card next to the completion-rate bars; the report
  currently aggregates done/open counts per habit title only.

- [ ] Deprecate the legacy `?workspace=` URL alias after one release: it now
  maps onto `view=` (and `workspace=new` opens the editor modal); emit a
  console warning first, then drop the mapping and the doc row.

### Views: Team, Timeline & Presence (Web UI)

Implemented 2026-07-07: colored presence indicators (state → dot/badge color
mapping, with the state text always shown so color is never the only
signal), a redesigned Status view using person cards plus an
Active-only / All-latest toggle, a Team presence board view combining latest
status records, per-person open messages, and assignee workload counts, a
Timeline view (chronological agenda board with a red now line, per-type rail
nodes, day headers, dimmed past rows, and Today / Next 24h / Week presets),
and a fullscreen toggle (header ⛶ button, `f` key, command palette).
`GET /api/status?active=false` was also fixed to actually include ended
records. Follow-up work:

- [ ] Audit untyped boolean query parameters across all FastAPI routes:
  with untyped defaults FastAPI 0.83 passes raw query strings through, so
  `?open_only=false`, `?blocked=false`, and similar are truthy strings and
  behave as `true`. `/api/status?active=false` is fixed and
  regression-tested; apply the same string-aware parsing (or typed `bool`
  parameters) to `/api/items`, `/api/messages`, `/api/agenda`, and the
  chart routes, with a test per route. (P1 — correctness.)

- [ ] Make presence state colors configurable: a config key
  `web.presence.states` mapping custom state names onto the built-in color
  classes (green/red/violet/amber/gray), merged over the default regex
  rules, so teams with their own vocabulary ("onsite", "wfh") get correct
  dots without code changes. (P2)

- [ ] Persist the Timeline range in the URL (`range=today|24h|week`) like
  other view state so wall displays can bookmark
  `?view=timeline&range=week&refresh=120`, and re-render the now line every
  minute on auto-refreshing screens instead of only on reload. (P2)

- [ ] Order and pin Team board cards: sort by the config `users` order or a
  `web.team.pin` list (pinned people first, others alphabetical), and add a
  per-person click-through from the card to `?view=&assignee=NAME`. (P2)

### Context Menu & Dark Mode (Web UI) — New

### Stats & Charts (Web UI) — New

### Item Selection (Web UI) — New

- [ ] Add a multi-level undo history to the Web UI: the undo toast currently
  keeps only the most recent action; a small history (last 5 actions with
  labels) surfaced from the command palette would make bulk edits safer.

### Detail Modal Improvements (Web UI) — New

- [ ] Add an inline timer control to the detail modal for task-like items: start /
  stop buttons that update `elapsed:` through the existing item update
  endpoint, reusing the CLI `timer` duration math, so the est/elapsed progress
  bar can be driven entirely from the browser.

### Agenda & Notifications (Web UI) — New

---

## P1: Multiple Files / Sync / External Tools

- [ ] Document the recommended directory layout for a typical user:
  `life.txt` (hand-written), `.generated/` (ICS sync output), `archive/`
  (archived items), `.cache/lifetxt/` (undo stack, backup, notification
  state). Explain which directories belong in `.gitignore`.

- [ ] Define integration boundaries for calendar sources beyond ICS and for
  presence/message tools (Teams, Discord, Slack): specify which fields are
  imported, which are exported, and which are read-only in life.txt because
  they are managed by the external tool.

- [ ] Define conflict policy for `sync-ics --merge-existing`: decide whether
  local edits inside generated records should be overwritten, preserved by
  selected keys, or reported as conflicts before replacement. Current behavior
  replaces matching UID-backed records and preserves comments/unmatched lines.

- [ ] Add usage example for `.pre-commit-hooks.yaml` to docs: show the
  `.pre-commit-config.yaml` snippet that references the `lifetxt-check` hook,
  and document which file patterns are matched by default.

- [ ] Document that secret URLs and tokens (iCalendar feed URLs, API tokens)
  must not be stored in life.txt content. Reference the `--url-env` and
  `--key-env` patterns as the correct approach.

---

## P1: Validation

Diagnostics added to `check` and `health` that catch common mistakes.

---

## Use-Case Backlog (added 2026-07-07)

Concrete feature proposals derived from walking the whole system (format,
CLI, Web UI/API, MCP, editors) as different kinds of users. Each item names
the commands, flags, config keys, or endpoints it would introduce so it can
be promoted into the P1/P2 sections above when picked up. The suggested
priority is tagged per item; nothing here blocks the next release by itself.

### Quick capture & mobile (any user away from a desktop)

- [ ] (P1) Make the Web UI installable as a PWA: have `serve` expose a
  `manifest.json` and a minimal service worker behind config
  `web.pwa.enable` (default false) so phones can pin the UI to the home
  screen. Cache only the app shell (the single HTML page); all `/api/*`
  traffic stays online so the read/write model is unchanged.

- [ ] (P2) Register the PWA as a Web Share Target so text shared from other
  mobile apps opens the record editor modal prefilled as an inbox item
  (`[ ] N <shared text>` with `tag:inbox`), writing through the existing
  `POST /api/items/raw`. Depends on the PWA item above.

- [ ] (P1) Add `lifetxt capture` for zero-friction terminal capture:
  `echo "buy milk" | lifetxt capture --stdin` and `capture --clipboard`
  append `[ ] T TITLE captured:NOW` (type overridable with `--type N`),
  delegating to the same validation and atomic-write path as `quick` so
  nothing new can corrupt the file.

### Students (classes, assignments, semester rhythm)

- [ ] (P2) Add `import-ics --preset university`: map recurring lecture
  VEVENTs to `E` items with `repeat:weekly` + `until:SEMESTER_END` and a
  `project:` derived from the course-code prefix of the summary, so a
  timetable export becomes a one-command semester setup.

- [ ] (P2) Show days-remaining countdowns: `agenda --countdown` adds a
  `D-n` column computed from `due:`/`to:`, and the Web Dashboard "Today"
  card shows a days-left badge for items due within
  `web.dashboard.due_soon_days` (default 7).

### Freelancers (billable time)

- [ ] (P1) Add `lifetxt invoice`: aggregate `elapsed:` per project for a
  billing period — `invoice --project clientA --month 2026-06 --rate 8000
  --currency JPY --round 15m --format markdown|csv`. Reuse the
  `review`/`stats` elapsed aggregation; `--round` rounds each item up to
  the billing increment before summing; per-project default rates come from
  config `billing.rates.{project}`.

### Small teams (shared file over git)

- [ ] (P1) Add `lifetxt standup`: print "done yesterday / planned today /
  blocked" for `--user NAME` (default config `user.name`) derived from
  `done:` dates, `due:` today, and open blockers; `--format
  text|markdown|slack`, where `slack` reuses the `digest` webhook transport
  and `--url-env` pattern.

- [ ] (P2) Add a per-person workload summary to the CLI and API: `who
  --workload` and `/api/status?workload=true` appending open / due-today /
  overdue / blocked counts per assignee. The Web Team view now computes
  open/overdue per assignee client-side; a server-side summary would let
  the CLI, MCP clients, and kiosks reuse the same numbers.

- [ ] (P2) Ship a built-in "mine" preset: `?preset=mine` resolves to
  `assignee:<config user.name>&open_only=true` without requiring a
  `views.mine` config entry, and the Items toolbar shows a "My items" chip
  when `user.name` is configured.

### GTD practitioners (inbox → next actions)

- [ ] (P1) Promote `context:` to a first-class filter: accept `--context
  @home` on `filter`/`agenda` (and `next` below), add a `context=` URL/API
  parameter, prompt for context in `inbox --process` alongside
  project/due/assignee, and Tab-complete known context values from loaded
  files.

- [ ] (P1) Add `lifetxt next`: show the top N actionable tasks — open, not
  blocked, not `[?]` — sorted by priority, then due, then age:
  `next --context @errands --project home --limit 3`. Implement as a
  curated wrapper over `filter` so all existing filters keep working.

- [ ] (P2) Add `review --someday`: list `[?]` items untouched for longer
  than `--older-than 30d` (by `updated:`/`created:`) so someday/maybe items
  get re-decided during the weekly review; later surface the same list as
  an optional card in the Web Review view.

### Habit builders & journalers

- [ ] (P1) Add `lifetxt habit today`: materialize today's habit checkboxes
  from `H` items with `repeat:` into the writable file, idempotent per
  habit+date through a generated `id:` (re-running never duplicates);
  `--dry-run` previews. A git hook, cron job, or Task Scheduler entry can
  run it each morning so daily habits become checkable items automatically.

- [ ] (P2) Add journal prompts: `quick --journal` opens `$EDITOR` prefilled
  from config `journal.prompt` (e.g. three reflection questions) and writes
  a `J` item with `on:today` and a multiline body; the Web editor modal
  gets a "Journal" shortcut that prefills the same prompt text.

### Care & family coordination

- [ ] (P2) Extend notifications to acknowledgeable recurring reminders:
  notification records currently cover type `M` messages only. Let `R`
  items with `repeat:` plus `notify_at:`/`require_ack:true` keep notifying
  until an `ack:` is written (reusing the message Ack/Snooze plumbing), with
  optional re-notification after `notifications.escalate_after` (e.g.
  `30m`) — medication and pickup reminders on a shared screen.

- [ ] (P2) Document a "family board" kiosk recipe in `docs/{en,ja}/web.md`:
  a worked `views.family` preset combining `mode=kiosk`, `kiosk_filter`,
  `kiosk_title`, `refresh`, and `theme`, plus a wall-tablet setup checklist
  (autostart URL, notification permission, preventing sleep).

### Accessibility & inclusive use

- [ ] (P1) Web UI accessibility pass: `role=tablist`/`tab` semantics with
  arrow-key movement on the view bar, `aria-live=polite` on the toast and
  notification updates, a skip-to-content link before the header, and a
  visible-focus audit of all interactive elements. Extends the existing
  WCAG AA contrast item in the Design System section.

- [ ] (P2) Honor `prefers-reduced-motion`: disable kiosk auto-scroll,
  skeleton shimmer, and modal transitions when the media query matches,
  with a `web.reduce_motion: true` config override for kiosk deployments.

- [ ] (P2) Add a high-contrast theme: `?theme=high-contrast` plus a
  `web.theme.high_contrast` token set layered on the planned theming hook,
  so low-vision users get a supported mode instead of browser extensions.

### Non-English users

- [ ] (P2) Add a Web UI label dictionary: config `web.language: en|ja` and
  a `?lang=` parameter switching the static chrome strings (view names,
  buttons, empty states, help modal) from a small dictionary embedded in
  `webapp.py`; item content is user data and is never translated. Start
  with Japanese since `docs/ja` already exists.

### First-run & evaluation

- [ ] (P1) Add `lifetxt demo`: start `serve` against generated sample data
  in a temp directory — `demo --persona student|team|freelancer` seeds
  persona-flavored items (courses, a sprint with assignees, client
  projects with elapsed time) and shows a "Demo data — nothing is saved to
  your files" banner, so the Web UI can be evaluated with one command and
  zero risk.

- [ ] (P2) Add a guided empty state to the Web UI: when zero items load,
  replace the empty table with three actions — "Add your first task"
  (opens the editor prefilled with a commented example), "Import"
  (ICS / Todoist / GitHub doc links), and "Open docs".

### Long-horizon users (years of data)

- [ ] (P2) Add `review --year 2026`: a year selector in
  `review.resolve_review_range` plus per-month subtotal rows in the report
  (tasks completed, habit rate, journal count, elapsed), with
  `--format html` producing a shareable year-in-review page; expose the
  same selector through `GET /api/review` and MCP `get_review`.

- [ ] (P2) Add scheduled auto-archive: config
  `archive.auto: {age: "180d", target: "archive/{year}.life.txt"}` applied
  by `cleanup --auto` (documented for cron and Windows Task Scheduler),
  reusing `archive`'s orphan-children handling and `--dry-run` semantics.

### Developers

- [ ] (P2) Add `lifetxt todo-scan`: import `TODO`/`FIXME` source comments
  as tasks — `todo-scan src/ --project myrepo --tag code` generates stable
  IDs from a path+text hash so re-runs update instead of duplicating, and
  `--prune` closes tasks whose source comment has disappeared.

---

## P2: CLI — Power User Commands

Additional commands for users who want deeper inspection, style enforcement,
long-term file management, and sharing. Implement after P1 commands are stable.

- [ ] Extend `template` beyond config-defined templates: consider also
  supporting a `templates.life.txt` file using a reserved `TEMPLATE` type
  marker as an alternative to config JSON, for teams that prefer templates to
  live alongside their life.txt files under version control. The config-based
  `template list` / `template apply NAME --append FILE` (with `{today}`,
  `{next_monday}`, `{next_week}` placeholders resolved at apply time) is
  implemented; see CLI guide section 18.

---

## P2: Editor Support

- [ ] Package VS Code grammar and snippets as a proper extension installable
  from the Marketplace or via `code --install-extension`, not by copying files
  manually.

- [ ] Keep editor file-association documentation current for `life.txt`,
  `*.life.txt`, and `*_life.txt` in `docs/en/editor.md` and
  `docs/ja/editor.md`.

- [ ] Generate VS Code editor snippet key lists directly from
  `lifetxt/model.py` (`RECOMMENDED_KEYS_BY_TYPE`, `KNOWN_KEYS`, status/type
  aliases) to prevent drift between the editor extension and the spec.
  `lifetxt/completion.py` (shell Tab-completion for bash/zsh/fish) already
  derives its `--type`/`--status` value lists and detail-key flag list from
  `lifetxt/model.py` and its `COMMANDS` tuple has been brought up to date
  with every current subcommand; only the VS Code snippet side remains.

- [ ] Add highlight snapshot tests for every grammar token: title, status,
  type, detail key, quoted value, body continuation (`|`), line continuation
  (`\`), `#!` directive, and `enc:` encrypted value prefix. Run these in CI
  to catch grammar regressions.

- [ ] Add editor support for `#!` metadata directive lines: highlight
  distinctly from ordinary `#` comment lines. Add snippets for common
  directive combinations (`self` + `timezone` + `project`).

- [ ] Add editor support for encrypted field values (`enc:` prefix): display
  with a distinct color and a tooltip indicating the value is encrypted.

- [ ] Add snippets for: task with timer fields (`est:`, `elapsed:`), event
  with attendees, status record (self), message with notification, journal
  entry with mood, linked subtask with `parent:` and `depends_on:`, and
  template record.

---

## P2: Documentation / Examples

- [ ] Resolve documentation synchronization policy: decide which of `readme.md`,
  `docs/en/readme.md`, `docs/ja/readme.md`, and `life_txt_format_spec.md` is
  the authoritative source for each topic, and document the policy so
  contributors know where to make changes.

- [ ] Add worked examples for: `timer` (start, pause, stop, summary),
  `stats` (weekly grouping), `tui` (keymap cheatsheet), `fzf` (preview and
  actions), `git-hook` (install and commit-msg), `completion` (bash/zsh/fish
  install).

- [ ] Add recommended workflow docs with step-by-step instructions for:
  daily use (`quick` → `inbox` → `done` → `summary`), team status sharing,
  message notifications, calendar sync (`sync-ics` + `agenda`), weekly review
  (`review` → LLM → `template apply`), and periodic archiving.

- [ ] Add migration notes for every breaking format change: `S`, `M`, `J`
  type additions, multiline body (`|`), hierarchy and `parent:`, CSV column
  schema, `elapsed:` normalization, Markdown subset, and RRULE storage.
  Include the `migrate` command invocation for each change once implemented.

- [ ] Add screenshots or terminal captures for: Web UI agenda view, `tui`
  dashboard, `stats` weekly output, `plot` terminal chart, and `doctor`
  diagnostic output. Include in both English and Japanese docs.

- [ ] Generate a diagnostic code catalog from parser and validator definitions:
  each code (E0xx, W2xx, W3xx, W4xx) must have a name, description, example
  triggering input, and resolution hint. Use this catalog as the source for
  CLI `--help`, shell completion, and the docs diagnostic reference.

- [ ] Document recommended file-splitting strategies (not enforced
  constraints): one file per editor/author, auto-generated files in
  `.generated/`, archives in `archive/`, and periodic archiving schedule.
  Clarify that the tool enforces nothing; these are operational recommendations.

- [ ] Document `#!` metadata directive placement rules in the format spec:
  the parser (`parser.py`'s `parse_directives`) stops scanning for
  directives at the first non-directive, non-blank line, so directives must
  appear contiguously before the first item — this constraint is not
  documented anywhere yet. The four-level resolution order with a worked
  side-by-side example (CLI flag vs. config JSON vs. `#!` directive vs.
  built-in default) is now documented in CLI guide section 12.1.

- [ ] Document `archive` command and workflow: all `--orphan-children` modes
  with before/after examples, `--block-on-external-refs` for cross-file
  safety, structure-preserving comment behavior, and when to use `--dry-run`.

- [ ] Document W219 resolution: explain the three resolution paths (close
  children manually, `archive --orphan-children adopt`, `archive
  --orphan-children promote`) and when `--ignore W219` is appropriate.

- [ ] Document `plot`: chart types, filter options, terminal rendering
  behavior, enabling SVG/PNG output, and piping text output to a pager.

- [ ] Document `undo` and `backup.auto`: differences between the two safety
  mechanisms, recommended config for users without Git, and step-by-step
  recovery from an accidental write.

- [ ] Add `docs/en/ai-integration.md` and `docs/ja/ai-integration.md`:
  expand beyond the basic MCP setup already documented in README/CLI/Web docs
  with client-specific configuration examples, CLI pipe patterns (`to-json |
  llm "..."`), example prompts for `review --format json` → LLM weekly review,
  local LLM (Ollama) setup for privacy-sensitive files, and a GitHub Actions
  workflow for automated AI summaries on push. Include annotated examples
  showing what life.txt data looks like from the AI's perspective.

- [ ] Add full command docs and workflow examples to `docs/en/cli.md` and
  `docs/ja/cli.md` for: `quick`, `done`, `undo`, `assign`, `summary`,
  `review`, `health`, `inbox`, `cleanup`, `archive`, `plot`, `search`, `lint`,
  `diff`, `snapshot`, `migrate`, `who`. All of these (plus every other
  subcommand) now have a one-line entry in the section 1 command-overview
  table, but only `init`, `doctor`, `encrypt`, `decrypt`, `share`, `digest`,
  and `template` have a dedicated worked-example section (sections 16-18).

- [ ] Expand `docs/en/web.md` and `docs/ja/web.md` with worked examples for:
  statistics dashboard usage, chart panel workflows, item creation/editing,
  Git integration endpoints and security model, and the `quick-add` shortcut.
  Also document the newer UI affordances: command palette (Ctrl+K), undo
  toast, group-by, keyboard list navigation (j/k/x/Enter), inline status
  cycling, item export, graph layout presets and SVG/PNG export, detail modal due
  quick-postpone, est/elapsed progress bar, and the agenda blocked filter.
  The redesigned app shell also needs a short section: header workspace view buttons,
  density toggle, `?theme=` URL parameter, and the print stylesheet.
  The REST table (including `/api/blockers`, `/api/review`, and
  `agenda?blocked=`), parse endpoint, graph panel, kiosk parameters, message
  thread basics, the Review view, the Focus quick-add, the Team and Timeline
  views, presence indicators, and the fullscreen toggle are now documented.

- [ ] Document the dependency graph feature end-to-end: explain the
  `links --format mermaid` and `links --format dot` CLI outputs, the
  `/api/graph` endpoint, the browser GUI graph panel, and when to use each.
  Include a worked example showing how to trace a blocked task back to its
  root blocker using both the CLI and the GUI.

- [ ] Consider generating CLI reference pages from `argparse` definitions to
  eliminate drift between `--help` output and the Markdown docs.

---

## P2: Tests / CI / Release

- [ ] Add CI pipeline: unit tests, compile checks, and example file
  validation on every push. Run on Python 3.10, 3.11, and 3.12 on Ubuntu,
  Windows, and macOS.

- [ ] Add a lightweight smoke-test runner for release checks: execute key CLI
  smoke tests (including timer state-file and cross-platform path tests)
  without running the full unittest suite.

- [ ] Add snapshot tests for all important human-readable CLI output so
  unintended formatting changes are caught automatically.

- [ ] Add sync tests comparing `RECOMMENDED_KEYS_BY_TYPE` in
  `lifetxt/model.py` with the type-specific recommended key lists in the
  English and Japanese format specs.

- [ ] Add cross-platform tests: paths with spaces, glob expansion, Windows
  line endings (`\r\n`), and shell completion output on bash, zsh, and fish.

- [ ] Add glob input tests for `*.life.txt`, `*_life.txt`, and
  `projects/**/*.life.txt` across all file-reading commands.

- [ ] Add parser edge-case tests: nested quotes, invalid `|` continuation
  variants, indentation with mixed spaces and tabs, and same-file
  duplicate-ID edge cases. (Unicode, emoji, CRLF, multi-value already covered.)

- [ ] Add canonical hierarchy edge-case tests: `from-jsonl --canonical`,
  `from-csv --canonical`, custom `ids.key`, a parent without an ID, and items
  that already have explicit `parent:` details.

- [ ] Add recurrence tests: occurrence expansion for all five simple repeat
  values, `interval:` / `until:` / `count:` edge cases, remaining occurrence
  export shapes, and long-range expansion performance (10 years of daily
  recurrence must complete under 500 ms).

- [ ] Add real-export fixture tests for `import-ics --preset todoist` and
  `--preset github`: cover multiple Todoist CSV dialects, GitHub search API
  result objects, missing optional fields, labels with commas, and closed
  issues without `closed_at`.

- [ ] Add duration normalization tests (W222): `1h00m` simplification, elapsed
  accumulation across multiple items in the same project.

- [ ] Add `#!` directive wiring tests for `timezone`: verify datetime display
  is affected once timezone wiring is implemented.

- [ ] Add `quick` tests: `write_file` config fallback (no `--append`).

- [ ] Add Markdown rendering regression tests: CLI HTML output snapshot and
  Web UI Markdown preview snapshot, run in CI to prevent the table-rendering
  bug from reappearing.

- [ ] Add large-file performance tests: parsing, filtering, and duplicate-ID
  detection on a 50,000-line file must each complete under 5 seconds.

- [ ] Add CI job with optional web dependencies installed and run FastAPI
  test-client coverage for all `/api/*` routes. Local tests now include
  TestClient cases for parse, generated/read-only, mood chart, graph, and
  message threads, but they skip when `fastapi` is not installed.

- [ ] Add browser-level Web UI smoke tests with Playwright or an equivalent
  driver: raw import live parse preview, detail modal message replies, occurrence
  badges, kiosk change highlighting, explicit ref-link scroll fallback, and
  search highlighting in detail/body previews. Newly added interactive
  features also need DOM-level coverage: command palette (Ctrl+K) matching and
  execution, undo toast (status/delete restore), j/k/x/Enter keyboard
  navigation, inline status-badge cycling, group-by section headers, item
  CSV/JSON/Markdown export, graph layout switching plus SVG/PNG download, the
  detail modal due quick-postpone buttons, and the agenda blocked-filter cycle.
  The 2026-07 single-content router redesign added more surfaces to cover:
  the ten-view tab bar (each view rendering exactly one page section),
  Dashboard KPI tiles and their click-through navigation, Focus one-click
  done with undo, the Focus quick-add input (Enter submits, quoted titles
  with spaces, list reloads), the Focus "Today's schedule" and "Anytime
  reminders" groups, the Review view (range preset switching, KPI tiles,
  habit bars, mood pills, empty states per card), the Team presence board
  (dot/badge state colors, message click-through, workload pills), the
  Timeline view (now-line placement, range presets, all-day rows, day
  headers), the Status view active-toggle, the fullscreen toggle
  (fullscreenchange icon swap), the record editor modal
  (open via ＋ New / `n` /
  `?workspace=new`, close on save), legacy `?workspace=` alias mapping,
  density toggle persistence, skeleton-loading rows, contextual empty states,
  the back-to-top button, `?theme=dark|light` forcing, command-palette fuzzy
  matching and "Go to view" entries, and modal focus trapping/background
  inert behavior. Current tests cover static HTML hooks and API behavior, not
  real DOM interaction.

- [ ] Add release process: changelog (`CHANGELOG.md`), semantic versioning
  policy (`MAJOR.MINOR.PATCH`), and a `make release` or CI workflow that
  tags, builds, and publishes to PyPI.

- [ ] Verify packaging on a clean environment: `pip install -e .`, optional
  extras (`[web]`, `[crypto]`, `[plot]`), console script entry points, and
  Windows PowerShell usage.

- [ ] Add `archive` tests: structure-preserving mode (comments in both files,
  empty sections retained), all three `--orphan-children` modes, `--dry-run`
  for each mode, `--block-on-external-refs`, and cross-file reference warning.

- [ ] Add `#!` directive wiring tests for `timezone`: verify datetime display
  is affected once timezone wiring is implemented.

- [ ] Expand `encrypt`/`decrypt` tests beyond the key-file and AES-GCM round
  trips: cover `--dry-run`, `--type`, `--key-env`, empty key files, wrong
  passphrase failures, and `check` diagnostics for encrypted values.

- [ ] Expand `plot` output tests beyond SVG smoke coverage: text chart rendering
  for task, habit, mood, elapsed, deadlines, each `--group` value, sparkline
  terminal output, and optional PNG behavior when `matplotlib` is installed.

- [ ] Add `init` tests: generated files contain valid directives and a starter
  item; `.lifetxt.json` matches prompted values; prompts before overwriting.

- [ ] Add `doctor` tests: pass on a clean environment, correct
  pass/warn/fail per check, optional dependencies reported as warn, exit
  non-zero on any failure.

- [ ] Add `check --ignore` tests: `--code` filter interaction (include-only
  overrides ignore for same code when both flags specified).

- [ ] Add `undo` edge-case tests: concurrent write isolation (two simultaneous
  quick-adds to the same file).

- [ ] Add `done` tests: ambiguous title match (interactive confirmation prompt).

- [ ] Add `summary` edge-case tests: missing-ID count is accurate, multiple-file
  aggregation totals, and zero-item file returns empty counts without error.

- [ ] Add `review` edge-case tests: mood trend most-common-first summary aggregation.

- [ ] Add dependency edge-case tests: cross-file blockers, and source metadata
  in blocked agenda records.

- [ ] Add remaining CLI batch mutation tests: `batch done` writes across
  multiple files, `batch assign` updates matching records, `batch migrate`
  applies chained migrations, and partial failures produce a clear per-file
  summary without corrupting unaffected files. `batch tag-rename` is covered.

- [ ] Add `inbox --process` tests: prompts for project/due/assignee in sequence,
  each field correctly applied via `assist --update`.

- [ ] Add `assign` edge-case tests: ambiguous `--text` match (interactive
  confirm prompt), validation error when resulting line is invalid.

- [ ] Add `diff` cross-file and glob tests: pass glob sets to diff,
  verify cycle-safe behavior, and test `--status` filter (once added).

- [ ] Add `search` cross-file glob tests: pass a glob pattern covering multiple
  files and verify results aggregate correctly.

- [ ] Add `migrate` chained-migration tests: two migrations applied in sequence,
  idempotency (running twice produces same result), and `add-id` collision
  avoidance when file already has some IDs.

- [ ] Add a `digest --format slack-webhook` payload-shape test: mock the
  HTTP transport (e.g. monkeypatch `urllib.request.urlopen` or point
  `--url-env` at a local `http.server` fixture) and assert the JSON body is
  `{"text": ...}` with the expected summary content. `--format file` append
  and the missing-env-var-exits-before-network-request path are already
  covered in `tests/test_lifetxt.py` (`LifeTxtShareDigestTemplateTests`).

- [ ] Add `undo` / `backup.auto` tests: backup created before each write,
  `backup.keep` eviction, directory auto-created.

- [ ] Add chart API tests: `/api/chart/tasks`, `/api/chart/habits`,
  `/api/chart/mood`, `/api/chart/elapsed` each return a stable JSON structure
  with `labels` and `datasets` arrays; `from`/`to`/`project`/`group` query
  parameters filter results correctly; empty data range returns empty datasets
  without error.

- [ ] Add `/api/review` and MCP `get_review` edge-case tests: `week=true`
  taking precedence over `from`/`to`, an empty file returning zero counts
  without error, `mood_trend` ordering with multiple journal entries on the
  same day, and read-only server mode still serving the report. Report shape,
  invalid-month `400`/`ValueError`, and `project=` filtering are already
  covered in `tests/test_lifetxt.py` (`LifeTxtWebApiTests`, the MCP tests,
  and `ReviewRangeResolutionTests`).

- [ ] Add `links` tests for Mermaid/DOT: cross-file node references, titles
  with embedded quote characters.

- [ ] Add git API endpoint tests (with a real git repo fixture): `POST
  /api/git/pull` returns exit code and stderr; `POST /api/git/commit` with a
  message creates a commit; endpoints return 403 when `git.enable_api` is
  false; endpoints return 403 when accessed from a non-loopback address.

- [ ] Add `who` tests: same person has records in multiple files (latest wins).

---

## Deferred Ideas

Ideas that are useful but should not block any near-term release. Revisit
after the corresponding P1 or P2 feature is stable.

### Format & Parser
- [ ] Consider `#! import: PATH [as ALIAS]` directive (phase 2 of file-level
  metadata): auto-load declared files for cross-file ID resolution without
  listing them on the CLI. Unresolved design questions: relative-path base,
  maximum import depth, circular-import detection, read-only semantics for
  imported IDs. Evaluate whether `--config paths` already covers all practical
  cases before implementing.
- [ ] Consider namespace-qualified ID syntax (`alias:id`) only if flat
  cross-file resolution proves insufficient after `#! import` or `--config
  paths` is in place. The `:` separator conflicts with `key:value` parsing
  and requires a parser change; defer until a concrete unsolvable case arises.
- [ ] Consider JSON Schema definitions for JSON/JSONL output and API payloads
  to enable external tool validation without parsing life.txt directly.

### CLI Extensions
- [ ] Consider named or multiple parallel timers if the single global timer
  becomes too restrictive for users who switch between tasks frequently.
- [ ] Consider a small local daemon that unifies notification watch, timer
  status, and file-reload events into a single background process.
- [ ] Consider `quick` type inference from title keywords ("meeting at 14:00"
  → `E`, "remind me to …" → `R`) as an opt-in mode after the basic command
  is stable.
- [ ] Consider `template` variables beyond date placeholders (`{user}`,
  `{project}`) and a simple prompt mode that asks for variable values before
  expanding.
- [ ] Consider `digest` additional channels (Teams webhook, Discord webhook,
  desktop notification) now that `digest` (Slack webhook / email / file) is
  implemented and stable.
- [ ] Consider `archive` rotation policy (e.g., yearly auto-archive via config
  `archive.auto`) after the basic `archive` command is stable.
- [ ] Consider `--config paths` auto-load mode: when no file arguments are
  given, fall back to the paths configured in `.lifetxt.json`, reducing
  repetition in daily use.
- [ ] Consider `lint` community ruleset repository so teams can share and
  contribute standard style conventions.

### Web & API
- [ ] Consider interactive `plot` mode in `tui` as a live-updating chart
  panel, after the basic `plot` command is stable.
- [ ] Consider `who` integration into the `tui` sidebar panel showing team
  presence alongside tasks and agenda.
- [ ] Consider attaching `share --format html` output as an email attachment
  from `digest --format email` (currently `digest` sends only the plain-text
  summary body; `share` and `digest` are both implemented but not wired
  together).
- [ ] Consider write-conflict detection using source-ownership metadata before
  `update` and `delete` operations when multiple writers share a file.
- [ ] Consider a full Git server (e.g., Soft-serve or a Gitea-compatible
  endpoint) embedded in `serve` for teams who cannot use GitHub/GitLab. Only
  worth implementing if the lightweight `/api/git/*` subprocess endpoints
  prove insufficient for multi-user workflows; defer until there is concrete
  demand.
- [ ] Consider server-side rendering of the exported graph (SVG generated by
  the API rather than serialized from the DOM) so `share`/`digest` can attach
  the same image without a browser. Browser-side SVG/PNG export and `ring`/
  `lr`/`tb` layout switching are implemented.
- [ ] Consider an MCP HTTP/SSE transport with token auth for clients that
  cannot launch stdio commands directly. The current MCP server is dependency-
  free stdio and is intentionally separate from FastAPI.
- [ ] Consider publishing ready-to-copy MCP client configuration snippets for
  Claude Desktop, Cursor, and VS Code, including read-only and multi-file
  examples.

### Security
- [ ] Consider asymmetric encryption (public/private key) for `encrypt` to
  support multi-user scenarios where different people encrypt but only the
  key holder can decrypt.

### Ecosystem
- [ ] Consider import/export adapters beyond current ICS, Markdown, Todoist
  CSV, and GitHub Issues presets: org-mode, mailbox/message logs, and richer
  bidirectional calendar/status integrations.
- [ ] Consider a static HTML export mode (`serve --export DIR`) that writes
  a read-only snapshot of the GUI without requiring the server to keep running.
