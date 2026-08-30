# Decisions

## Extract a shared transport primitive rather than fully converging onto `send_smtp_text()`

See requirements.yml's decision log for the full reasoning: notify's
existing dry-run/success message text is asserted by a pre-existing test
(`test_notify_cli_email_dry_run`) and differs materially from
`send_smtp_text()`'s own generic wording. `_deliver_smtp_message()` is the
single authoritative SMTP transport (satisfying the issue's own "(or the
same single authoritative helper)" allowance) while each caller keeps
ownership of its own user-facing message text.

## No JSON Schema section for `notifications.email.smtp_port`

`notifications.*` has no JSON Schema section at all today (confirmed by
search before starting) -- only one existing `config_registry.py` entry
(`notifications.email.smtp_pass_env`) documents it for `config explain`,
with every other notification key (including `enabled`, `to`, `subject`,
`smtp_host_env`, `smtp_user_env`, `lookahead`, `grace`) unvalidated by any
schema. Adding strict schema validation for exactly one new key while every
sibling stays unvalidated would be a more inconsistent, larger-scoped change
than this issue asks for. `notifications.email.smtp_port` gets the same
treatment as its sibling `smtp_pass_env`: a `config_registry.py` entry only.

## `report inspect` output is not extended in this change

`report inspect` (#615, already closed) currently reports only a boolean
`email_configured` flag, never individual email-config fields. Adding a
`smtp_port` field there would touch an already-closed issue's surface for a
capability this issue's own scope contract does not name
(`req-report-resolved-inspection` is not in this change's `write_scope`).
The port remains fully observable through `report validate` (which runs the
same profile validator) and the profile configuration itself. Recorded as a
deliberate boundary, not an oversight, in case a future issue wants richer
`inspect` output for email delivery.

## Port validation runs unconditionally, including under `--dry-run`

An invalid `--smtp-port`/`smtp_port` must fail loudly even when
`--dry-run` is set, rather than silently producing a preview for a
configuration that would fail for real. This matches the existing
`report_cli._validate_profile()` philosophy (validate eagerly, before any
side effect) and is locked in by a dedicated test
(`test_invalid_port_is_rejected_even_under_dry_run`).
