# AI Permissions Standard

AI tools operate with least privilege. Permissions should support investigation,
implementation, validation, and review without giving AI final authority over
protected actions.

## Allowed by Default

When permitted by the local environment and repository policy, AI may:

- read repository files
- inspect Git status and diffs
- create local branches or worktrees for assigned tasks
- edit files within write scope
- run declared project commands
- draft issues, pull requests, plans, tests, and review reports

## Requires Human Approval

AI must request explicit human approval before:

- destructive filesystem or Git operations
- dependency-wide migrations
- force push or history rewrite
- changing repository permissions, rulesets, or secrets
- accessing external paid services
- deploying, releasing, rolling back, or retiring systems
- accepting security exceptions or major risks

## Prohibited

AI must not:

- bypass branch protection or Rulesets
- be the sole final approver of its own work
- store secrets in repository files, prompts, issues, PRs, logs, or artifacts
- resolve semantic conflicts without understanding and recording the decision
- claim a command passed unless it was executed
