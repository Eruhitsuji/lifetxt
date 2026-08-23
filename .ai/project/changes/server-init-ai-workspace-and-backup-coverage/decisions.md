# Decisions

## Bundle #528 and #529 into one branch/PR

Both items are tightly coupled: #528's generation step needs to feed the AI
workspace's write target into `backup_paths`, and #529's diagnostic needs the same
"derive every workspace's write target" concept. Implementing them separately would
mean #528 either duplicates or waits on #529's helper. Following the precedent
already established in this session (#513/#514/#515 landed together in PR #516 for
the same reason -- shared underlying mechanism), both land in one branch and PR here.

## `ai_workspace` is opt-in, not the new default

Repository owner confirmed (AskUserQuestion) implementing item 14 now rather than
deferring it. Default-off preserves every existing `server-init` deployment's
generated config byte-for-byte; only a new, explicit choice produces the
`workspaces`-shaped config. This matches this repository's established pattern for
`server_update.py`'s own opt-in extensions (uv/conda installers, structured service
commands, etc. -- all additive, none change default behavior).

## Backup-coverage gap gets a code-level warning, not a docs-only note

Repository owner confirmed (AskUserQuestion) the code-level warning over a
documentation-only fix. A silent gap here is exactly the risk #500's own text
anticipated ("server-update should not silently omit newly configured authoritative
AI write targets from backup coverage"); a warning the operator cannot miss during
every update run is safer than depending on them having re-read the docs after
adding a workspace.

## The diagnostic never auto-expands `backup_paths`

Automatically rewriting `backup_paths` was considered and rejected: `backup_paths`
may be deliberately curated (e.g. an operator excluding a scratch/generated workspace
on purpose), and silently expanding it on every run would itself be a surprising,
unreviewed configuration change to a Security/High-assurance deployment artifact.
Reporting and leaving the decision to the operator matches this project's existing
preference for warnings over silent auto-correction in deployment tooling (e.g. the
existing risk-classification review gate in `server-update` itself asks for explicit
`--approve` rather than auto-proceeding on a high-risk update).
