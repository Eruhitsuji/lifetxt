# Design

## Summary

Before `server-init` builds any plan containing the optional Remote backup
Polkit rule, execute the fixed `/usr/bin/pkaction --version` probe. Accept only
a successfully parsed version at or above 0.106, where upstream Polkit provides
the JavaScript `.rules` backend. Reject legacy 0.105 and indeterminate results
with an actionable diagnostic that keeps Remote `backup:run` disabled.

## Security Boundary

The generated rule remains unchanged: it matches the validated service user,
`start`, and `lifetxt-backup.service`. No `.pkla` fallback is possible because
that backend cannot constrain the systemd action details needed by the existing
authority contract. Probe argv and path are constants and contain no request or
deployment-controlled values.

## Verification and Limitations

Version detection prevents the known unsupported backend from receiving a
misleading artifact, but it cannot prove that a supported host loaded the
installed rule. The runbook therefore requires a real service-user start check
and negative checks for stop and another unit. A failed positive check requires
removing the rule and leaving Remote backup disabled. Scheduled backup remains
independent.

## Alternatives

- Broad legacy `.pkla` authorization is rejected because it grants general
  `org.freedesktop.systemd1.manage-units` authority.
- Treating every `.rules` directory as supported is rejected because the
  affected 0.105 host accepted the file while never evaluating it.
- Automatically starting the real backup service during `server-init` is
  rejected because a dry-run must not trigger an operational backup.

## Rollback

Revert the code and documentation change, remove any generated rule, and keep
Remote `backup:run` disabled. Scheduled `lifetxt-backup.timer` is unaffected.
