# Design: server-init AI workspace generation + server-update backup-coverage diagnostic

## Context

`lifetxt/server_init.py` generates a plain-text-only `paths`/`write_file` application
config today (`_application_config()`); it never produces the `workspaces`-shaped
config `#500`'s own "AI-safe workspaces" example describes. `lifetxt/server_update.py`'s
`backup_paths` is a static list computed once at `server-init` time
(`_server_update_config()`), never re-derived or checked against the live application
config at `server-update` time.

## Part 1 — `req-server-init-ai-workspace` (#528)

### Config shape

Add to `DEFAULT_CONFIG`:

```python
"ai_workspace": {
    "enabled": False,
    "write_file": "ai-inbox.life.txt",
},
```

### `_application_config()` change

When `config["ai_workspace"]["enabled"]` is true, emit:

```json
{
  "workspaces": {
    "default": {"sources": ["<life_txt_path>", "<generated google_calendar path>"], "write_file": "<life_txt_path>"},
    "ai": {
      "sources": [
        {"path": "<life_txt_path>", "role": "readonly", "writable": false},
        {"path": "<ai_workspace write_file>", "role": "primary", "writable": true}
      ],
      "write_file": "<ai_workspace write_file>"
    }
  },
  "web": {...}
}
```

The `default` workspace's `sources` list is exactly what today's `paths` list already
contains (primary `life.txt` + the generated Google Calendar mirror, when calendar
sync is configured), so switching representations does not change what `default`
resolves to. When disabled, `_application_config()` is byte-for-byte unchanged
(verified by a regression test asserting the disabled-case output equals the
pre-change function's output).

### File-creation plan

`build_plan()` gains one more `{"kind": "file", ...}` step for the AI-inbox path
(same empty-content, same-permissions, same conflict-refusal pattern already used for
`life_txt_path`), only when `ai_workspace.enabled` is true.

### `backup_paths` wiring

`_server_update_config()` appends the AI workspace's write target to `backup_paths`
when `ai_workspace.enabled` is true -- this is the direct, generation-time instance of
`req-server-update-backup-coverage-diagnostic`'s general concern; #529's diagnostic
covers every other case (manual edits, pre-existing deployments).

## Part 2 — `req-server-update-backup-coverage-diagnostic` (#529)

### Derivation

New helper in `lifetxt/server_update.py`:

```python
def _configured_write_targets(application_config_path):
    """Every workspace write_file the live application config declares.

    Reuses lifetxt.workspace.iter_workspace_definitions() unmodified --
    resolves both `workspaces`-shaped and legacy `paths`/`write_file`
    configs identically to how the rest of lifetxt already does.
    """
    from .workspace import iter_workspace_definitions

    try:
        with open(application_config_path, "r", encoding="utf-8") as handle:
            app_config = json.load(handle)
    except (OSError, ValueError):
        return []  # can't read/parse -> nothing to compare, not a new failure mode
    targets = []
    for _name, definition in iter_workspace_definitions(app_config).items():
        write_file = definition.get("write_file") if isinstance(definition, dict) else None
        if write_file:
            targets.append(str(write_file))
    return targets
```

Read failures degrade to an empty list (no warning), not a crash or a new failure
mode -- `server-update` already reads and depends on this same file elsewhere in its
flow, so a genuinely unreadable config would already surface as a harder failure
there; this helper's own job is only to add a warning, never to gate anything.

### Comparison and reporting

Called once per `run_server_update()` invocation (both dry-run and apply), comparing
`_configured_write_targets(config["application_config"])` against
`config["backup_paths"]` (path-string comparison after normalization, matching how
the rest of `server_update.py` already compares paths). Missing targets are appended
to the existing report/log structure under a new, clearly non-fatal key (naming
convention matches other non-fatal `server-update` diagnostics already in the
codebase, confirmed by reading `run_server_update`'s existing report shape before
choosing a key name). Never raises, never affects `bundle_exit_code`-equivalent
pass/fail logic.

## Testing strategy

- `tests/test_server_init.py`: disabled-default byte-identity test (asserts
  `_application_config()`'s disabled-case output matches a captured pre-change golden
  value); enabled-case config resolved through the real
  `lifetxt.workspace.iter_workspace_definitions()` (not a hand-rolled shape
  assumption); AI-inbox file creation/conflict-refusal; `backup_paths` inclusion.
- `tests/test_server_update.py`: covered/uncovered-workspace/uncovered-legacy-write-file
  fixture matrix; confirmation the warning never changes pass/fail outcome; malformed
  application-config-file degrades to no warning rather than crashing.
- Live verification: a disposable generated deployment with `ai_workspace.enabled`,
  confirming a real `lifetxt --config <generated> mcp --workspace ai --profile assist`
  round trip works exactly as the AI-Safe Workspaces documentation describes; a
  disposable `server-update` run against a deployment with an intentionally
  uncovered workspace, confirming the warning appears and the run still succeeds.

## Security review focus

- The new file-creation step must go through the exact same conflict-refusal and
  permission-setting path every other generated artifact already uses -- no new
  file-write primitive.
- The backup-coverage diagnostic must be provably non-blocking: a malicious or
  malformed application config must not be able to turn a warning into a denial of
  service against `server-update` itself (handled by the read-failure-degrades-to-
  empty-list design above).
- No new secret, credential, or network surface is introduced by either part.
