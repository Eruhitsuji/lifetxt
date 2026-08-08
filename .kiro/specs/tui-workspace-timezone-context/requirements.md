# Requirements Document

> **Authoritative copy lives in the change package, not here.**
>
> For non-trivial work, and for anything at High or Regulated assurance, this content is distilled
> into `.ai/project/changes/<change-id>/requirements.yml`, which is what reviewers and the other
> executors read. See `.ai/project/changes/README.md` for when a change package is required at
> all — below that threshold, the issue and pull request carry the reasoning and no package is
> needed.
>
> The formats differ on purpose: this file is Markdown for drafting, the change package is YAML
> for the standard's traceability records. Distilling is a manual step, so this file and the
> package can drift. The package wins.

## Project Description (Input)

Fix the CLI/TUI timezone-context installer (`lifetxt/safety_compat_v2.py`
`_patch_cli_timezone_installer`, mirrored in `lifetxt/runtime_safety_v2.py`
`install_cli_timezone_context`) so it honors `--workspace`: today it re-loads
raw config and only scans legacy top-level `config_paths()` / raw `--config`
parsing for a `timezone:` file directive, completely ignoring `--workspace`,
so a named-workspace user's actual resolved primary source is not consulted
and the wrong (or no) file-level timezone directive is found. This silently
affects `lifetxt tui` too, since `tui` goes through the same legacy CLI
dispatch and its periodic clock (`lifetxt/tui_app.py` using
`timezone_policy.now()`) and any notification timezone classification
(`lifetxt/notifier.py` using `timezone_policy.local_now_naive()`) both read
the same broken global timezone context. Also add a visible indicator of the
active workspace name (already resolved into `config['_active_workspace']` by
`cli.py` `_maybe_apply_workspace`) in the TUI title/status so users can see
`--workspace` took effect, matching `todo.md` P1 "Configuration and Workspace
Foundation" item: "Thread `--workspace` into the TUI and add per-workspace
timezone/notification context." Web/MCP/Remote surfaces are explicitly out of
scope for this iteration and will be filed as separate follow-up work.

## Introduction

lifetxt's CLI accepts a global `--workspace <name>` flag that already resolves
a named workspace's input and write paths so every command, including
`lifetxt tui`, reads and writes the correct files for that workspace. The
process-wide timezone context established before any command runs is resolved
separately, from the raw, workspace-unaware configuration, so it does not
consult the active workspace's actual source files for a file-level
`timezone:` directive. This silently affects the TUI's own clock and any
notification timezone classification, both of which consume that same
process-wide timezone context. Separately, the TUI gives no visible
indication of which workspace is active, so users cannot confirm that
`--workspace` took effect. This feature makes the timezone-context resolution
workspace-aware and adds a visible active-workspace indicator to the TUI.

## Boundary Context

- **In scope**: CLI-wide timezone-context resolution (used by every legacy
  CLI command, including `tui`), and the TUI's display of the active
  workspace name.
- **Out of scope**: Web API, MCP, and Remote surface timezone/workspace
  context handling (tracked as separate follow-up work); adding a new
  per-workspace `timezone` configuration key (workspaces gain no new declared
  setting in this iteration -- only the existing file-level `timezone:`
  directive and existing default-timezone configuration are resolved using
  the correct workspace-selected candidate files); changing the existing
  timezone precedence order itself; in-session workspace switching inside a
  running TUI.
- **Adjacent expectations**: This feature relies on the existing workspace
  resolution behavior and the existing timezone precedence order (CLI value,
  then file directive, then configured default, then host timezone) without
  changing either; it only changes which files are consulted as the "file
  directive" candidates when a workspace is active.

## Requirements

### Requirement 1: Workspace-aware timezone-directive resolution

**Objective:** As a lifetxt user who organizes life.txt files into named
workspaces, I want the CLI to look for a file-level `timezone:` directive
inside my active workspace's own sources, so that the timezone context
matches the workspace I am working in rather than an unrelated file.

#### Acceptance Criteria

1. When the CLI is invoked with `--workspace <name>` and the named workspace
   resolves successfully, the CLI shall search for the file-level
   `timezone:` directive only among that workspace's resolved input files, in
   the workspace's resolved priority order.
2. When the CLI is invoked without `--workspace` and the configuration
   declares no `workspaces` section and no `default_workspace`, the CLI shall
   search for the file-level `timezone:` directive using the same candidate
   files it uses today, so existing non-workspace configurations are
   unaffected.
3. When the CLI is invoked without an explicit `--workspace` but the
   configuration declares `workspaces` or `default_workspace`, the CLI shall
   search for the file-level `timezone:` directive among the resolved default
   workspace's input files.
4. If the workspace name given to `--workspace` does not exist, the CLI shall
   report the same error it reports today for an unknown workspace name, and
   shall not silently fall back to a different timezone source.
5. While resolving the workspace-selected candidate files, the CLI shall
   preserve the existing timezone precedence order unchanged: an explicit
   CLI-supplied timezone first, then a file directive, then the configured
   default timezone, then the host timezone.
6. The CLI shall apply workspace-aware timezone-directive resolution to every
   command dispatched through the CLI, including `lifetxt tui`, `lifetxt tui
   --plain`, and the dependency-free dashboard shown when the terminal is not
   interactive.

### Requirement 2: Consistent timezone context for the TUI clock and notifications

**Objective:** As a user running `lifetxt tui` against a named workspace, I
want the TUI's clock and notification timing to reflect the same timezone as
the rest of the CLI for that workspace, so due dates, overdue status, and
notification timing agree wherever I interact with lifetxt.

#### Acceptance Criteria

1. While the TUI is running against a workspace resolved under Requirement 1,
   the TUI's displayed time shall reflect the timezone context established
   for that invocation.
2. While notification matching or classification runs during a CLI or TUI
   invocation resolved under Requirement 1, timezone-dependent notification
   calculations shall use the same timezone context established for that
   invocation.
3. The TUI shall not establish a timezone context independent of the one
   already established for the invocation before the TUI started.

### Requirement 3: Visible active-workspace indicator in the TUI

**Objective:** As a user who launches `lifetxt tui --workspace <name>`, I
want to see which workspace is active without leaving the TUI, so that I can
confirm `--workspace` took effect before I start reading or editing.

#### Acceptance Criteria

1. When the TUI starts with a resolved workspace active, whether selected
   explicitly via `--workspace` or implicitly via a configured default
   workspace, the TUI shall display that workspace's name in its title bar or
   status line.
2. When the TUI starts with no workspace resolution active (a configuration
   with no `workspaces` section and no `default_workspace`), the TUI shall
   not display a workspace name, preserving its current title/status
   appearance.
3. Where the plain-text dashboard fallback is shown instead of the
   interactive TUI, the dashboard shall also display the active workspace
   name under the same condition as Acceptance Criterion 3.1.
4. The active-workspace indicator shall reflect only the workspace resolved
   at startup for the current invocation; this feature does not add
   in-session workspace switching.

### Requirement 4: No behavior change outside timezone-context resolution and the workspace indicator

**Objective:** As an existing lifetxt user or script author, I want this fix
to change only the timezone-context source-file selection and the TUI
workspace indicator, so nothing else about `--workspace` or timezone
resolution that I already depend on changes.

#### Acceptance Criteria

1. The CLI shall continue to resolve input paths, write targets, and
   generated/archive paths for `--workspace` exactly as it does today; this
   feature shall not alter that resolution.
2. The CLI shall not introduce a new configuration key, schema field, or
   per-workspace timezone override as part of this feature.
3. If workspace resolution reports diagnostics for the active workspace, the
   CLI shall report them exactly as it does today; this feature shall not
   change diagnostic behavior.
