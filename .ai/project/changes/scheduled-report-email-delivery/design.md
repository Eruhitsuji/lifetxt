# Design: Scheduled report email delivery

## Context

`lifetxt server-init`'s opt-in `reporting` section and `lifetxt server-report
plan|install|remove` (both delivered under #609-#611) already generate one
systemd oneshot service + `Persistent=true` timer per report job, running
`report run <profile> --previous`. Neither path can email the resulting
report; an operator wanting scheduled email delivery had to hand-write a
second unit or wrapper script outside lifetxt's own generator. #616 (a
sibling, dependency change on the same integration branch) added an explicit
SMTP port and a shared mail transport primitive to `report send` itself; this
change wires `report send` into the *scheduled* path.

## Shared unit generator: one function, two callers

`server_init.report_service_unit_text(config, job)` is the single function
both `server-init`'s `reporting` section (`build_plan()`, unchanged call
site) and `server-report plan|install` (`server_report.build_plan()`, which
imports the function directly: `from .server_init import
report_service_unit_text, report_timer_unit_text`) already call. Extending it
once benefits both paths with zero additional wiring at either call site --
confirmed by a dedicated identity-check test
(`test_report_service_unit_text_is_the_exact_function_server_report_reuses`)
asserting `server_report.report_service_unit_text is
server_init.report_service_unit_text`, so the two can never independently
drift.

```python
def report_service_unit_text(config, job):
    send_email = bool(job.get("send_email"))
    environment_file = job.get("environment_file")
    exec_lines = "ExecStart={exe} report run {profile} --previous --config {app_config}\n"
    if send_email:
        exec_lines += (
            "ExecStart={exe} report send {profile} --previous --config {app_config}\n"
        )
    environment_file_line = (
        "EnvironmentFile={environment_file}\n" if environment_file else ""
    )
    return (...).format(..., environment_file=environment_file)
```

`environment_file_line` is placed before the `ExecStart=` lines (matching
`systemd.service(5)`'s convention of `EnvironmentFile=` preceding the command
lines that consume it) and only emitted when `environment_file` is set, so a
default job (the overwhelming majority of jobs, and every job installed
before #617) produces byte-identical unit text to before this change --
locked in by `test_default_job_has_no_environment_file_or_second_exec_start`
(server-init) and `test_no_send_email_plan_has_no_environment_file_or_second_exec_start`
(server-report).

## Validation: reuse, not reimplementation

Two independent validation sites enforce the same three rules, both reusing
existing machinery rather than duplicating checks:

1. `server_init._validate_reporting_config()` -- validates every
   `reporting.jobs[]` entry at `server-init` config-load time, before any
   file is written. `send_email`'s "profile must have `email`" check reads
   `validated_profiles[profile_name].get("email")` from the report-profile
   validation this function already performs via `report_cli._profiles()` --
   no second parse of the profile's email section.
2. `server_report.build_plan()` -- validates the same three rules for
   `server-report plan|install`'s `--send-email`/`--environment-file`
   arguments, reading the profile's `email` key from the application config
   it loads for the named profile.

Both reuse `server_init._validate_required_absolute_nowhitespace_path()` (via
a small `ServerInitError`-to-`ServerReportError` translating wrapper,
`_validate_environment_file_path`, in `server_report.py`) for the
injection-safety check on `environment_file` itself -- the identical check
already protecting `service_control.wrapper_path`/`sudoers_path` and the
AI-workspace `write_file` path elsewhere in `server_init.py`.

Validation order (both sites): type-check `send_email` as a plain bool ->
if true, require the profile to carry `email` -> require `environment_file`
to be present and pass the path-safety check -> if `send_email` is false/
absent, require `environment_file` to be absent. Every rejection happens
before any file is written or any systemd command is run.

## CLI/plan surface

`server-report plan|install` gained `--send-email` (`store_true`) and
`--environment-file PATH` (`metavar="PATH"`), threaded into
`build_plan(..., send_email=args.send_email, environment_file=args.environment_file)`.
A new `_scheduled_email_line(plan)` helper renders `"Scheduled email: enabled
(environment file: %s)"` or `"Scheduled email: disabled"` from the `plan`/
`result` dict (both carry the same two keys), used in `plan`'s text output,
`install`'s dry-run preview, and `install --yes`'s post-write confirmation --
so the added network side effect (an outbound SMTP send) is visible in every
output mode without needing to read the generated unit file.

`build_plan()`'s returned `plan` dict and `apply_install()`'s returned result
dict both carry `send_email`/`environment_file` as top-level fields
(`--format json` exposes them directly), never any SMTP credential value --
the credentials live only in the file `environment_file` names, which
lifetxt never opens.

## Testing strategy

- `tests/test_server_report.py` `BuildPlanTests`: default job unaffected;
  `send_email` job generates `EnvironmentFile=`/two ordered `ExecStart=`
  lines with `report run`'s line index strictly before `report send`'s;
  `send_email` without a profile `email` section rejected; `send_email`
  without `environment_file` rejected; `environment_file` without
  `send_email` rejected, including an empty-string path argument; no SMTP
  credential name (`LIFETXT_SMTP_PASS`) ever appears in generated content.
- `tests/test_server_report.py` `ApplyInstallTests`/`ServerReportCliTests`:
  `send_email` surfaced in the `apply_install` result dict; CLI `plan`/
  `install` text and dry-run output show the scheduled-email line; CLI-level
  rejection of the two invalid combinations exits non-zero with a named
  error.
- `tests/test_server_init.py` `ReportingConfigGenerationTests`: the same
  three validation rules and unit-content assertions, exercised through
  `server_init.load_config()`/`build_plan()` directly (the `reporting`
  section's own path, independent of `server-report`'s CLI); an identity
  check locking in that `server_report.py` reuses
  `server_init.report_service_unit_text`/`report_timer_unit_text` verbatim
  rather than a parallel copy.
- Live manual verification (real CLI, disposable fixture, this Windows
  sandbox): `server-report plan/install` with `--send-email
  --environment-file` produced a real, on-disk `.service` file (inspected
  directly) containing `EnvironmentFile=C:/lifetxt-mail.env`, `report run`
  followed by `report send` as two ordered `ExecStart=` lines, and zero
  occurrences of any credential value; the disabled (default) case produced
  the unchanged single-`ExecStart=` unit; all four validation-refusal paths
  (missing email config, missing environment-file, environment-file without
  send-email, and the reverse) failed loudly with named errors before
  writing anything, confirmed via a real disposable fixture directory
  listing before/after each refusal.
- Full regression attempt: `python -m unittest discover` -> 3325 tests,
  FAILED (3 failures, skipped=195). The failures reproduce in isolation in
  `tests.test_external_verification.ProcessTreeTimeoutTests` (2 tests) and
  `tests.test_paths.MultiFileSourceIntegrityTests.
  test_permission_denied_file_among_multiple_sources_fails_loudly`, all
  outside #617's write scope. Focused #617 regression remains green:
  `python -m unittest tests.test_server_init tests.test_server_report` ->
  66 tests, OK.

## Security review focus

- `environment_file` is validated as an absolute, whitespace-free path
  before being written into any generated unit text -- the same injection-
  safety check already applied to every other systemd-unit-embedded path in
  this module, so a malicious or malformed value cannot break out of the
  `EnvironmentFile=` directive's own line.
- lifetxt never opens, reads, or embeds `environment_file`'s contents at any
  point in this change; only the path itself is ever written to disk (in
  generated unit text) or returned (in plan/JSON output). The actual
  credential values are supplied to the `report send` process exclusively by
  systemd itself, at service-start time, via the standard
  `EnvironmentFile=` directive -- outside lifetxt's own process entirely.
- `report send`'s own credential-non-disclosure guarantee (confirmed under
  #616: SMTP password never appears in intentional output or error text) is
  what makes `journalctl -u lifetxt-report-<name>.service` safe to inspect
  after a failed scheduled send; this change does not weaken or bypass that
  guarantee, since it invokes the unmodified `report send` command exactly
  as a human operator would.
- The two-`ExecStart=`-line ordering is systemd's own guarantee, not custom
  code in this change, so there is no new code path where a failed `report
  run` could still trigger `report send` on stale or partial output.
