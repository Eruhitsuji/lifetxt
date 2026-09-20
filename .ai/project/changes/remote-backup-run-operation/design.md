# Design

`BackupRunStore` is a process-local bounded admission ledger, matching Remote
Safe Mode's existing single-worker/session/rate-limit model. It keys retries by
principal and `Idempotency-Key`, allows one active operation, retains at most
100 statuses, and enforces a 900-second minimum per-principal cooldown.

After a required audit append succeeds, a daemon thread invokes only the
trusted configured argv prefix followed by `start lifetxt-backup.service`.
Systemd remains the execution and hardening boundary, and that unit continues
to run the canonical `backup run-scheduled` implementation and destination
lock. Runner output is discarded. Completion reads only the existing backup
status contract and maps it to separate normalized local/remote states.

The capability manifest advertises the operation only when Remote, backup,
audit, and the runner are configured. Authorization still independently
requires explicit `backup:run`, which is absent from every built-in role. The
Remote page checks both signals before revealing the control; the ordinary Web
surface is unchanged.

Restart drops the bounded HTTP status ledger and its idempotency cache. A
systemd job already dispatched continues under systemd, while a later execution
still meets the existing destination lock. Clients treat a missing old status
as expired state and obtain current backup status through the existing
read-only surface rather than receiving paths or journal output.
