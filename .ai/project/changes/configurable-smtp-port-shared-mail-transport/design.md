# Design: Configurable SMTP port and shared mail transport

## Context

Three surfaces send plain-text SMTP email today: `lifetxt report send`
(`lifetxt.mail_delivery.send_smtp_text`), `lifetxt digest --format email`
(same function), and notification email (`_send_notification_email_batch`
in `lifetxt/cli.py`, an independent inline `smtplib`/`MIMEText`
implementation predating `mail_delivery.py`'s extraction). None of the three
can pass an explicit SMTP port -- `send_smtp_text` calls
`smtplib.SMTP(smtp_host, timeout=10)` with no port argument at all, so
STARTTLS submission on the standard port 587 is unreachable without an
external relay or wrapper.

## Shared transport primitive

`lifetxt/mail_delivery.py` gains two additions:

```python
def validate_smtp_port(value):
    """Raise MailDeliveryError unless value is an int in [1, 65535].

    bool is explicitly rejected (bool is an int subclass in Python; a
    stray `true`/`false` in JSON config must not silently become port 1/0).
    Never called to select a default -- omitting a port (None) is a
    distinct, unvalidated case every caller handles separately.
    """

def _deliver_smtp_message(mime, to_addrs, smtp_host, smtp_user, smtp_pass, port=None):
    """The sole connect/starttls/login/sendmail sequence in this project.

    port=None reaches smtplib.SMTP(smtp_host, timeout=10) exactly as it did
    before this parameter existed, byte-identical to the pre-#616 call.
    """
```

`send_smtp_text(..., port=None, ...)` validates `port` up front (before the
`dry_run` branch, so an invalid value fails deterministically regardless of
`--dry-run`), includes an optional `" port %d"` note in its dry-run message
when a port is given, and delegates the real send to
`_deliver_smtp_message()`.

## Notification email convergence

`_send_notification_email_batch()` (`lifetxt/cli.py`) is rewritten to:

1. resolve `port` from `--smtp-port` or `notifications.email.smtp_port`
   (same `getattr(args, ...) or email_config.get(...)` precedence pattern
   already used for `host_env`/`user_env`/`pass_env`);
2. validate it via `mail_delivery.validate_smtp_port()`;
3. keep its own existing dry-run message text
   (`"[dry-run] Would email %d notification(s) to %s via $%s%s:\n%s\n"`),
   only adding the same optional port note `send_smtp_text` uses;
4. resolve credentials via `mail_delivery.resolve_smtp_credentials()`
   instead of its own duplicated inline `os.environ.get`/error-message
   block -- confirmed byte-identical error text before switching (see
   requirements.yml's decision log);
5. send via the shared `_deliver_smtp_message()` instead of its own
   `smtplib.SMTP(...).starttls()/.login()/.sendmail()` block.

This was deliberately **not** converged onto `send_smtp_text()` directly,
since that function's dry-run/success wording (subject-centric) differs
from notify's existing, test-asserted wording (notification-count-centric).
See requirements.yml's decision log for the full reasoning. The result: one
authoritative SMTP transport implementation
(`_deliver_smtp_message`/`resolve_smtp_credentials`), reused by all three
callers, while each caller keeps the user-facing message text its own
existing tests already lock in.

## CLI/config surface

- `notify --smtp-port PORT` (`type=int`, no default -- omission means "use
  config or the existing default port").
- `digest --smtp-port PORT` (same shape), threaded into
  `command_digest`'s email branch as `port=getattr(args, "smtp_port", None)`.
- `reports.*.email.smtp_port`: added to `report_cli.EMAIL_CONFIG_KEYS`,
  validated in `_validate_email_config()` via
  `mail_delivery.validate_smtp_port()` (wrapped to a `ValueError` naming the
  profile and field), and to the `schema_extensions_v5._report_email_config()`
  JSON Schema fragment (`{"type": "integer", "minimum": 1, "maximum": 65535}`).
  `_command_send()` passes `port=email_config.get("smtp_port")` through.
- `notifications.email.smtp_port`: a `config_registry.py` entry only (no
  JSON Schema section exists for `notifications` at all today -- confirmed
  by search before starting; adding a schema fragment for exactly one key
  while every sibling notification key stays unvalidated would be a more
  inconsistent, larger-scoped change than this issue asks for).

`report inspect`'s `email_configured` boolean output is deliberately left
unchanged (not expanded to show `smtp_port`) -- out of this change's write
scope (`report inspect` belongs to the already-closed #615), and the port is
already fully observable via `report validate`/the profile config itself.

## Backward compatibility

Every existing call site that does not set a port keeps calling
`smtplib.SMTP(host, timeout=10)` byte-for-byte -- verified directly by
`test_real_send_uses_starttls_and_login` (pre-existing, unmodified
assertion) and two new tests
(`test_send_without_smtp_port_preserves_default_smtplib_call`,
`test_notify_email_batch_without_port_preserves_default_smtplib_call`).

## Testing strategy

- `tests/test_mail_delivery.py`: `ValidateSmtpPortTests` (boundary/invalid/
  bool/float/string/None cases); `SendSmtpTextTests` port-passing,
  port-validated-before-network-access (including under `dry_run=True`),
  and dry-run port-note presence/absence.
- `tests/test_report_v2_cli.py`: profile validation accepts/rejects
  `smtp_port`; `report send` end-to-end with a mocked `smtplib.SMTP`
  confirms the configured port reaches the real call, and that omitting it
  preserves the exact no-port call signature.
- `tests/test_lifetxt.py`: `notify`/`digest` `--smtp-port` dry-run (real
  subprocess) shows the port note; an invalid `--smtp-port` fails before any
  dry-run output; a config-sourced (not CLI-flag) port is proven to reach
  the mocked `smtplib.SMTP` call via a direct, in-process
  `_send_notification_email_batch()` call.
- `tests/test_config_validation.py`: registry entry shape;
  `notifications.email.smtp_port` (an integer) is confirmed **not** to trip
  the unrelated `C003` plaintext-secret scanner (which only flags string
  values under secret-hinting key names).
- Live manual verification (real terminal, no mocks): `report send`
  end-to-end with a mocked `smtplib.SMTP` via a standalone script; `notify
  --email --smtp-port 587 --dry-run` and `digest --format email --smtp-port
  587 --dry-run` both showing the port note; an out-of-range port rejected
  before any dry-run text for both `notify` and `digest`.

## Security review focus

- The port is not secret and is safe to appear in dry-run/log output; only
  host/user/pass remain environment-variable references, never resolved
  into intentional output.
- `validate_smtp_port()` must run before any network call on every path,
  including under `--dry-run` (an invalid dry-run port must still fail
  loudly rather than silently succeed with a misleading preview) --
  confirmed by a dedicated test
  (`test_invalid_port_is_rejected_even_under_dry_run`).
- No new dependency, no new file write, no new persisted state.
