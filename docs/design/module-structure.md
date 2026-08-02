# Module Structure Investigation

Status: investigation result for #67.

This note decides whether the current module structure is a problem worth
acting on, what measurable criteria should trigger decomposition, and how the
work should be sliced if it is scheduled.

Measured on `main` at `94765ac` after PR #68.

## Decision

The current structure is a real maintainability problem, but it is not urgent
enough to justify a large refactor by itself.

Do not keep unconstrained import-time mutation as a deliberate long-term design.
Treat it as compatibility debt. The next architectural move should be to
constrain extension points with explicit registries and composition boundaries,
then replace the existing monkey-patches one slice at a time during planned
surface splits.

The recommended option is therefore:

1. Constrain the pattern with a registry contract.
2. Extract obvious assets and registries first.
3. Replace each import-time wrapper with direct composition only when the
   target surface is being split or touched for a related change.

This is intentionally not a request to split `cli.py`, `webapp.py`, `mcp.py`, or
`tui_app.py` immediately.

## Current Map

`git ls-files "*.py"` reports 240 Python files and 100,642 total lines.

| File | Lines | Share | Primary issue |
| --- | ---: | ---: | --- |
| `lifetxt/webapp.py` | 11,710 | 11.6% | Embedded frontend asset plus server routes in one file |
| `lifetxt/cli.py` | 11,259 | 11.2% | Argument parser registry and 129 command handlers in one file |
| `tests/test_lifetxt.py` | 9,151 | 9.1% | Cross-surface regression history in one review unit |
| `lifetxt/mcp.py` | 2,848 | 2.8% | Tool schemas, handlers, resources, and JSON-RPC wiring in one file |
| `lifetxt/tui_app.py` | 2,843 | 2.8% | State, command handling, layout, rendering, and mutations in one file |

Line count is not the decision criterion. It is a symptom that points at mixed
responsibilities and hidden extension points.

### `webapp.py`

`webapp.py` is two things:

- Server-side Python through line 2,691.
- One embedded `HTML_PAGE` string from line 2,692 through line 11,710.

The embedded page is 9,019 lines, or 77.0% of the file. It contains HTML, CSS,
JavaScript, i18n dictionaries, command-palette handlers, dashboard/focus/review
views, undo behavior, completion behavior, and many UI workflows. The Python
server side has 55 route decorators inside `create_app`.

This means the `webapp.py` roadmap gap is not primarily "split a large Python
module." The first split should extract the frontend asset from the server
module, then split route groups only after the server responsibilities are
visible.

Server responsibility groups:

- app creation, middleware, exceptions, and config exposure;
- item, line, raw-line, and ID-based read/write endpoints;
- agenda, graph, blockers, stats, chart, review, and command catalog endpoints;
- message, notification, timer, work-session, attachment, status, shorthand,
  capture, and Git endpoints;
- helper functions for item serialization, payload conversion, text mutation,
  config projection, sorting, filtering, and error shaping.

Frontend responsibility groups inside `HTML_PAGE`:

- layout and CSS;
- client API wrapper and configuration application;
- Japanese i18n;
- view and dashboard routing;
- item list, drawer, bulk actions, undo, context menu, and filters;
- messages, notifications, timers, work sessions, attachments, agenda, review,
  focus, graph, stats, Git modal, command palette, and completion.

### `cli.py`

`cli.py` has 305 top-level functions. Of those, 129 are `command_*` handlers.
`build_parser` alone spans 2,608 lines and contains 151 literal `add_parser`
calls. The file also contains command execution helpers, mutation helpers,
formatting helpers, IO helpers, and completion behavior.

The main problem is not just that the file is long. It is that command
definition, option schema, handler dispatch, and command implementation are
interleaved. Any split that moves handler bodies without first making command
metadata declarative will preserve the existing review burden.

### `mcp.py`

`mcp.py` has 65 registered tool handlers, a 600-line `_tool_schemas` function,
resource listing/reading, JSON-RPC handling, and read-only/destructive tool
classification. It is structurally closer to a registry than `cli.py`, but the
schema definitions and handlers still live in the same large module.

MCP should not be split independently from the CLI/Web registry discussion. The
safer move is to define the shared operation metadata first, then let MCP expose
tool schemas from that metadata.

### `tui_app.py`

`tui_app.py` already has a visible command registry shape, but state,
navigation, mutation, layout, rendering, help, key handling, and color setup are
still in one file. This file is smaller than the others and should wait behind
the CLI/Web/MCP surface decisions unless a TUI-specific feature forces the
split.

### `tests/test_lifetxt.py`

`tests/test_lifetxt.py` has 97 test classes and 9,151 lines. The largest
classes are parser, CLI filter, agenda CLI, Web API, Web app, MCP, and CLI
expansion suites.

The immediate rule should be: do not add new broad feature tests to
`tests/test_lifetxt.py` when a focused test file already exists or can be
created. Split old tests opportunistically by class when a related surface is
touched. Do not perform a standalone mass test move before the corresponding
surface boundaries are clearer.

## Import-Time Mutation Map

The 13 `_INSTALLED = False` modules are compatibility and surface-extension
layers. They install themselves from `lifetxt/__init__.py`, so ordinary package
import mutates public modules before callers use them.

| Module | Lines | Primary targets | Main effect |
| --- | ---: | --- | --- |
| `remote_ticket_writes.py` | 211 | `webapp`, `remote_web`, `remote_access`, `surface_runtime` | Adds remote ticket write routes and capability details |
| `remote_contracts_v6.py` | 600 | `webapp`, `mcp`, `surface_runtime`, `safety_foundation` | Adds remote v6 routes, MCP tools, clock gates, capability records |
| `remote_web.py` | 398 | `webapp`, `surface_runtime` | Wraps `create_app` with remote auth/session/resource endpoints |
| `runtime_safety_v2.py` | 238 | `mcp`, `webapp`, `cli`, safety modules | Adds timezone/revision context and stable diagnostics compatibility |
| `safety_compat_v2.py` | 150 | `extra_cli`, `cli`, safety/workspace modules | Compatibility wrappers for safety/doctor behavior |
| `surface_runtime.py` | 769 | `webapp`, `mcp`, `mutation`, `safety_foundation` | Adds revision contract, operation matrix, Web/MCP precondition gates |
| `surface_runtime_compat.py` | 273 | `mcp`, `webapp`, `mutation`, `surface_runtime` | Backward-compatible MCP/Web revision behavior |
| `ticket_custom_fields.py` | 1,132 | `cli`, `tickets`, `ticket_revision_writes`, capability modules | Adds custom-field registry, validation, CLI command wrapping |
| `ticket_planning_cli.py` | 560 | `cli` | Adds `version` and `sprint` command trees |
| `ticket_project_surfaces.py` | 591 | `cli`, `mcp`, `projects`, capability modules | Adds ticket project CLI/MCP/capability behavior |
| `ticket_revision_writes.py` | 607 | `cli`, `tickets`, capability modules | Adds exact-revision ticket write behavior |
| `ticket_workflow_surfaces.py` | 352 | `mcp`, `tickets`, capability modules | Adds ticket workflow MCP/capability behavior |
| `ticket_workflow_cli.py` | 589 | `cli` | Adds ticket workflow, watcher, time, and activity commands |

The pattern is useful historically because it let newer capabilities land
without editing already-large modules. The cost is that control flow is no
longer statically local:

- `webapp.create_app` is wrapped by multiple modules.
- `mcp.call_tool`, `mcp.tool_schemas`, resources, and tool maps are modified
  after definition.
- `cli.build_parser`, `cli.main`, and ticket command handlers are wrapped or
  extended after import.
- ticket model behavior is changed by assigning functions into `tickets`.

This should not be copied for new features.

## Options Compared

| Option | Cost | Risk | What it unblocks | Judgment |
| --- | --- | --- | --- | --- |
| Leave as is | Lowest short-term cost | Hidden control flow persists; future splits remain hard to review | Nothing | Not recommended except as temporary status quo |
| Replace injection with direct composition, then split | Highest; likely many shared files and large diffs | High blast radius across CLI/Web/MCP/tickets; difficult rollback if halfway done | Cleanest final architecture | Correct end state, wrong first step |
| Split big files without touching injection | Medium to high | Can make control flow harder by spreading patched behavior across more files | Some file-size reduction | Not recommended |
| Constrain with registries, then replace per slice | Medium; incremental | Temporary dual structure and registry design work | Reviewable decompositions and safer future splits | Recommended |

### Option Risk Details

| Option | Review burden | Blast radius | Interaction with in-flight work | Midway revert behavior |
| --- | --- | --- | --- | --- |
| Leave as is | Low now, high later because reviewers must remember import side effects | None immediately | Lowest conflict risk | Nothing to revert, but the structural risk remains |
| Replace injection with direct composition, then split | Very high; reviewers must understand all surfaces and installation order at once | CLI, Web, MCP, tickets, safety, remote, and capability docs | Should block most surface work while in flight | A partial revert can leave import order, wrappers, or capability records inconsistent |
| Split big files without touching injection | High; reviewers must inspect moved files plus unchanged wrappers | Target file plus every module that patches it | Creates conflicts with any extension or route/command work touching the same target | Reverting one split may not revert the wrapper assumptions that moved with it |
| Constrain with registries, then replace per slice | Moderate; each PR reviews one boundary and one old wrapper | One surface or one extension family per slice | Can run in parallel with unrelated product work if write scopes do not overlap | Each slice should be independently revertible to the previous wrapper path |

## Split Criteria

A module is a candidate for decomposition when at least one objective trigger
below applies and the change has a narrow, reviewable boundary.

1. Embedded asset trigger:
   A non-Python literal asset is more than 1,000 lines or more than 25% of a
   Python module. The first action is to extract the asset, not to move server
   logic.

2. Surface registry trigger:
   A single module declares more than 30 public commands, routes, or tools and
   lacks a declarative registry that records name, public contract, handler,
   read/write classification, and capability impact.

3. Import-time mutation trigger:
   A module mutates public functions or maps in another module at import time,
   especially `create_app`, `build_parser`, `main`, `call_tool`,
   `tool_schemas`, or `TOOL_HANDLERS`. New work must use an explicit registry
   or composition hook instead.

4. Reviewability trigger:
   A file mixes three or more independent reasons to change and a normal
   feature PR must inspect unrelated route, command, tool, UI, and mutation code
   to prove behavior. The split must isolate one reason to change.

5. Test ownership trigger:
   A test file has more than 25 test classes or more than 3,000 lines spanning
   more than three surfaces. New tests should go to focused files, and old
   classes should move only when their related surface is already being touched.

Raw line count alone is explicitly not a trigger. A large generated table, a
static asset, or a cohesive registry may be acceptable if it is declarative and
has one reason to change.

## Stop Criteria

Stop splitting when these are true for the affected surface:

- New feature registration is a small declarative diff plus a handler or
  service implementation.
- No new `_INSTALLED` wrapper mutates core surface functions.
- Remaining legacy wrappers have explicit owners and removal conditions.
- Reviewers can identify the public contract, handler, read/write behavior, and
  capability impact without scanning unrelated surfaces.
- Reverting one slice restores the previous behavior without requiring a second
  coordinated revert.

## Decomposition Plan

Each slice below is intended to become a separate issue and PR.

1. Web asset extraction
   - Size: M, because the diff is mostly moved lines.
   - Write scope: `lifetxt/webapp.py`, a new Web asset module or package data
     file, focused Web tests.
   - Goal: move `HTML_PAGE` out of `webapp.py` without changing routes,
     endpoints, or rendered bytes.
   - Revert behavior: one revert returns to the embedded string.

2. Web route grouping
   - Size: S per route group.
   - Write scope: one route group and its focused tests.
   - Candidate groups: items/raw-line, agenda/stats/charts, messaging,
     timer/work-session/status, attachments, Git.
   - Dependency: run after asset extraction, or after a route registry hook
     exists.

3. Surface extension registry
   - Size: S/M depending on whether it covers one surface or CLI/Web/MCP
     together.
   - Write scope: registry module, one existing extension module, targeted
     surface tests.
   - Goal: make extensions register capabilities, operations, commands, routes,
     or tools through explicit calls rather than replacing public functions.

4. CLI parser registry skeleton
   - Size: M.
   - Write scope: `cli.py`, a command registry module, completion/help tests.
   - Goal: make command metadata declarative before moving command handler
     bodies.
   - Non-goal: moving every command in the first PR.

5. CLI command-family extraction
   - Size: S per family after the registry skeleton exists.
   - Candidate groups: config/workspace, project/portfolio/area, messaging,
     ticket core, ticket workflow/planning, import/export, archive/review.

6. MCP schema registry extraction
   - Size: S/M.
   - Write scope: `mcp.py`, one MCP registry module, MCP schema/handler tests.
   - Goal: separate schema declaration and handler dispatch while preserving
     current tool names and read-only/destructive classifications.

7. TUI decomposition
   - Size: S per boundary.
   - Candidate groups: state, command definitions, key handling, rendering,
     mutation/recovery presentation.
   - Dependency: lower priority unless TUI work is scheduled.

8. Focused test migration
   - Size: XS/S per moved class cluster.
   - Write scope: one old test class cluster and one focused test file.
   - Rule: move tests when the related surface is touched; do not do a single
     repository-wide test shuffle.

## Web Roadmap Gap

`todo.md` now records a `webapp.py` split item beside the existing `cli.py` and
`tui_app.py` items. The roadmap line points at this decision: extract the
embedded frontend first, then split route groups through shared operation or
route registries.

## Urgency

This is not urgent. There is no current bug, failing gate, blocked capability,
or release condition that requires immediate restructuring.

The work becomes urgent only if one of these conditions appears:

- A feature requires editing two or more patched surfaces and cannot be reviewed
  without understanding import-time mutation order.
- Capability drift, command catalog, or MCP schema checks start requiring new
  exceptions because registration is not explicit.
- `HTML_PAGE` or `build_parser` changes become frequent enough that unrelated
  UI/API/CLI code conflicts in normal PRs.

Until then, apply the criteria opportunistically and keep slices small.

## Evidence Commands

```text
git ls-files "*.py"
rg -l "^_INSTALLED = False" lifetxt --glob "*.py"
rg -n "^HTML_PAGE|^def |@app\.|app\.(get|post|put|delete)" lifetxt/webapp.py
rg -n "^def build_parser|^def command_|add_parser\(|set_defaults\(" lifetxt/cli.py
rg -n "^TOOL_HANDLERS|^def _tool_schemas|^def _tool_|^def call_tool" lifetxt/mcp.py
rg -n "webapp|cli\.py|tui_app|monkey|install\(|split|module" todo.md docs/design .ai/project/RULES.md
```
