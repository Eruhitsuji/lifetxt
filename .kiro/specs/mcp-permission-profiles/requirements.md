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
>
> See #101 for the decision behind this.

## Project Description (Input)

MCP permission profiles (read|assist|full) for the `lifetxt mcp` command.

Context: this is the first implementation child issue (GitHub Issue #502,
parent epic #500 "Provider-independent Generative AI Integration") in the
lifetxt repository. Assurance level: High (authorization/security-sensitive
change per this repository's `ASSURANCE_LEVELS.md` escalation rules).

Who has the problem: operators who connect an external AI client (ChatGPT,
Claude, Gemini, a local LLM, an IDE agent) to their `lifetxt mcp` stdio
server. Today `lifetxt mcp` exposes either every tool (default) or, with
`--read-only`, no write tools at all -- there is no safe middle ground, and
no protection against a future tool silently becoming available to a
constrained connection just because it was added without being classified.

Current situation: `lifetxt mcp` already classifies tools for MCP annotation
purposes only (advisory hints, not enforced). The only real enforcement
point today is a single read-only flag, checked individually inside each
write-tool handler. There is no enforcement at the point where the server
advertises or dispatches a tool call, and no profile between "read-only" and
"everything."

What should change: add a `--profile` option to `lifetxt mcp` with three
values -- `read`, `assist`, `full` -- enforced both when the server
advertises its tool list and when it dispatches a tool call. `read` allows
only tools that never write. `assist` allows those same tools plus exactly
one additional tool that stages a non-authoritative change proposal
(`stage_proposal`); this allowlist is a repository-owner-confirmed decision
and must not be widened by this feature. `full` is today's current,
unchanged behavior. The existing `--read-only` flag becomes equivalent to
`--profile read` (also repository-owner-confirmed) rather than a second,
independent enforcement path. Any tool that is not explicitly allowed under
`read`/`assist` must be denied, including a tool nobody has yet classified,
so a future tool cannot silently become reachable from a constrained
connection. Existing per-tool write guards stay in place unchanged as
defense in depth.

## Boundary Context

- **In scope**: the `lifetxt mcp` command's `--profile` flag and its three
  values; enforcement at both tool-listing and tool-call time; the
  `assist` profile's exact allowlist (read tools plus the one named
  proposal-staging tool); `--read-only` becoming equivalent to
  `--profile read`; fail-closed handling of any tool not on a constrained
  profile's allowlist; English and Japanese documentation of the three
  profiles.
- **Out of scope**: which workspace sources or records are visible to an AI
  client (disclosure/visibility policy), any change to `lifetxt serve`'s Web
  API (it has its own, separately maintained read-only behavior), Remote
  Safe Mode, Cloud Mailbox or any storage-mediated transport, provider-
  specific setup adapters, widening the `assist` allowlist beyond the one
  named tool, and any change to what an allowed tool actually does.
- **Adjacent expectations**: this feature relies on the existing
  distinction between tools that never write and tools that do, and on the
  existing proposal-staging tool already behaving as a non-authoritative,
  human-reviewed change (per the Unified Inbox proposal contract). It does
  not redefine either of those; it only decides which of them a given
  profile may reach.

## Requirements

### Requirement 1: Profile Selection
**Objective:** As an operator connecting an external AI client, I want to choose a permission profile when starting the MCP server, so that I can control how much of lifetxt's tool surface that client can reach.

#### Acceptance Criteria
1. When the operator runs `lifetxt mcp` with `--profile read`, `--profile assist`, or `--profile full`, the MCP Server shall start with the corresponding profile active.
2. If the operator runs `lifetxt mcp` with a `--profile` value other than `read`, `assist`, or `full`, then the MCP Server shall reject the invocation with an error identifying the invalid value and shall not start.
3. When the operator runs `lifetxt mcp` without `--profile` and without `--read-only`, the MCP Server shall start with the `full` profile active.

### Requirement 2: Read Profile Enforcement
**Objective:** As an operator granting an AI client read-only access, I want the `read` profile to expose only non-mutating tools, so that the client cannot cause any data change through the MCP connection.

#### Acceptance Criteria
1. While the `read` profile is active, the MCP Server shall include only non-mutating tools when it advertises its available tools.
2. While the `read` profile is active, when the client calls a tool that is not one of the advertised non-mutating tools, the MCP Server shall reject the call with an error and shall not execute the tool.
3. While the `read` profile is active, the MCP Server shall reject a call to a tool that has not been explicitly designated as non-mutating, in the same way it rejects a call to a known mutating tool.

### Requirement 3: Assist Profile Enforcement
**Objective:** As an operator who wants an AI client to draft changes without granting it direct write access, I want the `assist` profile to allow only proposal staging in addition to read access, so that every AI-suggested change still requires my acceptance before it affects my data.

#### Acceptance Criteria
1. While the `assist` profile is active, the MCP Server shall include every non-mutating tool plus exactly one additional tool, the one that stages a non-authoritative change proposal (`stage_proposal`), when it advertises its available tools.
2. While the `assist` profile is active, when the client calls a non-mutating tool or the proposal-staging tool, the MCP Server shall execute it.
3. While the `assist` profile is active, when the client calls any tool other than a non-mutating tool or the proposal-staging tool, the MCP Server shall reject the call with an error and shall not execute the tool.
4. While the `assist` profile is active, the MCP Server shall reject a call to a tool that has not been explicitly designated as non-mutating or as the proposal-staging tool, in the same way it rejects a call to any other disallowed tool.

### Requirement 4: Full Profile Backward Compatibility
**Objective:** As an existing operator who already trusts an AI client with full access, I want the `full` profile to behave exactly like today's default, so that adopting this feature does not change any tool availability for my existing setup.

#### Acceptance Criteria
1. While the `full` profile is active, the MCP Server shall advertise and allow every tool that it advertises and allows today, with no additional restriction introduced by profile enforcement.
2. The MCP Server shall behave under the `full` profile, for every existing tool and every existing caller, identically to how `lifetxt mcp` behaves today when neither `--profile` nor `--read-only` is given.

### Requirement 5: `--read-only` Compatibility
**Objective:** As an operator who already uses `--read-only` today, I want that flag to keep working exactly as before, so that my existing MCP configuration does not break when this feature ships.

#### Acceptance Criteria
1. When the operator runs `lifetxt mcp --read-only`, the MCP Server shall enforce the same restrictions as `lifetxt mcp --profile read`.
2. If the operator supplies both `--read-only` and a `--profile` value other than `read`, then the MCP Server shall reject the invocation with an error naming the conflict rather than silently preferring one flag over the other.
3. The MCP Server's help text shall describe `--read-only` as equivalent to `--profile read`.

### Requirement 6: Fail-Closed Handling of Unclassified Tools
**Objective:** As an operator relying on constrained profiles for safety, I want any tool that has not been explicitly allowed under a profile to be unreachable, so that adding a new tool to lifetxt in the future cannot silently widen what a constrained AI connection can do.

#### Acceptance Criteria
1. While the `read` or `assist` profile is active, the MCP Server shall deny any tool that is not on that profile's explicit allowlist, whether that tool is a known mutating tool or a tool with no prior classification at all.
2. The MCP Server shall not use a tool's descriptive metadata (such as an MCP tool annotation) as the basis for allowing that tool under a constrained profile.

### Requirement 7: Defense-in-Depth Preservation
**Objective:** As a developer maintaining lifetxt, I want existing per-tool write protection to remain active in addition to profile enforcement, so that a defect in the new profile check does not by itself reopen a tool that was already protected before this feature.

#### Acceptance Criteria
1. While `--read-only` or an equivalent constrained profile is active, the MCP Server shall continue to reject an individual mutating-tool call at the point where that tool's own logic executes, independent of the profile-level check.

### Requirement 8: Documentation
**Objective:** As an operator setting up MCP access for the first time, I want the three profiles, the `assist` allowlist, and the `--read-only` relationship documented, so that I can choose the right profile without reading source code.

#### Acceptance Criteria
1. The MCP Server's documentation shall describe the `read`, `assist`, and `full` profiles, the tools allowed under each, and the relationship between `--read-only` and `--profile`, in both of this project's documented languages.
