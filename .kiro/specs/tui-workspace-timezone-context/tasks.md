# Implementation Plan

> **This file is working material, not the task source of truth.**
>
> In this repository, actionable work lives in GitHub Issues.
> `.ai/managed/core/TASK_MANAGEMENT.md` makes Issues the source of truth, and
> `.ai/managed/core/INDEX.md` lists "no implementation without a reviewable task source"
> in the non-overridable baseline. A checklist here would compete with both.
>
> Use this breakdown to decide what the issues should be, then file them. Each must meet
> `.ai/managed/core/DEFINITION_OF_READY.md` before implementation starts, and an issue that is
> `status:inbox` or `status:blocked` may not be started. Writing this file does not open that gate.
>
> Recording the resulting issue numbers beside each task here is encouraged; inventing progress
> here without them is not.

- [ ] 1. Foundation: shared workspace/timezone helpers
- [ ] 1.1 Add a public workspace-resolution-active predicate and active-workspace-name accessor
  - Move the existing "is workspace resolution active for this config" check into a public function so it has one owner instead of staying private and duplicated
  - Add a small accessor that reads back the active workspace name already recorded on a resolved configuration
  - Observable: the CLI's existing workspace path/write-target resolution behaves identically before and after the move (no behavior change), verified by the existing workspace test suite passing unmodified
  - _Requirements: 1.1, 1.2, 1.3, 3.1, 3.2, 3.3, 4.1_
  - _Boundary: workspace module_

- [ ] 1.2 Add a workspace-aware candidate-file resolver for the timezone directive search, with unit tests
  - Build the ordered candidate-file list used to search for a file-level timezone directive: files named directly on the command line first, then the active workspace's resolved input files when workspace resolution is active, otherwise today's legacy candidate list unchanged
  - An unresolvable (unknown) workspace name falls back to the legacy candidate list rather than raising, so the timezone bootstrap never crashes ahead of the command's own error reporting
  - Observable: a unit test suite demonstrates all four candidate-selection cases (no workspace config, explicit `--workspace`, implicit default workspace, unknown workspace name) returning the expected candidate ordering
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  - _Boundary: timezone_policy module_
  - _Depends: 1.1_

- [ ] 2. Core: make both CLI timezone-context bootstraps workspace-aware
- [ ] 2.1 (P) Wire the legacy timezone-context installer to the workspace-aware candidate resolver
  - Extract `--workspace` from the raw argument list the same way the installer already extracts `--config`
  - Replace the installer's inline candidate-file construction with the shared resolver from 1.2
  - Observable: invoking the wrapped CLI entry point with `--workspace <name>` against a fixture workspace whose primary source carries a `timezone:` directive establishes that timezone for the duration of the call
  - _Requirements: 1.1, 1.3, 1.5, 1.6_
  - _Boundary: runtime_safety_v2 module_
  - _Depends: 1.2_

- [ ] 2.2 (P) Wire the active (compat-patched) timezone-context installer identically
  - Apply the same `--workspace` extraction and candidate-resolver wiring to the installer replacement that actually runs in production today
  - Observable: the same fixture-driven behavior as 2.1 holds when the CLI is invoked through the normal package entry point (which installs this patched version)
  - _Requirements: 1.1, 1.3, 1.4, 1.5, 1.6_
  - _Boundary: safety_compat_v2 module_
  - _Depends: 1.2_

- [ ] 3. Core: visible active-workspace indicator in the TUI
- [ ] 3.1 (P) Show the active workspace name in the interactive (curses) TUI header
  - Record the active workspace name, if any, when TUI session state is constructed
  - Render it as part of the existing header line only when a workspace is actually active, leaving the header unchanged otherwise
  - Observable: a header rendered with an active-workspace configuration contains the workspace's name; a header rendered with a legacy (no-workspace) configuration is byte-identical to today's output
  - _Requirements: 3.1, 3.2, 3.4_
  - _Boundary: tui_app module_
  - _Depends: 1.1_

- [ ] 3.2 (P) Show the active workspace name in the plain-text dashboard fallback
  - Apply the same active-workspace-name-when-present rule to the non-interactive dashboard header used when the terminal is not interactive or `--plain` is given
  - Observable: the plain dashboard header contains the workspace name under an active-workspace configuration and is unchanged under a legacy configuration
  - _Requirements: 3.3, 3.4_
  - _Boundary: tui module_
  - _Depends: 1.1_

- [ ] 4. Integration and validation
- [ ] 4.1 Verify the TUI clock and notification timing inherit the fixed timezone context
  - Confirm, with a test, that neither the TUI clock nor notification timezone-dependent classification establishes its own timezone context, so both automatically pick up the workspace-resolved context from Task 2
  - Observable: with a workspace-resolved fixture configuration carrying a distinctive `timezone:` directive, the TUI's rendered clock text and a notification's overdue/timing classification both reflect that timezone during the same invocation
  - _Requirements: 2.1, 2.2, 2.3_
  - _Boundary: tui_app module, notifier module_
  - _Depends: 2.1, 2.2_

- [ ] 4.2 Verify unknown-workspace and no-workspace invocations are unaffected
  - Confirm an unknown `--workspace` name still produces the CLI's existing "unknown workspace" error and non-zero exit, not a crash or silently different timezone-affected output
  - Confirm every non-workspace (legacy `paths`/`write_file`) invocation path is unaffected end to end, including diagnostics reporting
  - Observable: both scenarios are covered by passing tests exercising the real CLI entry point
  - _Requirements: 1.4, 4.1, 4.2, 4.3_
  - _Boundary: runtime_safety_v2 module, safety_compat_v2 module_
  - _Depends: 2.1, 2.2_

- [ ] 4.3 Run full regression and static checks
  - Run the complete unit test suite, lint, format check, and the CLI smoke check, and capture the results
  - Observable: the full suite passes with no new failures or skips beyond the pre-existing baseline, and lint/format report clean
  - _Requirements: 4.1, 4.2, 4.3_
  - _Depends: 4.1, 4.2_
