# Write Scope Policy

Every implementation task must declare allowed write paths.

```yaml
write_scope:
  - "src/backend/auth/**"
  - "tests/backend/auth/**"

forbidden_scope:
  - "src/frontend/**"
  - "database/migrations/**"
  - "package-lock.json"
```

If required work falls outside write scope, stop and update the issue or create a follow-up issue.
