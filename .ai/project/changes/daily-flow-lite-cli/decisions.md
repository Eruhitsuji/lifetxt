# Decisions

- 2026-10-08 20:26 JST: Eruhitsuji explicitly approved `flow [path ...]`, required
  `--date`, `--day-start`, `--day-end`, text default and `--format json` in the
  task conversation. Recorded on issue1145; D1-D3 already approved in issue1143.
- Reuse the merged PR1150 core without algorithm changes; today is not an alias.
- Raise assurance from proposed Standard to High for public CLI evidence; final
  human risk acceptance and implementation/integration review remain pending.
- Use existing workspace source resolution but explicitly exclude archive roles
  from automatic selection, because legacy input_paths includes archives.
- No additional timezone/evaluated-at/filter/policy flags or config keys. First
  input directive/config/host policy is reused; unresolved local/host fails.
- One bounded race retry. No write lock or cross-file atomicity claim.
- Self-review reproduced legacy timezone prescanning of excluded workspace
  archives (2 red regression tests). Add flow-only routing in the existing CLI
  dispatch module, within the issue's CLI-routing scope; old routes unchanged.
- Partial/blocked output is useful but nonzero, complete capacity failure is
  successful computation with visible unplaced reasons. Machine output is the
  unchanged canonical model, not an independently versioned CLI envelope.
