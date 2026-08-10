# AI-Human Interaction Standard

The standard is optimized for AI-assisted operation. Humans should not need to
read every standard document before getting useful guidance.

## Presentation Types

AI messages should use one of these types:

- Information
- Recommendation
- Decision Request
- Blocker
- Completion and Next Action

## Required Decision Context

For important judgments, the AI must present:

- current state
- evidence inspected
- facts
- assumptions
- recommendation
- alternatives
- risks
- applicable Rule IDs
- required human approval
- next action

Ask one to three questions at a time and include one recommended option when a
decision is needed.

## Human Approval Required

Explicit human approval is required for:

- requirements change
- scope change
- public API change
- data model change
- data migration or deletion
- authentication or authorization change
- security exception
- external service or cost addition
- destructive operation
- merge
- release
- deployment
- rollback
- retirement

## Supervised Autonomous Batch Execution

When a human directs an AI to work through a batch of open work and states they
will be unavailable for further check-ins afterward, sequence the interaction
as follows instead of either asking before every step or never asking at all:

1. Investigate and triage every candidate item first (read issue bodies and
   comments, check for blockers, confirm current repository state).
2. Identify the decisions in that batch that genuinely require human judgment
   under "Human Approval Required" above or under `AI_PERMISSIONS.md` --
   not routine implementation details already decided by existing standard
   guidance.
3. Ask all of those questions in one batched round, each with a stated
   recommendation and tradeoff, so the human can answer everything before
   stepping away, per "Required Decision Context" above.
4. Execute the full batch afterward without further interruption: self-scope
   any newly discovered work into its own tracked issues (see `REVIEW.md`'s
   "Horizontal Review Scope Discipline" for the same discipline applied to
   discovered issues), write right-sized task contracts, verify each change
   directly rather than relying on tests alone, and complete a security review
   before finalizing each change.
5. Report a complete summary and stop at a natural boundary -- an open,
   mergeable pull request -- rather than merging autonomously. Merge, release,
   deployment, and every other item under "Human Approval Required" remain
   human-only regardless of the earlier batched approval; that approval covers
   scoping the work, not the approval-required actions themselves.

This pattern only changes how the pre-work scoping conversation is sequenced.
It does not add, remove, or relax any item in "Human Approval Required".

## Proactive Triggers

AI tools should proactively guide the user when they detect:

- unclear requirement
- missing acceptance criteria
- possible duplicate feature
- task too large
- unresolved design decision
- overlapping write scope
- security impact
- compatibility impact
- before merge
- before release
- before deployment
- operational risk
- blocked work
