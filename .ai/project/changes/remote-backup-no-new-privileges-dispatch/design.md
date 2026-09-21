# Design

## Summary

Generate an optional root-owned Polkit JavaScript rule from `server-init`. The
rule approves `org.freedesktop.systemd1.manage-units` only when the caller is the
validated service account, the systemd action verb is `start`, and the unit is
exactly `lifetxt-backup.service`. Remote backup dispatch then invokes
`/bin/systemctl --no-ask-password start lifetxt-backup.service`; systemd and
Polkit authorize it outside the Web process, so `NoNewPrivileges=true` remains
effective.

## Interfaces and Contracts

- ADDED: `service_control.remote_backup_polkit_rule_path` server-init setting.
- MODIFIED: supported `remote.backup_run.service_command` deployment value is
  `/bin/systemctl --no-ask-password` for hardened system services.
- UNCHANGED: Remote HTTP routes, scopes, audit, idempotency, cooldown, operation
  status, scheduled backup unit, archive format, remote upload, and retention.

## Alternatives

- Disabling `NoNewPrivileges` was rejected because it weakens the entire Web
  service to make a single operation work.
- Sudo and a setuid-style helper were rejected because privilege acquisition
  inside the Web process is incompatible with the hardening boundary.
- A general Polkit authorization for `manage-units` was rejected because it
  would permit other verbs or units.

## Risks

- A distribution may use a different systemctl path or require Polkit reload;
  the path remains explicit configuration and the runbook requires an exact
  service-user verification command.
- An operator can install an incorrect rule; `server-init` emits reviewable,
  deterministic content and refuses conflicting existing files.

## Operations Impact

Operators opt in to the new rule path, review/install the generated artifact as
root, configure the fixed systemctl argv prefix, and verify the exact start as
the service account. Rollback removes the rule and restores the prior config;
scheduled backups remain functional throughout.

## Compatibility Impact

The new setting defaults to null, so existing server-init plans and deployments
are unchanged. Existing wrapper/sudoers service control remains supported for
interactive server-update only.
