# lifetxt 1.0.2 Release Notes

`1.0.2` is a small post-`1.0.1` usability patch release. It completes a
batch of five daily single-item CLI conveniences implemented under
[#664-#668](https://github.com/Eruhitsuji/lifetxt/issues/669) and merged
via [PR #670](https://github.com/Eruhitsuji/lifetxt/pull/670). No Format
1.0 syntax, public API, schema, or storage behavior changed.

## Highlights

- **`lifetxt reopen PATH [ID]`** ([#664](https://github.com/Eruhitsuji/lifetxt/issues/664)) --
  undoes an item's completion: removes `done:` and restores the item to
  its existing kind-aware open/default status (the same status `clone`
  gives a fresh copy). An already-open item is a deterministic no-op;
  Habit records, which log completions as multiple `done:` dates rather
  than a single completed state, are refused with an actionable
  alternative.
- **`lifetxt progress PATH ID --set VALUE`** ([#665](https://github.com/Eruhitsuji/lifetxt/issues/665)) --
  directly assigns `progress:` (a percentage or a fraction), mutually
  exclusive with the existing `--delta` increment/decrement. Unlike
  `--delta`, `--set` works even when the item has no existing
  `progress:` value, since a direct assignment needs no starting point
  to add to or subtract from.
- **`lifetxt due PATH ID DATE`** / **`--clear`** ([#666](https://github.com/Eruhitsuji/lifetxt/issues/666)) --
  sets, replaces, or clears one item's `due:` value through the same
  guarded mutation path as `done`/`progress`/`clone`.
- **Bounded relative-date shorthand** ([#667](https://github.com/Eruhitsuji/lifetxt/issues/667)) --
  `due`'s `DATE` argument (and `quick`/`add`'s pre-existing
  `--due`/`--do`/`--until` flags) accept `today`, `tomorrow`,
  `yesterday`, a weekday name, `next_week`, and signed offsets such as
  `+3d`/`-1w`/`+2m`/`+1y`, resolved through one shared, deterministic
  resolver. **This is a CLI-input convenience only**: resolution happens
  at the command-line boundary, and the value actually written to
  `life.txt` is always the resolved canonical absolute date (for example
  `due:2026-09-09`, never `due:tomorrow`). Format 1.0 itself gains no new
  syntax, and no Web API, MCP, or other machine-readable surface gained
  any relative-date semantics.
- **`lifetxt recent PATH`** ([#668](https://github.com/Eruhitsuji/lifetxt/issues/668)) --
  a read-only, newest-first view of recently created or updated items,
  composed from existing parsing, short-ID, and relative-time display.
  Defaults to ordering by `updated:` with a fallback to `created:`;
  `--updated`/`--created` select one basis explicitly with no fallback.

See [cli.md](cli.md#1313-reopen) (and the following `due`/`recent`
sections) and [new-cli-workflows.md](new-cli-workflows.md) for full
command reference and examples.

## Compatibility

No breaking change. All five commands are new, additive surfaces reusing
existing guarded mutation, target-resolution, and read primitives; no
existing command's default behavior, output shape, or machine-readable
contract changed.

## Upgrading

No migration is required. Existing `life.txt` files, configuration, and
scripts against `1.0.1` continue to work unchanged under `1.0.2`.

## Release status

- **`v1.0.2`**: prepared at this release-preparation commit
  (see [#669](https://github.com/Eruhitsuji/lifetxt/issues/669) for the
  full preparation and publication checklist). Version metadata bumped
  `1.0.1` -> `1.0.2` in `pyproject.toml`/`lifetxt/__init__.py`; the MCP
  server and Web API version surfaces both derive from
  `lifetxt.__version__` and were confirmed to report `1.0.2` before tag
  creation.

## Installation smoke

```text
python -m lifetxt --help
lifetxt --help
python -m lifetxt check examples/minimal_life.txt
```

Per the reduced Stable-release gate established under
[#454](https://github.com/Eruhitsuji/lifetxt/issues/454) and reused for
this patch release, the release-critical minimum is the same clean
wheel/sdist build, fresh-environment install, and representative core
smoke recorded for `1.0.0`/`1.0.1` in
[Stable Release Artifact Verification](stable-release-artifact-verification.md).
