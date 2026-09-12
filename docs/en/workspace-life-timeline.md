# Workspace Life Timeline

`lifetxt timeline --workspace-timeline [path ...]` provides a bounded,
read-only chronological stream across the Native History records of all current
items in the selected workspace. It composes the existing per-item
`temporal-timeline-v1` reader; it does not inspect Git or infer history from
current fields.

Use `--since`, `--until`, `--event`, `--project`, and `--limit` to keep the
query bounded. JSON output uses `workspace-life-timeline-v1` and includes
target/source provenance, `bounds.truncated`, diagnostics, limitations, and
workspace completeness. A partial or manually edited source is never reported
as globally complete.
