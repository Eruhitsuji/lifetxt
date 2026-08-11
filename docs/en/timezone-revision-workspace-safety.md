# Revision, Timezone, and Workspace Safety

This document describes the P0 safety layer added after the public Web/MCP revision foundation and the executable release policy.

## 1. Persistent revision migration telemetry

The Web server supports two explicit modes:

- `observe`: legacy Web writes without a revision remain temporarily accepted. Every fallback is persisted and returned with deprecation headers.
- `required`: every supported life.txt write must include `If-Match` or `X-Lifetxt-Expected-Revision`. Missing preconditions fail with HTTP 428 before the compatibility fallback can run.

Configure the mode and migration evidence:

```json
{
  "web": {
    "revision_mode": "observe",
    "revision_metrics_path": ".cache/lifetxt/revision-metrics.json",
    "revision_migration_window_days": 14
  }
}
```

Equivalent environment variables are:

```text
LIFETXT_REVISION_MODE
LIFETXT_REVISION_METRICS_PATH
LIFETXT_REVISION_MIGRATION_WINDOW_DAYS
```

The default metrics path is `.lifetxt-revision-metrics.json` beside the writable life.txt file. It is operational state, not authored life.txt content.

### Inspect migration evidence

```bash
lifetxt safety revisions life.txt --pretty
```

The report includes:

- total fallback count;
- counts by API endpoint;
- observation start and latest fallback time;
- configured zero-use window;
- `ready_to_require_revisions`;
- the metrics file revision.

The Web equivalents are:

```http
GET /api/revision-metrics
GET /api/revision-metrics/export
```

The export response includes `metrics_revision`, and the same value is returned in `X-Lifetxt-Metrics-Revision`.

### Reset an observation window

A reset is destructive operational state and therefore requires the metrics file's exact revision:

```bash
lifetxt safety revisions life.txt \
  --metrics-path .cache/lifetxt/revision-metrics.json \
  --reset \
  --expected-hash <sha256>
```

A stale hash fails instead of erasing newer evidence.

### Migration rule

Do not switch to `required` merely because the server supports it. First reset or start a documented observation window, migrate all supported clients to revision discovery and `If-Match`, and wait until `ready_to_require_revisions` is true. The report requires both:

1. zero fallback use; and
2. a complete configured observation window.

## 2. Shared timezone policy

The resolved timezone follows this precedence:

1. CLI `--timezone` override;
2. `#! timezone:` in the workspace file;
3. `defaults.timezone` in configuration;
4. host timezone.

CLI, extended CLI commands, Web requests, MCP JSON-RPC requests, and legacy comparison helpers share the resolved timezone context.

### Shared deterministic fixture matrix

`tests/timezone_fixture_matrix.py` is the single source for stable timezone and
clock expectations. It covers CLI/file/config/host precedence, aware and naive
values, time-only anchors, DST gaps and folds, non-hour offsets, local midnight,
historical transition behavior, and positive/negative remote clock skew limits.

CLI, TUI, Web, and MCP resolve timezone policy through `timezone_policy`; the
fixture-driven core tests therefore cover their shared interpretation boundary.
Notifications, import/export, projects, tickets, events, time entries, and work
sessions consume timezone-aware parser/time utility values and do not maintain a
second parser. Remote writable requests use the shared `clock_skew` boundary;
authenticated session and audit binding is tracked separately in #311.

On Windows, named IANA zones are resolved only through `zoneinfo` and the
declared `tzdata` dependency. `dateutil` and `pytz` are deliberately not
fallbacks, so a missing declared provider fails loudly instead of changing
timezone behavior by accident.

Inspect the policy:

```bash
lifetxt safety timezone life.txt --pretty
```

Interpret a sample value:

```bash
lifetxt safety timezone life.txt \
  --sample 2026-11-01T01:30 \
  --fold-policy later \
  --pretty
```

### Authored value rules

- Offset-aware datetimes retain their authored instant and are converted to the resolved timezone for display/comparison.
- Naive datetimes are interpreted as wall time in the resolved timezone.
- Time-only values must be anchored to a date before timezone conversion.
- Non-hour offsets such as `Asia/Kathmandu` (`+05:45`) are preserved.

### DST folds

A repeated wall time is ambiguous. The default policy is `error`. Callers must choose:

- `earlier`: first occurrence;
- `later`: second occurrence.

### DST gaps

A skipped wall time does not exist. The default policy is `error`. Callers may choose:

- `next`: first valid minute after the gap;
- `previous`: first valid minute before the gap.

Gap adjustment is bounded to three hours so a configuration error cannot silently move a record by an arbitrary amount.

## 3. Compensated multi-target transactions

`lifetxt.multi_target` provides a dependency-free transaction contract for operations that affect more than one file, including:

- timer JSON state plus its associated life.txt item;
- attachment create/update/delete plus the life.txt reference.

The implementation:

1. sorts targets by absolute path and acquires every sidecar lock in that order;
2. verifies every expected revision before any write;
3. stages and validates every replacement before any write;
4. commits and verifies each target;
5. compensates already committed targets in reverse order if a later target fails;
6. raises `MultiTargetCommitError` and exposes every rollback error.

This is not a claim of portable filesystem-level atomicity across unrelated files. A process or machine crash during commit may require recovery from backups or a future durable transaction journal. The current guarantee is in-process detection, ordered locking, preflight validation, verified commit, and explicit compensation.

### Timer and item example

```python
from lifetxt.multi_target import timer_and_item_transaction
from lifetxt.mutation import read_text_snapshot

result = timer_and_item_transaction(
    "timer.json",
    lambda state: {"running": True, "item_id": "T-1"},
    read_text_snapshot("timer.json").content_hash,
    "life.txt",
    lambda text: text.replace("[ ] T Focus", "[/] T Focus"),
    read_text_snapshot("life.txt").content_hash,
)
```

The capability matrix must continue to report timer/attachment revision enforcement as incomplete until existing public timer and attachment handlers use this contract end to end.

## 4. Workspace diagnostics

The stable workspace diagnostics add these codes:

| Code | Meaning |
|---|---|
| `F111` | Malformed metadata directive |
| `F112` | Tab in leading indentation |
| `F113` | Indentation not divisible by two spaces |
| `F114` | Invalid timezone directive |
| `F115` | Duplicate ID across active/archive files |
| `F116` | Dangling link |
| `F117` | Missing parent |
| `F118` | Dependency cycle |
| `F119` | Corrupt timer state |
| `F120` | Unsafe or mismatched write target |
| `F121` | Persisted legacy revision fallback use |
| `F122` | Corrupt revision telemetry |

Diagnostics preserve stable `source`, `line`, `column`, `span`, `code`, `severity`, `message`, and `hint` fields and are sorted deterministically.

## 5. Integrated doctor

Run the integrated report:

```bash
lifetxt doctor life.txt \
  --archive archive.txt \
  --timer-state .cache/lifetxt/timer.json \
  --revision-metrics .cache/lifetxt/revision-metrics.json \
  --pretty
```

The report includes:

- workspace read/write targets;
- timezone policy;
- revision migration readiness;
- active/stale lock evidence;
- stable workspace diagnostics;
- optional dependency availability.

### Stale lock cleanup

Inspection is read-only by default. A cleanup request without `--force` only reports the plan:

```bash
lifetxt doctor life.txt --cleanup-stale --stale-after 300 --pretty
```

Removal requires both flags:

```bash
lifetxt doctor life.txt \
  --cleanup-stale \
  --force \
  --stale-after 300 \
  --pretty
```

Before unlinking, doctor rechecks that the lock is still proven stale and that inode, size, and modification time did not change.

## 6. Published schemas

The schema bundle now contains 21 Draft 2020-12 documents. New documents cover:

- revision metrics;
- timezone policy;
- workspace diagnostics;
- doctor output;
- multi-target results;
- JSON exports;
- proposals;
- saved views;
- remote profiles;
- groups;
- per-recipient delivery state;
- transaction journal and recovery;
- strict timer operations;
- redacted support bundles;
- revision-migration evidence.

Generate the authoritative bundle:

```bash
lifetxt format schemas dist/schemas --pretty
```

The release gate checks generated-versus-published equality, validates representative instances, and resolves local `$ref` links among published schemas.

## Scope boundaries

This batch does not claim completion of:

- removal of observe mode before a real zero-use migration window;
- existing CLI/TUI quick capture, archive, and undo handler migration;
- public timer and attachment handler integration;
- durable crash-recovery journals for multi-target commits;
- real terminal, browser-engine, fzf/peco, or SMTP verification;
- full replacement of every direct `datetime.now()` boundary in recurrence, timer, notification, and completion code.

## Practical migration sequence

1. Run `lifetxt safety timezone` to confirm the resolved timezone source.
2. Run `lifetxt safety revisions` while Web revision mode is still `observe`.
3. Migrate clients to revision discovery and `If-Match`.
4. Wait for a complete zero-fallback observation window.
5. Switch Web revision mode to `required` only after the report says `ready_to_require_revisions`.
