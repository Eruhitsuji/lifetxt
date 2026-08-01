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
