# Security Review

Status: completed by Codex before final verification.

## Review Scope

- `lifetxt/server_init.py`
- `lifetxt/cli.py` `server-init` wiring
- `tests/test_server_init.py`
- `docs/en/cli.md`
- `docs/deployment/ubuntu-server.md`

## Findings

1. Fixed: generated unit/sudoers fields accepted unsafe strings.

   `service_user`, `service_group`, `service_control.sudo_user`,
   `service_control.wrapper_path`, and `service_control.sudoers_path` are
   inserted into generated systemd/sudoers/script artifacts. The initial
   implementation validated presence but not control characters, whitespace in
   sudo wrapper paths, absolute wrapper/sudoers paths, or POSIX account shape.
   That could produce malformed or attacker-influenced privileged artifacts if
   an untrusted config file were applied.

   Fix: added explicit POSIX account validation, single-line/control-character
   path validation, and absolute/no-whitespace validation for service-control
   privileged paths. Added regression coverage in `tests/test_server_init.py`.

## Review Checks

The final review re-checked:

- dry-run non-mutation;
- no shell-string command execution;
- no broad passwordless `systemctl` recommendation;
- no service bind wider than `127.0.0.1`;
- no silent overwrite of production data, sudoers files, units, or proxy config;
- no real secrets, private hostnames, Calendar URLs, or production paths.

No additional confirmed findings remain in the implemented slice.
