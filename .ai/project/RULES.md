# Project Rules

Add project-specific rules here.

Rules in this file may specialize overridable common standards. They must not
weaken non-overridable common standards such as secret handling, protected
branch review, or write-scope enforcement.

If the user asks what to do next, use `.ai/project/GUIDANCE.yml` and the common
`NEXT_ACTION.md` standard before recommending implementation.

Project process choices belong in `.ai/project/METHOD.yml`. Do not encode
method-specific behavior only in an AI tool's local instruction file.

## GitHub Labels

Issue templates under `.github/ISSUE_TEMPLATE/` declare labels in their `labels:`
block. GitHub silently ignores a declared label that does not exist in the
repository: the template still works, but the issue is created with no label and
nothing warns anyone. Every template in this repository declared labels that had
never been created, which is how #43 was found.

Rules:

- Every label declared by an issue template must exist in the repository.
- A change that adds a name to a template's `labels:` block must create that
  label in the same change. Reviewing anything under `.github/ISSUE_TEMPLATE/`
  includes checking this.
- Labels are managed manually, through repository settings or `gh label create`.
  There is deliberately no manifest file and no synchronising workflow.

The taxonomy has two axes:

- `type:*` — one per issue template: `algorithm`, `deprecation`, `feature`,
  `guidance`, `incident`, `investigation`, `operations`, `process`, `standards`,
  `task`. They share the colour `#1d76db` so the axis reads as one group.
- `status:*` — workflow state, one label per issue. `status:inbox` (`#ededed`)
  is applied by every template; the remaining values are described under
  **Issue Status** below.

The `type:*` axis intentionally does not cover every change type in
`.ai/managed/core/ASSURANCE_LEVELS.md`. Bug, Refactoring, Security, Performance,
and Migration have no template, so they have no label; change type is recorded in
the issue body and pull request rather than by label. GitHub's default labels
(`bug`, `enhancement`, and so on) remain available for ad-hoc use.

Issues closed before this taxonomy existed were deliberately not relabelled, so
older issues carry whatever label was available at the time.

## Issue Status

Issue status is expressed with a `status:*` label. Exactly one is set at a time.
The eight values come from `.ai/managed/core/TASK_MANAGEMENT.md`:

| Label | Meaning |
| --- | --- |
| `status:inbox` | Filed, not yet refined. Applied by every issue template. |
| `status:ready` | Meets `DEFINITION_OF_READY.md`; implementation may start. |
| `status:planned` | Accepted and scheduled, not yet started. |
| `status:in-progress` | Implementation underway on a dedicated branch or worktree. |
| `status:in-review` | Pull request open, awaiting independent review. |
| `status:blocked` | Waiting on a decision, dependency, or access. |
| `status:done` | Merged and Definition of Done satisfied. |
| `status:cancelled` | Closed without implementation. |

Implementation must not start while an issue is `status:inbox` or
`status:blocked` (`TASK_MANAGEMENT.md:69`). Moving an issue to `status:ready`
means asserting that every condition in `DEFINITION_OF_READY.md` is met — it is a
gate, not a formality.

### Status backend: labels instead of GitHub Projects

`.ai/managed/core/TASK_MANAGEMENT.md`'s `governance.status_backend` field
(added when the standard was synced past commit `0737bcac`) makes this an
explicit, first-class choice rather than an undocumented deviation. This
project sets:

```yaml
governance:
  status_backend: github-labels
```

in `.ai/project/PROJECT.yml`. Before this field existed, `status:*` labels
were used in place of the standard's default (GitHub Projects) as a
documented specialization; the reasons below are unchanged, they are just no
longer a deviation from an overridable default. Reasons:

- One maintainer and no cross-project portfolio, so the planning and
  cross-project-visibility benefits of Projects do not currently apply.
- Both humans and AI executors work this repository from the terminal. Labels are
  returned by the same `gh issue list` that enumerates the backlog, whereas
  Projects requires an additional `read:project` token scope that the current
  tooling does not hold — status would be invisible at the point of use.
- Every issue template already declares `status:inbox`, so labels were half
  implemented. Running both mechanisms would reintroduce the dual-source-of-truth
  problem that #51 decided against for `todo.md`.

This specializes an overridable standard. It does not weaken any item in the
non-overridable baseline in `.ai/managed/core/INDEX.md`: the task source of truth
remains GitHub Issues, and the `Inbox`/`Blocked` gate is preserved above.

Revisit when any of these becomes true:

- more than one person or agent plans the backlog concurrently
- cross-project or portfolio visibility is needed
- status automation (boards, workflows) would carry its own weight
- the `read:project` scope is granted and Projects becomes usable from the CLI

## Runtime Dependencies

The project is dependency-light by design: `web`, `tui`, and `dev` are optional
extras, and the core parser, CLI, ticket model, and future counter-machine
runtime stay free of third-party requirements.

`tzdata`, declared for Windows only, is the one mandatory runtime dependency.
Do not remove it as unnecessary. Windows has no IANA timezone database for
`zoneinfo` to read, so a clean Windows install could resolve no timezone at all
— the recorded `integration_test` command failed in an environment built by the
recorded `setup` command (#73). It is data-only, has no transitive
dependencies, and its platform marker keeps every other platform
dependency-free.

Timezone resolution now uses that one declared source and nothing else. The
`dateutil` and `pytz` fallbacks were removed in #76: being undeclared, they only
ever resolved anything when an unrelated package happened to install one, which
is exactly how #73 stayed hidden on an Anaconda environment for so long. Code
that works only when a dependency arrives by accident reads as supported and is
not. Do not reintroduce an undeclared fallback; if a platform genuinely needs
another source, declare it here first.

Adding any further mandatory dependency is a decision, not an implementation
detail. Record the reason and the alternative that was rejected, as here.

## Verification Evidence

A failing or flaky suite run must be reported with its captured output. A
summary line is not a diagnosis, and the output is gone the moment the terminal
scrolls or the command is piped through something that truncates it.

Use `unit_test_captured` (or its PowerShell variant) from
`.ai/project/COMMANDS.yml` when a run might fail. It keeps the complete output
in `.test-output.log` and prints only the summary, so truncating the display
cannot destroy the evidence. `.test-output.log` is already ignored by the
leading `.*` rule in `.gitignore`.

This rule exists because a full run reported `FAILED (errors=1)` during #76 and
the error text was lost to a truncating pipe before anyone read it. Two later
runs passed and the cause was never identified (#78). One unexplained failure is
tolerable; being unable to look at it is not.

When a run does fail, record the interpreter version, the shell, whether
`BashCompletionExecutionTests` ran or skipped, and whether the working tree was
modified while the run was in flight. Each of those has already changed the
reading of a result at least once in this project.

## Traceability Gate

Code-changing pull requests are those whose diff changes `lifetxt/**` or
`tests/**`. They must add a meaningful `.ai/project/TRACEABILITY.yml` update
before merge.

A meaningful traceability chain update adds non-empty `requirement_id`,
`capability_id`, `task_issue`, `tests_or_evidence`, and `status` fields. On pull
request CI, it must also add the current `pull_request` URL. Empty, comment-only,
or formatting-only edits to `.ai/project/TRACEABILITY.yml` do not satisfy the
gate.

If traceability is not applicable, record an exception in
`.ai/project/TRACEABILITY.yml` with `exception_type:
traceability_not_applicable`, `task_issue`, `pull_request`, `scope`, `reason`,
`approved_by`, and `status: accepted`.

Enforcement is `tests.test_traceability_gate` inside the required release-gate CI
job. CI compares the pull request diff with the base SHA and passes the current
pull request URL to the test. Local runs compare feature branches with
`origin/main` when that ref is available.

Rejected alternatives:

- PR template checkbox only, because a checked box cannot prove that the diff
  contains a meaningful traceability update.
- Workflow-only shell logic, because the policy is easier to test and review as
  ordinary Python unittest code.
- Suite-only enforcement, because the PR base SHA and current pull request URL
  are CI context and should be passed explicitly by the workflow.

### Multi-PR integration branches

The gate assumes one PR per requirement by default: the entry a task adds when
it merges is expected to already name the PR the gate is checking. A batch that
lands through an integration branch (several task branches merging into one
`feature/*` branch, then one final PR into `main`) breaks that assumption --
every entry correctly names its own sub-PR, and none of them names the final
PR, because that PR did not exist yet when they were written.

Add one further chain entry when opening the integration-branch-to-`main` PR,
recording that PR as its own step (`pull_request` set to the integration PR,
not any sub-PR). Do not rewrite the sub-PR entries to point at the integration
PR instead -- that would misattribute the work to a PR that did not implement
it. See `.ai/project/TRACEABILITY.yml`'s `req-remote-batch-integration` entry
for the pattern, and #131 for why it was needed.

## Change Package Close-out

A change package must not still say the work is only proposed once that work has
landed. `.ai/project/changes/README.md` requires closing or archiving a package
after merge, and `ASSURANCE_LEVELS.md` expects retained evidence at High
assurance -- the package is the artifact that carries it.

Rules:

- When a package's own `traceability.yml` reports landed work, `change.yml`
  must not be `draft` or `proposed`.
- No `verification.yml` entry may remain `planned`. Record the command, the
  result, and the commit it ran on. **A plan is not evidence.**
- A requirement with no test behind it is recorded as a gap with a `tracked_by`
  issue, not omitted and not described as verified.

Enforcement is `tests.test_change_package_closeout`, which runs in the ordinary
suite. It is deliberately offline: whether a pull request merged is not knowable
from the repository, so the check uses the package's own contradiction instead --
traceability links claiming landed work while `change.yml` says otherwise. That
state is self-inconsistent regardless of what GitHub reports.

This rule exists because the first change package sat at `proposed` with all five
verification entries reading `planned` after five merged pull requests, and
nothing reported it. Closing a package was nobody's step (#117). The same shape
had already occurred twice: #47 closed with its traceability criterion unmet, and
#103's steering text became false the moment #105 merged.

Closing out the first package also found a recorded evidence claim that did not
exist: `req-atomic-replace-retry-policy-consistency` cited assertions on retry
constants that no test makes. **Stale records and untrue records arrive by the
same route** -- nobody re-reads them after the work is done.

Rejected alternatives:

- Extend the #88 traceability gate, because that gate reasons about a pull
  request diff, while this is a repository-state invariant that holds
  independently of any diff.
- A rule with no mechanism, because that is what was already in
  `.ai/project/changes/README.md` and it did not hold.
- Querying GitHub for issue or pull request state, because the suite must run
  offline and a check that needs a token is a check that gets skipped.

## Tracked Exceptions

`.ai/project/COMMANDS.yml` may record a command as `tracked_exception` when no
command can be configured yet. The `tracked_by` issue is what keeps the exception
from becoming permanent, so it has to be an issue that cannot outlive it.

Rules:

- `tracked_by` must reference an issue whose **closure condition is the removal of
  that exception**. A broad cleanup or milestone issue is not acceptable: it can
  be completed while the exception survives, which silently leaves the exception
  untracked.
- Every exception must state a `reason` and a `removal_condition`.
- Closing an issue that appears as a `tracked_by` value requires either removing
  the exception in the same change, or repointing `tracked_by` at a new issue that
  satisfies the rule above.

This rule exists because the `format` and `lint` exceptions were tracked by #39,
a general post-adoption foundation issue. #39 was legitimately completed by #40
while both exceptions remained, and nothing surfaced them again until #44.

## Configuration Setting Completion

Configuration documentation is part of the acceptance criteria for every new,
changed, deprecated, or removed configuration setting. A setting is not complete
when only the implementation, default, template, or schema changes.

For any task that changes a configuration setting, the issue and PR must either
update these items together or explicitly state why an item is not applicable:

- authoritative schema/registry metadata, including default, type, provenance,
  restart requirement, secret status, versioning, and deprecation or replacement
  metadata when relevant
- `lifetxt config explain` behavior and any generated explanation data
- English and Japanese configuration documentation
- examples or fixtures that demonstrate the setting when the behavior is visible
  to users
- migration, compatibility, and downgrade behavior, including tests or recorded
  evidence for the chosen behavior

Configuration-setting task acceptance criteria must call out this rule. If the
task intentionally narrows or rejects one part of the rule, the replacement
expectation belongs in the issue and PR rather than only in reviewer comments.

## Where Decisions Live

Per #51:

- **Actionable work** — GitHub Issues are authoritative. When `todo.md` and an
  Issue disagree about what should be built, the Issue wins.
- **Principles and product boundaries** — this file is authoritative. When
  `todo.md` and this file disagree about what the project will or will not do,
  this file wins.
- `todo.md` remains the roadmap and the parking lot for ideas that are not yet
  actionable. It is not a task list and not a rules document.

## Stable Release Stabilization

The stable-release stabilization tracker is #283. During this phase,
`.ai/project/STABLE_RELEASE.yml` is the repository-authoritative policy for the
feature freeze, release-boundary classification, and exception path.

This does not replace the existing task gates: GitHub Issues remain the source
of truth for actionable work, and implementation must still not start from
`status:inbox` or `status:blocked` issues. A feature-freeze exception is a
reviewable issue or pull request decision, not a shortcut around security,
migration, data, operations, release, or destructive-operation approvals.

## Design Principles

Moved from `todo.md` by #54. These constrain what is acceptable, not what is
scheduled; a change that violates one needs an explicit decision, not a
workaround.

`docs/en/philosophy.md` / `docs/ja/philosophy.md` (#506) explain the
long-term reasoning and vision behind these principles for users and
contributors in more accessible terms. That document does not add new
rules; it explains and cross-references the rules below. If the two ever
disagree, this file is authoritative and the philosophy document must be
corrected to match, not the reverse.

- Fail loudly when behavior is ambiguous or data may be lost.
- Keep life.txt authoritative and use standard, inspectable interchange formats.
- Route authoritative writes through validated, atomic, conflict-aware mutation
  contracts.
- Treat compensated multi-target commits as an explicit recovery contract, not as
  portable filesystem-level atomicity.
- Keep CLI, TUI, Web API, Web UI, MCP, editor support, schemas, configuration,
  and documentation semantically aligned.
- Make effective configuration deterministic, explainable, schema-valid, and safe
  to migrate before allowing it to control remote access, integrations, or
  automatic writes.
- Prefer lifetxt as an action and information hub over copying every external
  system's full data into life.txt.
- Represent development tickets with normal Task records plus documented
  `record:ticket` metadata until evidence justifies a new item type; preserve
  generic project `record:issue` records for non-ticket project issues and risks.
- Keep the current ticket state readable on the ticket record while storing
  comments and audit-relevant changes as append-only `record:ticket_event`
  records committed through the same transaction as the state change.
- Treat Git, GitHub, GitLab, CI/CD, chat, and email as external authorities when
  appropriate; store stable references, normalized summaries, proposals, and
  audited actions instead of silently mirroring complete histories.
- Treat remote access, integrations, development-tool automation, and general
  automation as proposal-producing clients unless a validated write contract
  permits direct mutation.
- Treat a successful release gate as evidence, not as permission to ignore known
  baseline debt.
- Preserve old public CLI behavior when introducing richer reports; use explicit
  modes or unambiguous new flags.

Parsing has one further guarantee, moved from the counter-machine section of
`todo.md` because it holds regardless of that feature:

- Keep normal life.txt parsing permissive. Unknown custom keys remain valid.

The three counter-machine design principles stay with the counter-machine
specification and move in #51 Part 2.

## Product Boundaries

Things this project has decided **not** to do, and the conditions under which
each could be revisited. Moved from `todo.md` by #54.

- **Keep credentials outside life.txt and plaintext configuration.** Store only
  environment-variable or OS credential references, define token scopes and
  rotation checks, and ensure logs, effective config, diagnostics, exports, and
  support bundles never expose secrets.
- **Keep remote/local transfer explicit** through export, copy, or proposal
  import. Do not add background bidirectional synchronization, automatic Git
  synchronization, or silent local caching of authoritative data.
- **Keep external attachments reference-first.** Copy or transform content only
  through the attachment transaction, MIME, size, privacy, permission, and
  recovery policies; never silently mirror an entire mailbox, chat history, issue
  tracker, repository, or CI log.
- **Do not automatically close tickets** from commit keywords, merge events, CI
  success, or deployment success until proposal review, permission, idempotency,
  stale-evidence handling, and compound event-history writes are proven.
- **Do not add arbitrary Web JavaScript**, direct life.txt rewrite plugins,
  unrestricted integration or development-tool hooks, unrestricted automation, or
  provider-triggered computation before sandbox and permission models exist.
- **Keep arbitrary CSS administrator-only and disabled by default**; keep
  arbitrary JavaScript and third-party in-page plugins deferred.
- **Do not attempt to replace** email, calendar, chat, Git hosting, CI/CD, issue
  trackers, or file storage wholesale; integrate through references, summaries,
  proposals, and explicit approved actions.

Counter-machine boundaries stay with the counter-machine specification and move
in #51 Part 2.

## Specifications

Spec-driven development uses cc-sdd, installed for Claude Code and Codex by #104.
Per #101:

- **cc-sdd writes to `.kiro/specs/<feature>/`.** That is working material.
- **`.ai/project/changes/<change-id>/` is the source of truth.** For non-trivial
  work, and for anything at High or Regulated assurance, the spec is distilled
  into a change package, which is what reviewers and the other executor read.
- Distilling is a manual step, so the two can drift. **The change package wins.**

`.ai/project/changes/README.md` sets the threshold for needing a package at all:
non-trivial changes, High or Regulated assurance work, public API changes, data
changes, migrations, operations changes, or any change where requirements,
design, tasks, tests, and release evidence may drift. Below that threshold the
issue and pull request carry the reasoning, and no package is created.

The formats differ deliberately. cc-sdd emits Markdown; the change package uses
`requirements.yml` and the other template files, because those feed the
standard's traceability records.

### Tasks are GitHub Issues

A spec's task breakdown decides what issues to file. It is not itself a task
list. `.ai/managed/core/TASK_MANAGEMENT.md` makes Issues the source of truth for
actionable work, and `.ai/managed/core/INDEX.md` puts "no implementation without
a reviewable task source" in the non-overridable baseline.

`.kiro/settings/templates/specs/tasks.md` carries this rule, so it appears in
generated output rather than only here.

### A specification does not authorise implementation

The gate for starting work is an issue meeting
`.ai/managed/core/DEFINITION_OF_READY.md` and not labelled `status:inbox` or
`status:blocked`. Approved requirements and a reviewed design are inputs to
decomposition, not permission.

### Why `.kiro/specs/` is acceptable now

Issue #101 first chose Kiro and forbade a `.kiro/specs/` tree, reasoning that a
specification directory **only one tool reads** would be an alternative source of
truth outside the repository and GitHub, which
`.ai/managed/core/AI_TOOL_COMPATIBILITY.md` forbids adapters from creating.

cc-sdd removed that premise: it ships the same skills to Claude Code and Codex,
so both executors read the same specs. What the rule protects is that
`.kiro/specs/` must not become the *source of truth* — never the location itself.

Recorded because the original reasoning is still readable in #101's body, and
someone acting on it alone would reinstate a prohibition whose basis has gone.

Revisit if spec-driven work returns to a single-tool arrangement, or if the
distillation step is found to be skipped often enough that the change package
stops reflecting the spec.
