# Multi-Agent Development Standard

This standard supports humans and multiple AI tools working in parallel.

## Core Rule

```text
1 Issue = 1 executor = 1 branch/worktree = 1 pull request
```

## Roles

- Orchestrator: decomposes work and assigns dependencies
- Architect: defines shared contracts before parallel implementation
- Implementer: changes files within the assigned write scope
- Reviewer: reviews without final approval responsibility for own work
- Tester: verifies behavior and expands test coverage
- Integrator: handles shared files, conflicts, and integration order

Tasks may run in parallel only when there is no blocking dependency, write scopes do not overlap, shared contracts are stable, shared files have an owner, and each executor uses a dedicated branch/worktree.

Do not let multiple executors use the same worktree, push to the same branch, include unrelated issues in one pull request, change outside write scope, or let an implementing AI be the final approver.
