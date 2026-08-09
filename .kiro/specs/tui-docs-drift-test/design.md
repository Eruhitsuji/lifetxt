# Design Document

## Overview
A new test (`tests/test_surface_runtime.py`) parses `docs/en/cli.md`'s "#### Commands" section markdown tables into a `{name: usage}` dict and compares it against `{command.name: command.usage for command in tui_app.COMMANDS}`, reporting missing/stale/mismatched entries.

## File Structure Plan
### Modified Files
- `tests/test_surface_runtime.py`: `_tui_doc_commands()` parser + `TuiDocumentationDriftTests`.
- `docs/en/cli.md`, `docs/ja/cli.md`: fix any drift the new test finds.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| 1.1-1.4 | `_tui_doc_commands()` regex-parses `| \`/name usage\` | ... |` rows; `test_docs_command_tables_match_the_tui_command_registry` diffs the two dicts |

## Testing Strategy
- Run the new test against the current repository state: found and fixed 2 real, pre-existing drift cases (`/now` missing its `[PERSON]` usage argument in docs; `/state`'s ` | end` usage variant missing in docs), in both `docs/en/cli.md` and `docs/ja/cli.md`.
