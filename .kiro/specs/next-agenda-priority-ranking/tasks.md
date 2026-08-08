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
>
> See #101 for the decision behind this.

## Tasks

- [ ] 1. (P) Implement the overdue-aware ranking key with direct unit coverage
  - Add a pure function that computes overdue status against the current date, then falls back to next's existing priority ordering, then due date, then created date, then source line, exactly matching the tie-break chain requirements.md defines
  - Cover, as direct unit tests (no CLI invocation): an overdue item ranking ahead of a higher-priority not-yet-due item; an item due exactly today classified as not overdue; an item with no due date classified as not overdue and sorting after present-due items at equal priority/overdue status; two overdue items with equal priority and due date breaking the tie by created date, then by line
  - Observable completion: running the new unit tests in isolation (without touching the CLI parser or `command_next`) passes and exercises every tie-break level once
  - This task is the only one of the four that edits the shared test file (adding new test cases, not modifying existing ones), so it stays parallel-safe against task 2, which touches only the argument parser
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_
  - _Boundary: Core logic (ranking key)_

- [ ] 2. (P) Add the `--rank` flag to the `next` command's argument parser
  - Register a boolean opt-in flag on `next`'s existing argument parser, defaulting to off, alongside its existing `--limit`/`--format`/`--pretty` options
  - Observable completion: invoking `next --help` lists the new flag; verify by inspection and manual invocation only (parsing `next --rank` yields a truthy flag, parsing `next` without it yields the same falsy default as today) — this task does not add its own automated test, since task 3 and task 4 exercise the parsed flag end to end and this task touches only the argument parser, not the shared test file
  - _Requirements: 1.1_
  - _Boundary: CLI argument parser_

- [ ] 3. Wire the ranking key into `next`'s item ordering
  - When the flag from task 2 is set, order the items `next` already selects using the ranking key from task 1 instead of the command's current fixed ordering; when the flag is absent, keep using the current ordering exactly as today
  - Resolve "today" once per command invocation using the project's existing deterministic date resolution already used elsewhere in this module, rather than reading it separately per item
  - Observable completion: running `next --rank` against a small fixture with a mix of overdue, due-today, and no-due items returns them in the order task 1's tests predict; running `next` without the flag against the same fixture is unaffected
  - _Depends: 1, 2_
  - _Requirements: 1.4_
  - _Boundary: `next` command orchestration_

- [ ] 4. Validate default-output non-regression and option composition end to end
  - Confirm `next` without `--rank` selects the same items and produces output identical to the pre-change baseline, including its existing exclusion behavior for closed/blocked/parked items
  - Confirm `next --rank` selects the exact same item set as plain `next` on the same input, only reordered
  - Confirm ranked ordering is reflected consistently across each of `next`'s existing output formats
  - Confirm ranked ordering composes correctly with each of `next`'s existing filtering/limiting options
  - Observable completion: the full existing `next`-related test suite plus the new end-to-end cases all pass together, with no existing assertion changed to accommodate this feature
  - _Depends: 3_
  - _Requirements: 1.2, 1.3, 3.1, 3.2_
  - _Boundary: `next` command orchestration, test suite_
