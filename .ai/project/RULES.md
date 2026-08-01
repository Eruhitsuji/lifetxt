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
- `status:*` — triage state. `status:inbox` (`#ededed`) is applied by every
  template and means "filed, not yet refined to Ready".

The `type:*` axis intentionally does not cover every change type in
`.ai/managed/core/ASSURANCE_LEVELS.md`. Bug, Refactoring, Security, Performance,
and Migration have no template, so they have no label; change type is recorded in
the issue body and pull request rather than by label. GitHub's default labels
(`bug`, `enhancement`, and so on) remain available for ad-hoc use.

Issues closed before this taxonomy existed were deliberately not relabelled, so
older issues carry whatever label was available at the time.

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
