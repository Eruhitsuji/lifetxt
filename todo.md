# lifetxt TODO / Roadmap

Last updated: 2026-06-27 (updated x4)

This roadmap tracks remaining work after the current prototype updates. Completed prototype-only items are removed; items below are implementation, validation, documentation, or design work that still matters.

Priority guide:

- `P0`: Stabilize features that are already implemented and likely to break in real use.
- `P1`: Implement or refine core features that affect the format, CLI, API, or daily workflow.
- `P2`: Improve usability, documentation, packaging, and long-term maintainability.
- `Deferred`: Useful ideas that should not block the next practical release.

## P0: Stabilization

- [ ] Verify `tui` in real terminals: WSL, Windows Terminal, Textual installed/not installed, watchdog installed/not installed, Vim-like keymap, and curses colors.
- [ ] Verify `lifetxt fzf` with actual `fzf` and `peco` on both Windows and Unix-like shells, including preview command quoting.

## P1: Format Semantics

- [ ] Simplify and document recommended detail keys. Keep a small core set and define type-specific meanings only where necessary.
- [ ] Clarify user-related keys: `owner`, `assignee`, `attendee`, `person`, `sender`, `recipient`, `team`, and `group`.
- [ ] Expand `repeat:` and `RRULE:` consistently in `agenda`, `filter --after/--before`, `stats`, Web API, and exports.
- [ ] Decide whether typo-like `repete:` should be auto-fixed, warned as a likely `repeat:`, or left as a custom detail key.
- [ ] Decide which item types should recommend `elapsed:` beyond task-like records.
- [ ] Finalize timezone-aware datetime round-trip rules for parser, JSON/CSV output, display, and filtering.
- [ ] Define dependency semantics for `depends_on:` and `blocks:` beyond generic links.
- [ ] Decide whether hierarchy should be represented mainly by `parent:` or inferred indentation, and how `--canonical` should output it.
- [ ] Add line continuation syntax: a trailing `\` at end of line joins the next line as if they were one, following shell convention (bash/zsh style). Define parser behavior for whitespace handling at the join point and error handling for a bare `\` at end of file.
- [ ] Define cross-file ID reference semantics: allow `parent:`, `ref:`, `depends_on:`, `blocks:`, and `related:` to resolve IDs across multiple loaded files, not only within a single file. Specify how the file of origin is reported in JSON/JSONL output and error messages.
- [ ] Define encryption metadata conventions: decide whether encrypted field values are stored inline as a tagged string (e.g., `note:enc:BASE64`) or in a separate sidecar file, and how the parser distinguishes encrypted from plain values without decrypting.

## P1: CLI / CUI

- [ ] Further unify filter options across `filter`, `agenda`, `stats`, `to-json`, `to-jsonl`, `to-csv`, and `markdown`.
- [ ] Add recurrence occurrence output options to `agenda`, including source item ID, occurrence datetime, and recurrence rule.
- [ ] Define export behavior for filtered recurrence occurrences in JSON, JSONL, CSV, and life.txt output.
- [ ] Add text output modes for wide/compact terminal widths where tables currently become hard to read.
- [ ] Improve `assist` support for Markdown body, RRULE, repeat, duration, and links.
- [ ] Keep CLI help and docs synchronized for `tui`, `fzf`, `timer`, `stats`, `git-hook`, and `completion`.
- [ ] Add `encrypt` and `decrypt` commands: encrypt selected field values (e.g., `body:`, `note:`, or all fields of `J` and `M` type items) using a passphrase or key file. `encrypt` rewrites matched values as tagged ciphertext in-place; `decrypt` restores them. Support `--field FIELD` to limit scope, `--type TYPE` to target specific item types, `--dry-run` to preview changes, and `--key-env ENVVAR` to avoid passing secrets on the command line. Use only Python standard-library primitives (`hashlib`, `hmac`, `secrets`) for the dependency-free core; document an optional path using the `cryptography` package for stronger algorithms. Define a stable ciphertext tag format (e.g., `enc:AES256GCM:BASE64`) so the parser can detect and skip rendering of encrypted values without decrypting.
- [ ] Add `plot` command for CLI-native visualization: render task completion trends, habit streaks, mood timelines, elapsed time by project, and deadline density as Unicode bar charts or sparklines in the terminal without any additional dependencies. Support `--type`, `--project`, `--from`, `--to`, and `--group daily|weekly|monthly` filters consistent with `stats`. Add an optional `--format svg` or `--format png` output mode using `matplotlib` or another opt-in dependency; keep the dependency-free text output as the default.

## P1: Web API / Browser UI

- [ ] Standardize API error responses with stable JSON error bodies.
- [ ] Add a simple local token option before supporting non-local use.
- [ ] Improve message thread UI using `parent:` and id-based message APIs.
- [ ] Improve Web notification UX: permission state, acknowledgement, snooze, retry, and visible delivery state.
- [ ] Allow display-mode presets from config `views`, not only URL query parameters.
- [ ] Represent recurrence occurrences in Web API/UI without confusing source items and generated occurrences.
- [ ] Add API tests for mixed writable files and generated/read-only files.
- [ ] Expand `docs/en/web.md` and `docs/ja/web.md` with current endpoint request/response examples.
- [ ] Add chart endpoints to the Web API (`/api/chart/tasks`, `/api/chart/habits`, `/api/chart/mood`, `/api/chart/elapsed`) that return JSON data suitable for rendering with a browser charting library. Add corresponding chart panels to the browser GUI.

## P1: Multiple Files / Sync / External Tools

- [ ] Document a recommended directory layout for hand-written files, generated ICS files, and archive files.
- [ ] Make generated/read-only file handling consistent across CLI, Web UI, and API.
- [ ] Improve `sync-ics` idempotency: stable IDs, update detection, deletion detection, and source metadata.
- [ ] Define integration boundaries for calendar sources beyond ICS.
- [ ] Define import/export boundaries for presence/message tools such as Teams, Discord, and Slack.
- [ ] Investigate CSV/JSON/Markdown adapters for external task-management tools.
- [ ] Consider JSONL streaming or watch-mode APIs for editors, launchers, and notification daemons.
- [ ] Add pre-commit framework examples in addition to the built-in Git hook installer.
- [ ] Document that secret URLs and tokens should not be stored in life.txt content.

## P2: Editor Support

- [ ] Package VS Code grammar/snippets so they can be installed manually without copying files.
- [ ] Keep editor file associations documented for `life.txt`, `*.life.txt`, and `*_life.txt`.
- [ ] Generate completion candidates from `lifetxt/model.py` to reduce drift between editor, CLI, and spec.
- [ ] Add highlight snapshot tests for title, status, type, detail key, quoted value, and body continuation.
- [ ] Add editor support for Markdown body, quoted values, RRULE, and recurrence occurrences.
- [ ] Add snippets for task, event, status, message, journal, timer-ready task, and linked subtask records.
- [ ] Add syntax highlight and snippet support for line continuation (`\` at end of line).
- [ ] Add syntax highlight support for encrypted field values (e.g., `enc:` prefix tag) so editors display them distinctly rather than as plain text.

## P2: TUI Usability

- [ ] Consider configurable TUI themes and keymaps after real-terminal feedback.
- [ ] Consider selectable TUI rows with item detail, open-in-editor, mark-done, and quick-filter actions.

## P2: Documentation / Examples

- [ ] Decide the synchronization policy between root `readme.md`, `docs/en/*`, `docs/ja/*`, and `life_txt_format_spec.md`.
- [ ] Add examples for `timer`, `stats`, `tui`, `fzf`, `git-hook`, and `completion`.
- [ ] Add examples for RRULE, recurrence occurrence, and external integration.
- [ ] Add recommended workflow docs: daily use, team status, messages, calendar sync, and weekly review.
- [ ] Add migration notes for major format changes: `S`, `M`, `J`, multiline body, hierarchy, CSV, `elapsed:`, Markdown subset, and RRULE.
- [ ] Add screenshots or terminal captures for Web UI, display mode, TUI, and stats output.
- [ ] Consider generating parts of the spec and CLI docs from parser/model definitions.
- [ ] Generate a diagnostic code/category catalog from parser and validator definitions for docs and shell completion.
- [ ] Add source ownership examples for generated/read-only files and mixed writable files.
- [ ] Document recommended file-splitting strategies: one file per editor/author (including auto-generated sources such as ICS sync), optional further split by project or period, and periodic archiving. Clarify that these are recommendations, not enforced constraints.
- [ ] Add archive workflow docs: when to archive, how to run the `archive` command, and how to include archive files in `agenda` or `filter` via glob patterns.
- [ ] Add `--fix` mode to `check` (or a separate `fix` command) to auto-apply W222 duration normalization and other canonicalization warnings in-place.
- [ ] Document line continuation syntax (`\`) with examples and known limitations (e.g., interaction with body continuation `|` lines).
- [ ] Document cross-file ID reference behavior: which commands resolve cross-file IDs, how to pass multiple files, and how `--config paths` can automate this.
- [ ] Document the `encrypt`/`decrypt` commands: supported algorithms, key management recommendations (passphrase vs. key file vs. environment variable), which field types are appropriate targets, and how to use `check` safely on a partially encrypted file.
- [ ] Document the `plot` command: available chart types, filter options, terminal rendering behavior, and how to enable optional SVG/PNG output.
- [ ] Add `plot` and `encrypt`/`decrypt` workflow examples to `docs/en/cli.md` and `docs/ja/cli.md`.

## P2: Tests / CI / Release

- [ ] Add CI for unit tests, compile checks, and example validation.
- [ ] Add a lightweight smoke-test runner for release checks that can execute selected CLI smoke tests, including the timer state-file smoke test, without running the full unittest suite.
- [ ] Add snapshot tests for important human-readable CLI output.
- [ ] Add cross-platform tests for paths, glob expansion, line endings, and shell completion output.
- [ ] Add glob input tests for `*.life.txt`, `*_life.txt`, and `projects/**/*.life.txt`.
- [ ] Add parser edge-case tests for escaping, quoted values, invalid continuation, indentation, duplicate IDs, and missing references.
- [ ] Add tests for RRULE, recurrence occurrence, timezone normalization, and duration parsing.
- [ ] Add tests for W222 duration normalization warnings across more edge cases (bare integers, `1h00m`, unrecognized formats like `1.5h`).
- [ ] Add snapshot tests for Markdown CLI HTML output and Web UI Markdown preview rendering.
- [ ] Check performance for large files and duplicate ID detection across many files.
- [ ] Add FastAPI test-client coverage when optional Web dependencies are installed.
- [ ] Add release notes, changelog, and versioning policy.
- [ ] Verify `pip install -e .`, optional extras, console script entry points, and Windows PowerShell usage.
- [ ] Add parser tests for line continuation (`\`): mid-line join, trailing whitespace, bare `\` at EOF, and interaction with body continuation lines.
- [ ] Add `archive` command integration tests for multi-file sources, `--status` custom filters, and `--before` edge cases (items missing date keys).
- [ ] Add `encrypt`/`decrypt` round-trip tests: verify that encrypting and decrypting a field restores the original value exactly, across all supported algorithms. Test `--dry-run`, `--field`, `--type`, and `--key-env` options. Test that `check` does not emit false-positive errors for encrypted values it cannot read.
- [ ] Add `plot` output tests: verify text chart rendering for task, habit, mood, and elapsed types with `--group daily`, `weekly`, and `monthly`. Add snapshot tests for terminal bar chart and sparkline output.

## Deferred Ideas

- [ ] Consider named or multiple parallel timers if the single global timer becomes too restrictive.
- [ ] Consider a small local daemon that unifies notification watch, timer status, and file reload events.
- [ ] Consider import/export adapters beyond ICS, such as Markdown, org-mode, Todoist CSV, and mailbox/message logs.
- [ ] Consider extending the Markdown subset with task lists, tables, or images only after editor support and security review.
- [ ] Consider read-only static HTML export for users who do not want to run the server.
- [ ] Consider JSON Schema for JSON/JSONL output and API payloads.
- [ ] Consider write-conflict detection that uses source ownership metadata before update/delete operations.
- [ ] Consider an `archive` rotation policy (e.g., yearly auto-archive via config) after the basic `archive` command is stable.
- [ ] Consider a `--config paths` auto-load mode where commands that accept file arguments fall back to configured paths when no explicit input is given, reducing repetition in daily use.
- [ ] Consider asymmetric encryption (public/private key) for the `encrypt` command to support multi-user or team scenarios where different people can encrypt but only the key holder can decrypt.
- [ ] Consider an interactive `plot` mode in `tui` that renders live-updating charts alongside the existing task and agenda panels, after the basic `plot` command is stable.
- [ ] Consider exporting `plot` output as a self-contained HTML file with embedded JavaScript charting (e.g., Chart.js) as an alternative to SVG/PNG for users who want to share reports without running the server.
