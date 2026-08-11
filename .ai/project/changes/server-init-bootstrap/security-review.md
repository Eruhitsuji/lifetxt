# Security Review

Status: pending final review after verification.

## Review Scope

- `lifetxt/server_init.py`
- `lifetxt/cli.py` `server-init` wiring
- `tests/test_server_init.py`
- `docs/en/cli.md`
- `docs/deployment/ubuntu-server.md`

## Initial Findings

No confirmed finding yet. Final review will specifically re-check:

- dry-run non-mutation;
- no shell-string command execution;
- no broad passwordless `systemctl` recommendation;
- no service bind wider than `127.0.0.1`;
- no silent overwrite of production data, sudoers files, units, or proxy config;
- no real secrets, private hostnames, Calendar URLs, or production paths.
