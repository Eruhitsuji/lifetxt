# Decisions

- Extend the existing `lifetxt remote` client rather than introduce another sync client.
- Require explicit server capability and policy admission before every ordinary-item write.
- Fetch a fresh authoritative snapshot revision immediately before each mutation.
- Keep the client online-only and stateless: no replica, cache, offline queue, or automatic merge.
- Reuse structured non-retrying conflict output and exit code 3.
- Keep transaction IDs optional for interactive convenience while allowing callers to supply a stable ID for safe replay.
