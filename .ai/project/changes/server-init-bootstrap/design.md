# Design

## Summary

`server-init` adds the initial-construction counterpart to `server-update`.
The command loads a deployment JSON file, builds a deterministic plan, annotates
filesystem steps as create/no-op/conflict, and mutates only when `--yes` is
present.

## Interfaces and Contracts

- ADDED: `lifetxt server-init --server-config PATH [--yes] [--format text|json]`.
- ADDED: `lifetxt.server_init.load_config`, `build_plan`, `run_server_init`.
- ADDED: bootstrap config keys for `install_root`, `data_root`, `python`,
  `installer`, `extras`, `service_user`, `service_group`, `web`,
  `calendar_sync`, `systemd`, `service_control`, `reverse_proxy`,
  `integrity_checks`, and `validation_commands`.
- ADDED: generated `server-update.json` using the existing `server_update`
  installer and integrity-check builders.

## Safety Model

- Dry-run is the default and only inspects the filesystem to classify planned
  paths.
- Source and data roots are normalized and refused when equal or nested inside
  each other.
- `--yes` creates missing directories/files and runs planned structured argv
  commands. It does not overwrite differing existing files.
- Generated files use exclusive create (`O_CREAT|O_EXCL`) so a late-created
  destination is not silently clobbered.
- Systemd service artifacts require explicit `service_user` and
  `service_group`; no username is inferred from documented examples.
- `web.bind` is constrained to `127.0.0.1`.
- Service-control generation creates an allowlist wrapper for only
  `is-active`, `stop`, and `start` on the configured lifetxt units.
- Nginx output keeps placeholder host/certificate values and proxies only to
  loopback.
- Health verification is included in the apply plan only when explicitly
  configured or when the same plan starts services; the generated
  `server-update.json` still carries the default health URL for future updates.

## Alternatives

- A shell script wrapper was rejected because it would duplicate existing
  Python validation and make argv safety harder to test.
- An all-powerful setup command that installs packages, manages firewalls, DNS,
  certificates, or VPNs was rejected as beyond lifetxt's deployment boundary.
- Silent adoption of existing files was rejected. Matching files are no-op;
  differing files require a future explicit adopt/repair workflow.

## Follow-up Candidates

- User-level/rootless systemd.
- Apache generation in addition to nginx.
- Backup retention/pruning defaults.
- Release/tag-based deployment defaults instead of tracking a branch.
- Import/adopt an existing manual Ubuntu deployment.
- Uninstall/decommission workflows.
- Deployment config schema/versioning.
- Non-Ubuntu Debian/Linux support.
- Containerized deployments.
