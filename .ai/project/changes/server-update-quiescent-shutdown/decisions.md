# Decisions

- Keep initial active-state observation solely as the restoration contract.
- Stop every configured unit because `systemctl stop` is idempotent for an
  already-inactive unit and removes reliance on a stale observation.
- Require a positive post-stop non-active result; command errors or empty state
  output fail before backup or code mutation.
- Keep list ordering explicit instead of inferring arbitrary timer dependencies.

