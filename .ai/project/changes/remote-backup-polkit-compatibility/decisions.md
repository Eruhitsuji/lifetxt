# Decisions

- Classify this follow-up as Security / High because it governs production
  systemd authorization and corrects an ineffective security artifact.
- Use Polkit 0.106 as the conservative minimum JavaScript `.rules` boundary.
- Fail closed on any compatibility uncertainty and provide no legacy fallback.
- Keep real authorization exercise as an explicit deployment gate because
  automatically starting a backup would violate plan-first dry-run behavior.
