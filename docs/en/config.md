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

1. built-in defaults
2. the loaded configuration file
3. the selected profile (`--profile NAME`)
4. environment overrides (an explicit allowlist, e.g. `LIFETXT_TIMEZONE`)
5. command-line flags

Inspect the result and where each value came from:

```console
$ lifetxt config effective            # merged JSON, secrets redacted
$ lifetxt config sources              # every key with its provenance
$ lifetxt config get defaults.timezone
$ lifetxt config explain web.port
```

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

Select a workspace for any command with the global `--workspace` flag:

```console
$ lifetxt --workspace work agenda
$ lifetxt workspace list
$ lifetxt workspace show work
$ lifetxt workspace files --resolved
$ lifetxt workspace validate --all
```

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

## Examples

Runnable examples live under `examples/config/`:

- `personal.lifetxt.json`
- `work.lifetxt.json`
- `project-multi-file.lifetxt.json`
