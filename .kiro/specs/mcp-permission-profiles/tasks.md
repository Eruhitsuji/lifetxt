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

This whole feature is tracked by a single GitHub Issue,
[#502](https://github.com/Eruhitsuji/lifetxt/issues/502), the first
implementation child of the #500 AI-integration epic. Its acceptance
criteria already cover every task below; no further sub-issue decomposition
is needed for a change this size (Task Decomposition Standard: S candidate).

## Tasks

- [ ] 1. Foundation: profile-aware `McpContext` and CLI flag
- [ ] 1.1 Normalize `--profile`/`--read-only` into one authorization state on `McpContext`
  - Add a `profile` parameter to `McpContext.__init__`; when omitted, normalize to `"read"` if `read_only` is truthy, else `"full"`
  - Validate `profile` is one of `"read"`, `"assist"`, `"full"`, raising a clear error otherwise
  - Derive `self.read_only = bool(read_only) or profile == "read"` so every existing write-guard call site keeps working unchanged
  - Observable: constructing `McpContext(profile="assist")` yields `.profile == "assist"` and `.read_only == False`; constructing with `read_only=True` and no `profile` yields `.profile == "read"` and `.read_only == True`
  - _Requirements: 1.1, 1.3, 4.2, 5.1, 7.1_
  - _Boundary: McpContext Profile/Read-Only Normalization_

- [ ] 1.2 Add the `--profile` CLI flag and reject conflicting flag combinations
  - Add `--profile` (`choices=["read", "assist", "full"]`, default `None`) to the `mcp` subparser
  - Update `--read-only`'s help text to state it is equivalent to `--profile read`
  - In `McpContext.from_args`, raise a clear error when `read_only` is truthy and `profile` is given and is not `"read"`
  - Observable: `lifetxt mcp --profile bogus` exits nonzero via argparse before any server code runs; `lifetxt mcp --read-only --profile assist` raises a clear conflict error before the stdio loop starts; `lifetxt mcp --read-only --profile read` is accepted
  - _Requirements: 1.2, 5.2, 5.3_
  - _Boundary: CLI mcp Subparser, McpContext Profile/Read-Only Normalization_
  - _Depends: 1.1_

- [ ] 2. Core: per-profile tool allowlist and enforcement
- [ ] 2.1 Compute the allowed tool set for each profile
  - Add a one-tool `ASSIST_EXTRA_TOOLS` frozenset containing `stage_proposal`
  - Add a function returning the allowed tool-name set for a given profile: `READ_ONLY_TOOLS` for `"read"`, `READ_ONLY_TOOLS | ASSIST_EXTRA_TOOLS` for `"assist"`, and `None` (meaning "no restriction") for `"full"` or an unset profile
  - Observable: calling the function with `"read"` returns exactly `READ_ONLY_TOOLS`; with `"assist"` returns `READ_ONLY_TOOLS` plus `stage_proposal`; with `"full"`/`None` returns `None`
  - _Requirements: 2.1, 3.1, 4.1, 6.1, 6.2_
  - _Boundary: MCP Profile Enforcement_
  - _Depends: 1.1_

- [ ] 2.2 Enforce the allowlist in `call_tool` before dispatching to a handler
  - Add a check, called by `call_tool` immediately after its existing unknown-tool check, that raises a clear error naming the tool and the active profile when the tool is not in the profile's allowed set
  - Do not consult tool annotations (e.g. `readOnlyHint`) anywhere in this check
  - Observable: under `read`, calling `stage_proposal` or `create_item` raises without the handler ever executing, while calling a read tool succeeds; under `assist`, `stage_proposal` succeeds and actually stages a proposal while `create_item` and a `DESTRUCTIVE_TOOLS` member are both denied; under `full`, every tool that succeeds today still succeeds
  - _Requirements: 2.2, 2.3, 3.2, 3.3, 3.4, 4.1, 6.1, 6.2_
  - _Boundary: MCP Profile Enforcement_
  - _Depends: 2.1_

- [ ] 2.3 Filter the advertised tool list by the active profile
  - Add a function that filters an already-built schema list to the allowlist from 2.1; leave `tool_schemas`'s own zero-argument signature unchanged (four other modules wrap it at import time with their own zero-argument wrappers and would break if it gained a parameter -- confirmed by live tracing, see research.md)
  - Update the `tools/list` branch of `handle_request` to call `tool_schemas()` as before, then filter the result by `context.profile`
  - Observable: a `tools/list` response under `read` contains only non-mutating tool names; under `assist` also contains `stage_proposal`; under `full`, the response is byte-identical to today's output
  - _Requirements: 2.1, 3.1, 4.1, 4.2_
  - _Boundary: MCP Profile Enforcement_
  - _Depends: 2.1_

- [ ] 3. Validation
- [ ] 3.1 Unit tests for profile normalization and CLI flag validation
  - Cover `McpContext` construction for all three profiles, the `--read-only`/`profile=None` default paths, the `--read-only == --profile read` equivalence, and the conflicting-flag rejection
  - Observable: `python -m unittest tests.test_mcp_expansion` passes with the new `McpPermissionProfileTests` cases covering task 1's behavior
  - _Requirements: 1.1, 1.2, 1.3, 4.2, 5.1, 5.2, 5.3, 7.1_
  - _Boundary: McpContext Profile/Read-Only Normalization, CLI mcp Subparser_
  - _Depends: 1.2_

- [ ] 3.2 Unit tests for the allowlist and its enforcement
  - Cover `tool_schemas` filtering per profile and `call_tool` allow/deny outcomes per profile, including a synthetic never-classified tool name denied under `read` and `assist` but allowed under `full`
  - Observable: `python -m unittest tests.test_mcp_expansion` passes with cases covering every allow/deny combination from task 2
  - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 4.1, 6.1, 6.2_
  - _Boundary: MCP Profile Enforcement_
  - _Depends: 2.2, 2.3_

- [ ] 3.3 Integration test and full-suite regression check
  - Drive a fake stdio session through `tools/list` then `tools/call` under each profile, confirming the listed set matches what is actually callable
  - Re-run the full existing `tests/test_mcp_expansion.py` and `tests/test_surface_runtime.py` suites to confirm the CLI/Web/MCP capability-drift gate (which calls `tool_schemas()` with no profile) is unaffected
  - Observable: both suites pass unmodified alongside the new tests; a real `lifetxt mcp --profile read|assist|full` stdio session, driven with real JSON-RPC lines against a fixture workspace, shows `tools/list` and `tools/call` agreeing in each mode
  - _Requirements: 2.2, 3.2, 4.1, 4.2_
  - _Boundary: MCP Profile Enforcement_
  - _Depends: 3.2_

- [ ] 3.4 (P) Document the three profiles and the `--read-only` relationship
  - Update `docs/en/ai-integration.md` and `docs/ja/ai-integration.md` to describe `read`, `assist`, `full`, the `assist` allowlist, and fail-closed behavior for unclassified tools
  - Update `docs/en/cli.md` and `docs/ja/cli.md`'s `mcp` command reference to document `--profile` and the `--read-only` alias
  - Observable: both languages describe the same three profiles and the same `--read-only` relationship; `scripts/validate_release_docs.py` passes against the updated documents
  - _Requirements: 8.1_
  - _Boundary: Documentation_
