# Decisions

D1-D3 approved by owner in #1143. User explicitly requested #1144 through PR.
High assurance for shared versioned output; no public endpoint or schema. S scope
is one pure composition purpose, with transport/snapshot IO separately tracked.

Existing CLI rank seam is imported directly, avoiding unneeded CLI edits or copied
priority logic. Source paths are lexically normalized; actual path admission/
symlink/case resolution belongs to callers. Parsed hashes never pretend to be
file byte revisions. Source retries/auth/visibility stay in future consumers.

Self-review fixes: bound on x at before materialization, physical-row source alias
deduplication, distinct no-line event provenance, deterministic invalid-ID snapshots,
self dependency blocking, parser-error occupancy uncertainty, and bounded text.

Alternatives rejected: generic solver, deadline-first/importance score, estimated
remaining duration, automatic split or runtime/file import. Existing contract explains
tradeoffs; conservative unknown occupancy and full estimate may reduce usefulness.

Independent review and merge authorization still required for final implementation
head. Do not claim implementing AI's self-review is independent approval.
