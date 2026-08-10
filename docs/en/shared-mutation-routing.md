# Shared mutation routing

All authoritative text and JSON replacement writes now enter through the shared mutation contract in `lifetxt.mutation` (`lifetxt/mutation.py`).

## Compatibility boundary

Existing modules historically imported these helpers:

```python
from lifetxt.atomic import atomic_write_text, atomic_write_json
```

Those names remain supported. They are now compatibility facades over `mutation.write_text` (see `lifetxt/atomic.py`), so callers receive the shared behavior without changing their public API immediately:

- a per-target sidecar lock;
- an in-lock reread of the current bytes;
- detection of a file that changes while the transform is running;
- atomic byte replacement;
- permission preservation where supported;
- post-write hash verification;
- UTF-8 BOM and existing newline preservation when the shared writer updates an existing file.

`atomic_write_bytes` is different. It is the internal commit primitive used after the shared mutation lock has been acquired. Application and surface code must not call it directly.

The fzf/peco helper was the one remaining life.txt writer that used `open(..., "w")` directly. A narrow compatibility bridge now replaces that helper at package initialization, which also covers the TUI status and delete actions that reuse it.

## The sidecar lock

`apply_text_mutation` acquires a `lifetxt.mutation.FileLock` before touching the target. The lock is a cross-platform sidecar file created with exclusive creation (`O_CREAT | O_EXCL`), so it works the same way on Windows and POSIX without a third-party dependency:

```text
<target-path>.lifetxt.lock
```

The lock file holds small JSON metadata written and fsynced before the writer proceeds:

```json
{
  "version": 1,
  "token": "HOSTNAME-1234-1699999999000000000",
  "pid": 1234,
  "host": "HOSTNAME",
  "operation": "task.create",
  "target": "/abs/path/life.txt",
  "created": "2026-08-10T10:00:00Z"
}
```

Default lock behavior (`lifetxt.mutation` module constants):

| Constant | Default | Meaning |
|---|---|---|
| `DEFAULT_LOCK_TIMEOUT` | `5.0` seconds | How long a caller waits for a contended lock before giving up |
| `DEFAULT_POLL_INTERVAL` | `0.05` seconds | How often the waiting caller retries lock creation |
| `DEFAULT_STALE_LOCK_AFTER` | `300.0` seconds | Minimum age before a lock is even considered for stale-lock recovery |

Stale-lock recovery is conservative. A lock is only removed and retried when *all* of the following hold: it is older than `stale_after`, its `host` matches the current host (a lock from another machine is never touched), its `pid` is confirmed **not** running on this host, and the lock file's `mtime`/inode/size are unchanged between the staleness check and the removal (so a lock that was just released and immediately re-acquired by someone else is not clobbered). If any of those checks fails, the caller keeps waiting until `timeout` and then raises `LockTimeout`, whose message embeds the current lock owner's JSON metadata so an operator can tell which process (host/pid/operation) is holding the file.

A caller that never explicitly releases the lock (a hard crash, `kill -9`, or a Windows-forced termination) leaves the lock file behind; the next writer either waits out `stale_after` and recovers it automatically (if the owning process is confirmed dead) or, if the check cannot confirm the owner is dead (host mismatch, or the process query is inconclusive), waits the full `timeout` and surfaces `LockTimeout` for a human to resolve. This is a liveness fallback, not a distributed lock manager -- it does not protect against two different real writers running concurrently in a way that a plain sidecar lock could not already handle; see `lifetxt safety locks` (`lifetxt.extra_safety`) for a CLI view of currently held locks and their ages.

## What one call to `apply_text_mutation` actually does

In order, `apply_text_mutation(path, operation, expected_hash=...)`:

1. Acquires the sidecar lock for `path`.
2. Reads the current bytes as a `TextSnapshot` (`before`). If the file does not exist and `operation.create` is false, raises `FileNotFoundError`.
3. If `expected_hash` was supplied and it does not equal `before.content_hash`, raises `MutationConflict` immediately -- the transform never runs against stale content.
4. Runs `operation.transform(current_text)` to compute the replacement text, then `operation.validate(replacement)` if a validator was supplied.
5. Encodes the replacement using the *existing* file's encoding/BOM (or the caller's defaults for a newly created file) and computes its hash.
6. Re-reads the file one more time (`latest`) and compares its hash to `before.content_hash`. This is the guard against a writer that bypassed the lock (or a filesystem quirk) changing the file between steps 2 and 6; a mismatch raises `MutationConflict` even though no `expected_hash` was ever supplied by the caller.
7. Commits through `atomic_write_bytes` only if the computed replacement differs from the current content -- a semantic no-op transform does not touch the file or its mtime.
8. Reads the file back once more and confirms its hash matches what was just written, raising `MutationConflict` (labeled `"<operation> post-write verification"`) if it does not -- catching a corrupted or interfered-with commit rather than reporting success on faith.
9. Releases the lock and returns a `MutationResult(path, operation, before_hash, after_hash, changed, created, snapshot)`.

Steps 3 and 6 are two different conflict checks with two different jobs: step 3 rejects a caller working from a version of the file it already knew was stale; step 6 catches an unexpected change that happened *during* the lock -- something that should be structurally impossible if every writer routes through this same layer, but is checked rather than assumed.

## Covered surfaces

The routing regression suite (`tests/test_shared_surface_mutation_routing.py`) verifies writes originating from:

- the atomic text and JSON compatibility APIs;
- the fzf/peco direct-writer replacement;
- TUI `_mutate_rows` status changes;
- TUI presence status transitions;
- timer-backed item updates;
- Web message acknowledgement;
- MCP item creation.

Web and MCP write helpers already converge on the Web file helpers, which converge on the atomic compatibility API. Timer and most TUI operations also use the atomic API. As a result, those paths now share one lock and commit implementation. The Web/MCP layer adds its own optimistic-concurrency contract (ETag/If-Match, `expected_file_hash`) on top of this one; see [public-surface-revisions.md](public-surface-revisions.md).

## Optimistic concurrency is still explicit

Routing a replacement through the shared layer prevents simultaneous commits and detects a change that happens during the locked transform. It does not automatically know which older file version a caller used to calculate a prebuilt replacement.

Callers that read first and write later must capture a snapshot and pass its hash:

```python
from lifetxt.mutation import mutate_text, read_text_snapshot

snapshot = read_text_snapshot("life.txt")
result = mutate_text(
    "life.txt",
    lambda current: current + "[ ] T New task\n",
    expected_hash=snapshot.content_hash,
    operation="task.create",
)
print(result.after_hash)
```

A stale hash raises `MutationConflict` instead of overwriting the newer file. Verified against a real fixture, a stale hash reproduces exactly this:

```pycon
>>> mutate_text("life.txt", lambda t: t + "x", expected_hash="0" * 64, operation="task.create")
Traceback (most recent call last):
  ...
lifetxt.mutation.MutationConflict: task.create conflict for /abs/path/life.txt: expected content hash 0000000000000000000000000000000000000000000000000000000000000000, found 56421fc3a950440da9132becd234f37007c7467c68904813ed3504ca854034f9. Reload the file and retry.
```

Adding operation-specific expected hashes and concurrent stale-writer tests for quick capture, item update, MCP, acknowledgement, timer, archive, and undo remains an ongoing release-safety task; check `tests/test_shared_surface_mutation_routing.py` for the current coverage before assuming a given surface already enforces this.

## `mutate_text`, `write_text`, and `mutate_json`

`mutate_text` is a thin convenience wrapper that builds a `MutationOperation` from a bare `transform` callable and calls `apply_text_mutation`. `write_text` goes one step further and accepts either literal replacement `text=` (for callers doing a full-file replace, matching the old `atomic_write_text` contract) or a `transform=` callable (for callers that want to compute the replacement from the current in-lock content) -- never both:

```python
from lifetxt.mutation import write_text

# Full replacement, like the old atomic_write_text:
write_text("life.txt", "entirely new content\n", operation="cli.replace")

# Semantic transform, preferred for new code:
write_text(
    "life.txt",
    transform=lambda current: current + "[ ] T Another task\n",
    operation="cli.append",
)
```

`mutate_json` layers JSON parse/dump on top of the same text contract: it decodes the current text as JSON (or uses `default` when the file is empty/missing and `create=True`), calls `transform(value)` with the decoded value, and re-serializes the result with `json.dumps(..., indent=2, sort_keys=True)` by default (`pretty=False` switches to compact `(",", ":")` separators). This is the primitive `lifetxt.revision_telemetry` and the timer state writers build on.

Multi-file writes -- where more than one target must change together, such as an attachment operation that updates both the stored file and the `life.txt` reference -- are not expressed with `lifetxt.mutation` directly. They use `lifetxt.multi_target.apply_multi_target`, which stages one `MutationOperation`-like `TargetPlan` per file, locks every target (sorted by path, to avoid lock-ordering deadlocks), and optionally records a durable transaction journal. See [transaction-recovery-and-strict-timers.md](transaction-recovery-and-strict-timers.md) for the journal format and recovery commands, and [safe-writes-attachments-and-work-sessions.md](safe-writes-attachments-and-work-sessions.md) for the semantic write layer (`lifetxt.write_operations`) built on top of both.

## Migration rule for new code

New authoritative writers should import `lifetxt.mutation` directly and provide a semantic transform that runs against the current in-lock text. The atomic compatibility API is retained for existing replacement-style callers, not as the preferred API for new surface code.

## Related documents

- [public-surface-revisions.md](public-surface-revisions.md) -- how Web/MCP expose this same content-hash contract as `ETag`/`If-Match` and `expected_file_hash`.
- [transaction-recovery-and-strict-timers.md](transaction-recovery-and-strict-timers.md) -- the durable journal used when more than one file must change together.
- [safe-writes-attachments-and-work-sessions.md](safe-writes-attachments-and-work-sessions.md) -- the semantic write layer (`lifetxt.write_operations`) built on this contract for CLI/TUI/Web/MCP item, attachment, and work-session writes.
- [process-boundaries-attachments-and-transaction-admin.md](process-boundaries-attachments-and-transaction-admin.md) -- external-editor sessions, which apply their result through this same revision-checked write path.
