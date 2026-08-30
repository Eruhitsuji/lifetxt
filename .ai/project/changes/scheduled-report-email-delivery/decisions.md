# Decisions

## Two ordered `ExecStart=` lines instead of a wrapper script

See requirements.yml's decision log. systemd's own `Type=oneshot` semantics
already guarantee ordered execution and whole-unit failure on any line's
failure, so no new orchestration code is needed. This keeps
`report_service_unit_text()` a small, template-only extension rather than
introducing a shell wrapper this project would then have to generate,
package, and keep in sync with the Python-level unit generator.

## Validation reuses the existing report-profile validator and path-safety check

`send_email`'s "profile must have `email`" rule reads from the report
profile validation `server_init._validate_reporting_config()` (via
`report_cli._profiles()`) and `server_report.build_plan()` already perform,
rather than re-parsing the profile's `email` section a second time.
`environment_file`'s absolute/no-whitespace check reuses
`server_init._validate_required_absolute_nowhitespace_path()`, the same
function already protecting `service_control.wrapper_path`,
`service_control.sudoers_path`, and the AI-workspace `write_file` path.
`server_report.py` wraps it (`_validate_environment_file_path`) only to
translate `ServerInitError` into its own `ServerReportError` convention --
the validation logic itself is not duplicated.

## `docs/ja/cli.md`'s server-report section is not added in this change

`docs/ja/cli.md` has no numbered sections 19-24 at all -- Development
Tickets, Remote Safe Mode Client, Commands Documented Elsewhere,
`server-init`, `server-update`, and `server-report` are all missing,
confirmed by comparing section headings between the English and Japanese
`cli.md` before writing any documentation for this change. This is a large,
pre-existing translation gap spanning several past features, not something
introduced by #616 or #617. Adding one isolated `server-report` section out
of order (with no preceding `server-init`/`server-update` context) would
read as structurally incoherent, and translating the full missing range is a
separate, much larger effort outside this issue's scope. `docs/ja/reports.md`
-- which already has a relevant "Ubuntu Server での定期実行" section -- was
extended instead, so Japanese-reading operators are not left with zero
pointer to the new capability, even though the detailed flag reference stays
English-only for now (matching `docs/deployment/ubuntu-server.md`'s own
established English-only precedent for deployment runbooks).

## `report_service_unit_text()`'s `EnvironmentFile=` line placement

Placed immediately before the `ExecStart=` lines, matching
`systemd.service(5)`'s documented convention of `EnvironmentFile=` preceding
the command lines whose environment it populates. No functional ordering
requirement exists between `EnvironmentFile=` and `ExecStart=` within the
`[Service]` section (systemd parses the whole section before executing
anything), but keeping the existing convention avoids surprising an operator
who edits the generated unit by hand.
