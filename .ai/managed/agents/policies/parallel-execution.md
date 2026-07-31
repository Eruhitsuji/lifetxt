# Parallel Execution Policy

Parallel execution is allowed only when there is no unresolved dependency, write scopes do not overlap, shared contracts are already merged or frozen, shared files are assigned to an Integrator, each executor has a separate branch/worktree, and each deliverable has a separate pull request.

High conflict-risk tasks should be serialized or moved behind an Architect or Integrator task.
