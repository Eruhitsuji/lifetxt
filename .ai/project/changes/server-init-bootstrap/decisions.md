# Decisions

| Date | Decision | Owner | Alternatives | Reason | Follow-up |
| --- | --- | --- | --- | --- | --- |
| 2026-08-11 | Add `server-init` as a Python CLI command rather than a shell script | Codex | Shell script wrapper; external Ansible role | Reuses `server-update` validation helpers, keeps argv execution structured, and keeps the deployment surface repository-owned. | None |
| 2026-08-11 | Require explicit `service_user` and `service_group` when systemd artifacts are generated | Codex | Default to `lifetxt`; infer from current user | The runbook examples are not normative paths/users. Requiring explicit values prevents hidden username assumptions. | None |
| 2026-08-11 | Refuse differing existing files by default | Codex | Overwrite; merge/adopt automatically | Existing production data, sudoers files, units, and reverse-proxy files need deliberate adoption/repair semantics. Byte-identical files are safe no-op. | Add an explicit adoption/repair issue if needed. |
| 2026-08-11 | Generate nginx only as a placeholder artifact | Codex | Manage nginx package/site enable/reload automatically; embed supplied host/cert/auth values | Reverse proxy environments vary and may contain secrets. Initial support should produce a reviewable artifact without claiming full server management. | Apache and richer proxy workflows remain follow-up candidates. |
| 2026-08-11 | Keep health and integrity checks in the plan | Codex | Only generate files and leave verification manual | Bootstrap should end by showing the same primitives operators need for readiness, while tests mock external execution to avoid touching a real host. | None |
