# Configuration and Workspaces

lifetxt reads a JSON configuration file that selects which life.txt files it
reads and writes, plus defaults such as timezone and identity. This guide is
task-oriented; for per-key metadata run `lifetxt config explain <path>`.

## Discovery order

The configuration file is located in this order:

1. `--config PATH` on the command line.
2. `LIFETXT_CONFIG` environment variable.
3. `.lifetxt.json` in the current directory.
4. `lifetxt.config.json` in the current directory.

If none are found, lifetxt falls back to reading `life.txt`.

## Minimum configuration

The smallest useful configuration keeps the historical top-level form:

```json
{
  "paths": ["life.txt"],
  "write_file": "life.txt",
  "defaults": { "timezone": "Asia/Tokyo" }
}
```

Top-level `paths` and `write_file` are treated as an implicit workspace named
`default`. Nothing needs to change to keep this working.

## Precedence

Effective values are resolved from lowest to highest priority:

1. built-in defaults (the same values `lifetxt config init` writes)
2. the loaded configuration file
3. the selected profile (`--profile NAME`)
4. environment overrides (an explicit, documented allowlist -- not every key)
5. command-line flags (applied by each command after this layer resolves)

The environment allowlist currently has five entries:

| Variable | Overrides |
| --- | --- |
| `LIFETXT_TIMEZONE` | `defaults.timezone` |
| `LIFETXT_PERSON` | `defaults.person` |
| `LIFETXT_WEB_HOST` | `web.host` |
| `LIFETXT_WEB_PORT` | `web.port` |
| `LIFETXT_DEFAULT_WORKSPACE` | `default_workspace` |

Any other `LIFETXT_*` variable you may see referenced elsewhere (for example
`LIFETXT_CONFIG`, or a `*_env`-referenced secret variable) is not part of this
precedence layer -- it is consulted directly by the feature that needs it,
not merged into the effective config object.

Inspect the result and where each value came from:

```console
$ lifetxt config effective            # merged JSON, secrets redacted
$ lifetxt config sources              # every key with its provenance
$ lifetxt config get defaults.timezone
$ lifetxt config explain web.port
```

`config sources` prints one row per effective key, its value, and where it came
from (`builtin-default`, `config:<path>`, `profile:<name>`, or
`env:<VARIABLE>`):

```console
$ lifetxt config sources
defaults.timezone       config:.lifetxt.json  "Asia/Tokyo"
web.port                builtin-default       8000
```

A key set through the environment reports the variable name as its source
(`env:LIFETXT_TIMEZONE`), which is how you can tell an override is active
without printing environment variables yourself.

## Named workspaces

A workspace is a named set of source files plus a write target. Define them
under `workspaces` and pick a default with `default_workspace`:

```json
{
  "default_workspace": "personal",
  "workspaces": {
    "personal": {
      "sources": [
        "life.txt",
        { "path": ".generated/calendar.life.txt", "role": "generated" }
      ],
      "write_file": "life.txt"
    },
    "work": {
      "sources": [{ "path": "work.life.txt", "role": "primary", "required": true }]
    }
  }
}
```

When a workspace has more than one writable source, every writable Web, MCP,
or multi-file server operation must name `write_file` explicitly. lifetxt does
not guess the first source, because that can silently write to the wrong file.
Single-source workspaces remain implicit, and read-only operations may still
inspect multiple sources. Authoritative writes are also rejected before
mutation when duplicate IDs exist across the loaded sources; repair the IDs
first so each workspace ID is unique.

Select a workspace for any command with the global `--workspace` flag:

```console
$ lifetxt --workspace work agenda
$ lifetxt workspace list
$ lifetxt workspace show work
$ lifetxt workspace files --resolved
$ lifetxt workspace validate --all
```

Several *unconfigured* default file paths (currently the notification watch
state file; see `lifetxt notify --watch` in
[new-cli-workflows.md](new-cli-workflows.md)) insert the active workspace's
name before the extension -- `.cache/lifetxt/notifications.json` becomes
`.cache/lifetxt/notifications-work.json` under workspace `work` -- so two
named workspaces defined in the same configuration file do not silently share
one state file. This only applies to the built-in default; an explicitly
configured path (`notifications.state_file`, `--state-file`) is always used
exactly as written, with no workspace name inserted. `lifetxt path` reports
the same resolved path `notify --watch` would actually use, so you can check
which file applies before relying on it.

## Source manifest fields

Each entry in `sources` is a path string or an object. The object form supports:

| Field            | Default          | Meaning                                            |
| ---------------- | ---------------- | -------------------------------------------------- |
| `path`           | (required)       | File, directory, or glob.                          |
| `role`           | `primary`        | `primary`, `input`, `generated`, `archive`, `readonly`, `reference`, `ticket_event`, `time_entry`. |
| `required`       | `false`          | Missing required sources are an error.             |
| `writable`       | role-dependent   | Read-only for generated/archive/readonly/reference. |
| `default_visible`| role-dependent   | Hidden by default for generated/archive.           |
| `format`         | `life`           | Source format hint.                                |
| `priority`       | `100`            | Lower numbers sort first in the input order.       |
| `watch`          | `true`           | Whether file watchers should observe it.           |
| `privacy`        | `normal`         | Privacy classification for redaction.              |
| `generated_by`   | `null`           | Tool that produces a generated source.             |
| `exclude`        | `[]`             | Glob patterns removed from directory/glob results. |

## Workspace safety limits

Workspace resolution enforces `workspace.max_total_source_bytes` across unique
resolved source files. The default is `67108864` bytes (64 MiB). Raise it only
after narrowing broad globs or excluding generated directories:

```json
{
  "workspace": { "max_total_source_bytes": 67108864 }
}
```

Link-cycle detection runs before glob expansion on source path prefixes and, for
recursive globs, on directory links under the static glob root. The total-size
limit is checked after deterministic expansion by stat'ing each unique physical
source file.

## Path resolution

Relative source paths resolve against the **configuration file's directory**,
not the current working directory, so a workspace behaves identically wherever
you run lifetxt from. Globs expand deterministically (sorted). Resolution
reports diagnostics for missing required sources (`WS001`), duplicate physical
files (`WS002`), paths outside the config directory (`WS003`), unknown roles
(`WS005`), unusable write targets (`WS006`/`WS007`), self-referential
symlink/junction cycles (`WS014`), total source bytes above
`workspace.max_total_source_bytes` (`WS015`), and an invalid size limit setting
(`WS016`).

## Profiles

Profiles are named overlays merged above the base configuration:

```json
{
  "profiles": {
    "remote": { "defaults": { "timezone": "UTC" } }
  }
}
```

```console
$ lifetxt config effective --profile remote
```

## Inspecting and validating configuration

`lifetxt config init [-o PATH] [--force]` writes a starter file containing the
*full* built-in template (every top-level section `config_template()`
defines, not a minimal skeleton) plus a printed reminder of the precedence
order above. Editing it down to only the sections you need is expected --
nothing requires every key to be present.

`lifetxt config show` prints the raw loaded file as JSON (no defaults, no
profile, no environment merge -- exactly what is on disk plus a public view of
`_path`). `lifetxt config revision` prints that file's exact SHA-256 content
hash, the same value `config set|unset|migrate --expected-revision` compares
against.

`lifetxt config check [--json]` validates structure and credential policy
without needing `jsonschema` installed, and additionally validates the whole
document against the published `config-v1.schema.json` when `jsonschema` is
available. It reports one of these codes per problem:

| Code | Severity | Meaning |
| --- | --- | --- |
| `C001` | error | `config_version` is newer than this build supports; writes are refused until you upgrade. |
| `C002` | error | `config_version` is missing, not an integer, or less than 1. |
| `C003` | error | A key that looks like a credential (containing `password`, `token`, `secret`, or `passwd`) holds a plaintext string instead of a `*_env` reference. |
| `C005` | error | `workspaces` is present but is not an object. |
| `C006` | error | A workspace definition has no `sources`, or a source entry is malformed. |
| `C007` | warning | A deprecated key is set (currently only `generated_paths`; see its replacement in `config explain generated_paths`). |
| `C008` | error | The document fails `config-v1.schema.json` validation (only reported when `jsonschema` is installed). |

Any `error`-severity finding makes the file unwritable (`config set`/`unset`/
`migrate` refuse to write it) until fixed; `warning`-severity findings do not
block a write. `config check` also reports any retained `.rejected*`
candidates from previously refused writes (see below), since those sit beside
the file and are easy to forget about.

`lifetxt config migrate [--dry-run] [-o PATH] [--expected-revision HASH]`
converts a legacy top-level `paths`/`write_file` configuration into the
versioned `workspaces.default` form and sets `config_version` to `1`, without
changing any other value. `--dry-run` lists the planned changes and writes
nothing. A configuration already on the current version and shape reports
"Configuration is already current; no changes." and exits successfully.

## Editing configuration safely

Read and write individual keys without hand-editing JSON:

```console
$ lifetxt config set web.port 8080
$ lifetxt config unset web.port
```

Values are parsed as JSON when possible (so `8080` is a number and `"text"` a
string), otherwise stored as a string.

Configuration writes are compare-and-set by default when the command writes
back to the file it loaded. The CLI reads the current file revision and passes
it as the write precondition, so a concurrent edit is refused instead of being
overwritten.

Set `config.write.require_revision` when every configuration write must carry a
revision precondition:

```json
{
  "config": { "write": { "require_revision": true } }
}
```

This does not change normal `lifetxt config set|unset|migrate` use against the
loaded file, because those commands discover the revision automatically. It
does refuse writes where no revision is available, such as writing to a
different `--output` file without `--expected-revision`.

Set `config.write.audit_log` to keep a durable, bounded record of configuration
write attempts beyond what the bounded `.bak`/`.rejected` rotation retains:

```json
{
  "config": {
    "write": {
      "audit_log": ".cache/lifetxt/config-write-audit.jsonl",
      "audit_max_bytes": 5242880
    }
  }
}
```

Each accepted or refused write appends one line recording only the timestamp,
path, outcome, and revisions involved -- never configuration content or key
values, so it cannot leak a secret-referencing setting. The file is trimmed
from the oldest end once it exceeds `audit_max_bytes`. Leaving `audit_log`
unset disables the trail entirely.

## Update checks

`lifetxt update-check` compares the running version against the latest
GitHub Release (or tag, if no Release is published) for a repository. The
default is this project's own repository, but a fork should point checks at
itself instead of silently comparing against upstream:

```json
{
  "update": { "repository": "your-github-username/your-fork" }
}
```

The `--repo OWNER/NAME` flag overrides this for a single invocation without
changing the stored default.

## Credentials

Never store passwords or tokens directly in configuration. Reference an
environment variable name instead — for example SMTP credentials use
`smtp_pass_env: "LIFETXT_SMTP_PASS"`. `config effective`, `config sources`,
and support bundles redact any key that looks like a secret.

Two different, deliberately different-width checks apply here, and it is
worth knowing both exist:

- **Display redaction** (`config effective`, `config sources`, support
  bundles) replaces the value of any key whose name contains `password`,
  `token`, `secret`, or `pass` with `***redacted***`, unless the key ends in
  `_env` (an environment-variable *reference* is safe to show). This is
  intentionally broad -- it also catches a key like `api_pass`.
- **`config check`'s `C003` error** only fires on `password`, `token`,
  `secret`, or `passwd` (not the bare substring `pass`). A key such as
  `api_pass: "hunter2"` is therefore redacted on display but does **not**
  fail `config check` -- it is still a plaintext secret sitting in the file
  on disk. Prefer the documented `*_env` convention over relying on either
  check to catch every naming choice.

An explicit SMTP port (not a secret; e.g. `587` for STARTTLS submission) is
supported the same way across every SMTP-delivery surface: `reports.*.email.
smtp_port`, `notifications.email.smtp_port`, and digest's `--smtp-port` flag.
All three ultimately reach the one shared `lifetxt.mail_delivery` transport,
so the port is validated (an integer from 1 to 65535) before any network
connection is attempted, and omitting it entirely preserves the effective
default SMTP port unchanged.

## Ticketing configuration

Development-ticket behavior (`lifetxt ticket ...`) reads several keys under
`ticketing`. Full workflow, custom-field, and write-safety behavior is
documented in [tickets.md](tickets.md) and [ticket-projects.md](ticket-projects.md);
this table covers the plain configuration surface:

| Key | Default | Meaning |
| --- | --- | --- |
| `ticketing.id_prefix` | `"TK"` | Prefix for generated ticket ids, e.g. `TK-1`. Keep distinct from task id prefixes. |
| `ticketing.required_fields` | `[]` | Ticket fields that must be present; missing ones are reported as `TK005` errors. |
| `ticketing.trackers` | `["bug", "feature", "task", "support"]` | Allowed ticket tracker values. |
| `ticketing.priorities` | `["low", "normal", "high", "urgent", "immediate"]` | Allowed ticket priority values, low to high. |
| `ticketing.severities` | `["trivial", "minor", "major", "critical", "blocker"]` | Allowed ticket severity values, least to most severe. |
| `ticketing.components` | `[]` | Allowed ticket component values. Empty means no restriction. |
| `ticketing.defaults.tracker` | `"task"` | Tracker assumed for `ticket new` when none is given. |
| `ticketing.defaults.priority` | `"normal"` | Priority assumed for `ticket new` when none is given. |

All eight keys are registered, so `lifetxt config explain ticketing.trackers`
(and the others) reports type, default, and description directly.

## Remote Safe Mode configuration

Remote Safe Mode's full configuration surface (`remote.enabled`,
`remote.principals`, rate limiting, audit logging, browser sessions, and the
`remote.allow_multi_worker` deployment-topology acknowledgment) is documented
in [remote.md](remote.md) rather than duplicated here, since enabling it also
requires understanding authentication and permission scopes that are specific
to that surface. Every `remote.*` key is registered; `lifetxt config explain
remote.<key>` works for all of them.

## Transaction recovery authorization

Local transaction administration can use `transactions.require_operator_authorization`
and `transactions.authorized_operators` as a single-operator allow-list. Remote
or multi-user recovery is stricter: authorization is derived from authenticated
principal context, not from the caller-provided `--operator` string. Use
`transactions.require_authenticated_recovery_authorization`,
`transactions.recovery_authorized_roles`,
`transactions.recovery_required_scopes`,
`transactions.recovery_allowed_projects`, and
`transactions.require_destructive_recovery_approval` to require roles, recovery
scopes, project limits, and separate approval for destructive restore actions.

## Complete key reference

Every key below is registered with the authoritative metadata registry, so
`lifetxt config explain <key>` returns its type, default, environment
override (if any), and a description for each. This table is grouped by area
rather than alphabetically; keys already covered by their own section above
or by a linked document are summarized here for completeness rather than
re-explained.

| Area | Keys |
| --- | --- |
| Core | `config_version`, `default_workspace`, `paths`, `write_file` |
| Config writes | `config.write.require_revision`, `config.write.audit_log`, `config.write.audit_max_bytes` |
| Update checks | `update.repository` |
| Capture presets | `capture.presets`, `capture.presets.*.type`, `capture.presets.*.status`, `capture.presets.*.project`, `capture.presets.*.tags`, `capture.presets.*.priority` |
| Workspaces | `workspaces`, `workspaces.*.sources`, `workspaces.*.write_file`, `workspace.max_total_source_bytes` |
| Profiles | `profiles` |
| Defaults | `defaults.timezone`, `defaults.person` |
| Web server | `web.host`, `web.port` |
| Notifications | `notifications.email.smtp_pass_env`, `notifications.email.smtp_port` |
| Identity | `ids.auto` |
| Editing | `editor` |
| Attachments | `attachments.root`, `attachments.max_files`, `attachments.max_bytes`, `attachments.max_file_bytes`, `attachments.ignores`, `attachments.allowed_mime`, `attachments.blocked_mime`, `attachments.open_state_file`, `attachments.remote_source_root`, `attachments.remote_chunk_bytes` |
| Transactions | `transactions.policy_file`, `transactions.admin_audit_file`, `transactions.preflight_on_startup`, `transactions.terminal_retention_days`, `transactions.max_transactions`, `transactions.max_total_bytes`, `transactions.max_transaction_bytes`, `transactions.require_private_permissions`, `transactions.allow_newer_read_only`, `transactions.evidence_include_paths`, `transactions.require_operator_authorization`, `transactions.authorized_operators`, `transactions.require_authenticated_recovery_authorization`, `transactions.recovery_authorized_roles`, `transactions.recovery_required_scopes`, `transactions.recovery_allowed_projects`, `transactions.require_destructive_recovery_approval` |
| Clock skew (Remote/Web writes) | `clock.skew_warning_seconds`, `clock.skew_reject_seconds`, `clock.require_remote_write_time`, `clock.client_time_header` |
| Remote Safe Mode | see [remote.md](remote.md); every `remote.*` key is registered |
| Projects | `projects`, `projects.*.aliases` (see [projects.md](projects.md)) |
| Ticketing | see the table above; full behavior in [tickets.md](tickets.md) |
| Inbox | `inbox.proposals_file` (see [inbox.md](inbox.md)) |
| Messaging groups | `groups` (see [messaging.md](messaging.md)) |
| Saved views | `saved_views` (see [query.md](query.md)) |
| Deprecated | `generated_paths` -- replaced by per-source `role: generated` sources and `sync_ics.generated_paths` |

This registry does not yet cover every key `lifetxt config init` writes into
the starter template. Sections such as `user`, `users`, `teams`, `tags`,
`message`, `timer`, `tui`, most of `notifications` (beyond the one key
above), `api`, `ids.key`/`ids.prefixes.*`, most of `web` (beyond `host`/
`port`), `views`, `templates`, and `sync_ics` exist and are read by their
respective features, but `config explain` on one of their keys reports "No
registered metadata" rather than failing silently -- it fails loudly instead
of guessing. Run `lifetxt config init -o /tmp/example.lifetxt.json` (any
throwaway path; `config init` always writes a file, it has no stdout mode) or
inspect `examples/config/*.lifetxt.json` to see their current shape and
defaults directly until they gain registry entries.

## Examples

Runnable examples live under `examples/config/`:

- `personal.lifetxt.json`
- `work.lifetxt.json`
- `project-multi-file.lifetxt.json`

## Periodic Markdown report profiles

Named periodic report profiles live under the optional top-level `reports`
object. Each profile requires `period` (`daily`, `weekly`, or `monthly`) and
may set `output`, `title`, `project`, `type`, `tag`, `open`, `mode`, and
`frontmatter`. A profile that adds `sections` opts into Report v2 (a
composition layer over existing lifetxt aggregations) and may also set
`format` (`markdown`/`json`/`html`), `audience` (`private`/`external`),
`compare` (`previous`), and `scope` (report-wide `project`/`tag`/`type`/
`status`/`person`/`open` filter applied once before any section provider
runs; legacy top-level `project`/`type`/`tag`/`open` are accepted as
compatibility aliases into `scope`). Any profile, v1 or v2, may add `email` (`to`,
`subject`, `smtp_host_env`, `smtp_port`, `smtp_user_env`, `smtp_pass_env`) to
support `lifetxt report send`; `smtp_port` is an optional explicit integer
port (e.g. `587` for STARTTLS submission) and omitting it preserves the
existing default SMTP port. Use `lifetxt config explain reports.<name>.<key>`
to inspect the registered metadata for a concrete profile key.

See [reports.md](reports.md) for the complete profile contract, output path
placeholders, generated frontmatter, and Obsidian/Notion workflows. A runnable
example is also provided at `examples/report_profiles.config.json`.

`lifetxt config init` intentionally does not add an empty `reports` object:
lifetxt has no built-in report profile or destination, so there is no meaningful
default profile to write. The optional surface is instead covered by the
published `config-v1` schema and the configuration registry used by
`config explain`.

This is an additive configuration-v1 extension. Existing configurations without
`reports` keep their previous behavior and require no migration. Removing the
optional `reports` section is the downgrade path and restores the pre-feature
configuration behavior.

## Named capture presets

Named `quick`/`q`/`add` capture defaults live under the optional top-level
`capture.presets` object:

```json
{
  "capture": {
    "presets": {
      "work-task": {
        "type": "T",
        "project": "work",
        "tags": ["work"],
        "priority": "normal"
      },
      "idea": {
        "type": "N",
        "tags": ["idea"]
      }
    }
  }
}
```

```sh
lifetxt quick --preset work-task "Prepare proposal"
lifetxt add --preset idea "Try local-first sync"
```

A preset may set `type`, `status`, `project`, `tags`, and `priority` --
exactly the fields `quick` already accepts as `--type`/`--status`/
`--project`/`--tag`/`--priority`. It is a defaults layer, never an invisible
override:

```text
existing config defaults < selected capture preset < explicit shorthand / explicit CLI arguments
```

An explicit `--project`/`--priority`/`--status`/`--type` flag or a capture
shorthand sigil (`@`/`!`/`^`) for the same field always wins over the preset.
`#tag` sigils and `--tag` values are merged with the preset's `tags` and
deduplicated rather than replaced. `q` and `add` accept `--preset` too,
since both are aliases of the same `quick` command contract. An unknown
preset name fails loudly and lists every configured preset name; a malformed
preset definition (an unsupported field, an empty value, or `tags` that is
not a non-empty array of strings) is rejected by configuration validation
rather than silently ignored.

Use `lifetxt config explain capture.presets` (or
`capture.presets.<name>.<field>` for one field's registered metadata) to
inspect the contract.

`lifetxt config init` intentionally does not add an empty `capture.presets`
object, for the same reason `reports` above does not: there is no meaningful
default preset to write. This is an additive configuration-v1 extension.
Existing configurations without `capture` keep their previous behavior and
require no migration; removing the optional `capture.presets` section is the
downgrade path. This does not replace the existing `template` command, which
remains the tool for fixed/multi-line record generation; capture presets are
for variable-title, same-metadata `quick`/`add` captures.

## Configurable TUI key bindings

`tui.bindings` is a small, explicit overlay on top of the selected
`tui.keymap` preset (`prompt`, `vim`, or `arrows`) for the interactive
`lifetxt tui` workspace:

```text
selected built-in tui.keymap preset  <  tui.bindings overrides
```

```json
{
  "tui": {
    "keymap": "vim",
    "bindings": {
      "move_up": ["k"],
      "move_down": ["j"],
      "open": ["enter", "l"],
      "done": ["x"],
      "search": ["/"],
      "help": ["?"],
      "quit": ["q"]
    }
  }
}
```

Each key in `tui.bindings` must be one of a fixed set of action ids: `move_up`,
`move_down`, `first`, `last`, `open`, `toggle_mark`, `done`, `search`,
`command`, `reload`, `help`, `quit`. The value is one key name or an array of
key names using the same deterministic symbolic spellings the TUI's own key
normalization already produces -- `j`, `k`, `g`, `G`, `enter`, `space`, `esc`,
`ctrl-p`, `up`, `down`, `home`, `end`, and so on. Unmentioned actions keep the
selected keymap's built-in key(s); a preset applies no `tui.bindings` overlay
of its own for actions the configuration does not mention.

This creates no new input or command engine: every action still invokes the
exact same existing TUI handler it always did (`quick`/`add`'s capture path is
unrelated). Only which physical key reaches which handler is configurable.

Safety and validation:

- A key already bound to two different actions in the same mode is rejected
  before the TUI starts, naming both actions.
- An unknown action id or an unsupported key name is rejected rather than
  silently ignored.
- Duplicate key aliases for the same action are deduplicated.
- `edit` (`e`), `undo` (`u`), the page-move keys, the view-cycle key (`Tab`),
  and the required cancel/exit path (`Esc`, and `Ctrl-C`, which is never
  routed through this registry at all) stay hard-coded and cannot be
  reassigned through `tui.bindings` in this first slice -- a custom map can
  never make the TUI impossible to exit or cancel.
- The `prompt` keymap has no nav-mode bindings of its own (it never leaves
  the input bar), so `tui.bindings` has no effect there.
- The non-interactive/plain dashboard (`lifetxt tui --plain`, or any
  non-TTY invocation) has no keyboard interaction and is unaffected by
  `tui.bindings`.

`?` (when the help reference is not already open) shows the *effective*
bindings, generated from the resolved configuration rather than a second,
separately maintained copy of the default key list -- so help can never
describe a key that no longer does what it says.

See [cli.md](cli.md#custom-key-bindings) for the full action list and a
worked example, and use `lifetxt config explain tui.bindings.*` to inspect
the registered metadata for one action's contract.

This is an additive configuration-v1 extension. Existing configurations
without `tui.bindings` behave exactly as before; the existing `tui.keymap`
values remain the authoritative base preset and are not renamed or
deprecated. Removing the optional `tui.bindings` section is the downgrade
path.

## Generic custom fields

The optional top-level `custom_fields` object declares typed, validated
metadata for ordinary (non-ticket) life.txt records -- a Journal rating, a
Note's energy level, a household or research classification -- without
changing the life.txt grammar or turning its open custom-key model into a
closed schema:

```json
{
  "custom_fields": {
    "energy": {
      "type": "enum",
      "values": ["low", "medium", "high"],
      "kinds": ["J", "N"],
      "filterable": true
    },
    "rating": {
      "type": "number",
      "minimum": 0,
      "maximum": 5,
      "kinds": ["J"],
      "filterable": true
    }
  }
}
```

```text
[N] N "Afternoon energy" energy:high
[N] J "Daily review" rating:4.5
```

Each field name maps to a definition object (or a bare type string, e.g.
`"energy": "string"`, as shorthand for `{"type": "string"}`). Supported
metadata:

| Key | Meaning |
| --- | --- |
| `type` | One of `string`, `integer`, `number`, `boolean`, `date`, `datetime`, `duration`, `enum`. |
| `label` | Optional user-facing label; defaults to the field name. |
| `description` | Optional explanation. |
| `repeatable` | Boolean; whether the field may appear more than once on one item. |
| `required` | Boolean; whether an applicable item must include the field. |
| `enum` / `values` | Allowed values, for `type: enum` (`values` is an accepted alias). |
| `minimum`, `maximum` | Numeric bounds, for `integer`/`number` types. |
| `min_length`, `max_length` | Length bounds on the normalized value. |
| `pattern` | A regular expression the normalized value must match. |
| `kinds` | Life.txt record kinds (`T`/`E`/`D`/`R`/`H`/`N`/`S`/`M`/`J`) the field applies to. Omitted means every ordinary kind. |
| `projects` | Projects the field applies to. Omitted means every project. |
| `filterable` | Boolean, default `false`; see Query behavior below. |

This is deliberately the smallest generic counterpart to the much richer
`ticketing.custom_fields` registry (below); both share one typed-value
implementation, so an equivalent `type`/`minimum`/`pattern`/... input is
parsed and validated identically in either registry. Privacy levels,
tracker/role scoping, and other ticket-workflow-specific metadata are
intentionally not part of the generic registry -- those stay ticket-specific.

`record:ticket` items are never governed by `custom_fields`; they remain
governed by `ticketing.custom_fields` only, and a generic definition never
reinterprets or overrides a ticket-specific one.

### Validation behavior

A field definition applies to an ordinary item when the item's kind matches
`kinds` (if given) and its `project:` matches `projects` (if given). For an
applicable item:

- a declared field's key no longer produces the generic "custom key, it will
  be preserved" warning -- it is recognized, not merely tolerated;
- its value(s) are normalized and validated against `type` and every
  constraint (`enum`/`minimum`/`maximum`/`min_length`/`max_length`/`pattern`);
- `repeatable: false` (the default) rejects more than one value;
- `required: true` reports an error when the item lacks the field.

An **undeclared** custom key is unaffected: it keeps today's exact
preservation and warning behavior. A **declared** field used on an item
outside its own `kinds`/`projects` scope is also left untouched -- it does
not silently gain stronger semantics just because the same key name is
declared somewhere else in the registry.

### Query behavior

Only definitions with `filterable: true` become dynamic Query fields,
recognized automatically by the shared query language (`field:value` /
`field=value` equality/membership matching) and therefore by every surface
built on it -- CLI `query`, Saved Views, MCP `run_query`, and Web/TUI Saved
Views -- with no separate implementation on any of those surfaces:

```sh
lifetxt query 'energy:high'
lifetxt view run energetic-notes
```

A configured field left `filterable: false` (the default) remains validated
metadata but is **not** accepted as a Query field name; querying it still
reports Q001 (unknown field), the same as any undeclared key. Numeric/date
comparison operators (`<`, `>`, and so on) for custom fields are out of
scope for this first slice; only equality/membership matching is supported.

Use `lifetxt config explain custom_fields.*.type` (or any other definition
key) to inspect the registered metadata contract.

This is an additive configuration-v1 extension. Existing configurations
without `custom_fields` behave exactly as today, and existing arbitrary
custom detail keys remain legal and preserved. Adding an entry intentionally
opts that field into stronger validation for applicable ordinary items; it
does not change the meaning of any existing `ticketing.custom_fields`
configuration. No life.txt file migration is required, since the stored
syntax remains ordinary `key:value` detail metadata -- an older lifetxt
version will preserve the custom detail text but will not know the new
configuration semantics. Removing the optional `custom_fields` section is
the downgrade path.
