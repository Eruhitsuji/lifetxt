# Decisions

- Owner explicitly approved the proposed endpoint/parameters/local auth boundary in this conversation at 2026-10-08 21:21 JST; recorded on issue1146.
- Keep High assurance and name Eruhitsuji for independent final-head implementation/integration review; self-review is not independent approval.
- Extend existing cap-daily-flow-planner-lite and reuse merged core unchanged.
- No break/buffer/limit/timezone overrides; core zero-rest/hard limits remain canonical.
- Candidate filters never remove authorized busy or dependency context.
- Exact-route runtime exclusions are necessary for no-write/safe-corrupt-read/denied-auth contracts; no existing route changes.
- Return shared model for partial/blocked computation; callers inspect completeness, not status alone.
- Public/local full-workspace admission stays distinct from Remote principal visibility; no claim of individual-record ACL enforcement.
