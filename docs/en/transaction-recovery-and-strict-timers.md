# Transaction Recovery and Strict Timer Writes

This document describes the durable recovery layer added on top of the compensated multi-target transaction contract. It covers transaction journals, explicit recovery actions, strict timer revisions, revision-metrics relocation, deterministic clocks, diagnostics, schemas, and support bundles.

## 1. Why a durable journal is required

`lifetxt.multi_target` locks every target, validates every expected revision, stages all replacements, commits in a deterministic order, and compensates already committed targets when a later write fails in the same process. A process termination, power loss, or operating-system failure can still interrupt that sequence.

A transaction journal records enough exact evidence to inspect and recover that interruption without guessing. It does not claim that unrelated files share one portable filesystem transaction.

## 2. Journal location and contents

The default journal directory is `.lifetxt-transactions` beside the writable life.txt file. It can be overridden by configuration or environment:

```json
{
  "transactions": {
    "journal_dir": ".cache/lifetxt/transactions"
  }
}
```

```text
LIFETXT_TRANSACTION_JOURNAL_DIR
```

Each transaction receives a unique directory containing `journal.json` plus exact before/after binary artifacts. The versioned journal records:

- transaction ID and operation name;
- target path and target kind;
- expected, before, and after SHA-256 revisions;
- whether a target existed before or is deleted after;
- artifact names and hashes;
- commit and compensation progress;
- created, updated, and terminal timestamps;
- terminal or recovery-required state;
- the last observed error.

Journal and artifact writes use file fsync, atomic replace, and parent-directory fsync ordering.

## 3. Journal states

Terminal states are:

- `committed`: every target matches the recorded after revision;
- `compensated`: every target was restored to its recorded before revision;
- `abandoned`: the transaction was explicitly abandoned after complete recovery evidence was backed up.

Recovery states include `prepared`, `committing`, `compensating`, `recovery_required`, `resume_failed`, and `compensation_failed`.

A recovery action refuses to overwrite a target when its current hash matches neither the recorded before revision nor the recorded after revision. Manual inspection is required in that case.

## 4. Inspect and recover transactions

List all journals:

```bash
lifetxt safety transactions list --pretty
```

Use a configured directory explicitly:

```bash
lifetxt safety transactions list \
  --journal-dir .cache/lifetxt/transactions \
  --pretty
```

Inspect one transaction by ID or journal path:

```bash
lifetxt safety transactions inspect \
  --journal TX_ID \
  --pretty
```

Resume remaining commits only when every target still matches an allowed recorded state:

```bash
lifetxt safety transactions resume --journal TX_ID --pretty
```

Restore all targets to their before revisions:

```bash
lifetxt safety transactions compensate --journal TX_ID --pretty
```

Abandon only after writing a complete backup of the journal and artifacts:

```bash
lifetxt safety transactions abandon \
  --journal TX_ID \
  --backup-dir recovery-backups \
  --pretty
```

Export metadata and hashes without embedding the binary artifacts:

```bash
lifetxt safety transactions export \
  --journal TX_ID \
  --output transaction-evidence.json \
  --pretty
```

Remove old terminal journals only with an explicit force flag:

```bash
lifetxt safety transactions cleanup \
  --older-than-days 30 \
  --force \
  --pretty
```

Non-terminal journals are never removed by retention cleanup.

## 5. Doctor and stable diagnostics

`doctor --workspace-safety` discovers the transaction directory, lists journal states, and treats a recovery-required transaction as a hard failure:

```bash
lifetxt doctor --workspace-safety life.txt \
  --journal-dir .cache/lifetxt/transactions \
  --pretty
```

New stable diagnostics are:

| Code | Meaning |
|---|---|
| `F123` | Transaction journal is unreadable or structurally corrupt |
| `F124` | Commit was interrupted and explicit recovery is required |
| `F125` | Compensation was interrupted or failed |
| `F126` | A target diverged from both recorded before and after revisions |

Doctor can also clean old terminal journals with `--cleanup-transactions`, `--transaction-retention-days`, and `--force`.

## 6. Redacted support bundles

A support bundle contains versions, hashes, diagnostics, policy output, and recovery metadata while excluding authored life.txt content, transaction artifacts, credentials, cookies, tokens, and raw absolute paths.

```bash
lifetxt doctor --workspace-safety life.txt \
  --support-bundle lifetxt-support.json \
  --pretty
```

Absolute paths are replaced with deterministic path pseudonyms. Review a bundle before sharing it because operational metadata can still reveal environment characteristics.

## 7. Strict timer revision contract

Timer operations can touch both timer JSON state and life.txt. Start and stop therefore use two revisions. Pause, resume, and cancel use the timer-state revision.

Discover current revisions through timer status, then send them with the mutation. In required mode, a missing revision fails before any write. A stale revision returns a conflict. A successful response returns both current revisions and transaction evidence.

CLI examples:

```bash
lifetxt timer start life.txt --id T-1 \
  --item-revision ITEM_SHA256 \
  --timer-revision '<missing>'

lifetxt timer stop life.txt \
  --item-revision ITEM_SHA256 \
  --timer-revision TIMER_SHA256

lifetxt timer pause --timer-revision TIMER_SHA256
```

Web request shape:

```json
{
  "action": "start",
  "item_id": "T-1",
  "item_revision": "ITEM_SHA256",
  "timer_revision": "<missing>"
}
```

MCP timer tools expose the same `item_revision` and `timer_revision` fields. The status response is the revision-discovery step for both Web and MCP clients.

The capability matrix remains conservative until every compound work-session and attachment path uses the same public contract.

## 8. Revision-metrics relocation and evidence

Revision migration metrics can be exported without revealing the local metrics path:

```bash
lifetxt safety revisions life.txt \
  --export-evidence revision-migration-evidence.json \
  --pretty
```

Move the persistent metrics store with an exact expected revision:

```bash
lifetxt safety revisions life.txt \
  --metrics-path old/revision-metrics.json \
  --relocate new/revision-metrics.json \
  --expected-hash METRICS_SHA256 \
  --pretty
```

Add `--delete-source` to move rather than copy. Source deletion is journaled with the destination creation so restart and upgrade migrations preserve the server instance ID, observation start, counters, and zero-use window.

## 9. Deterministic timezone clock

The timezone policy now provides context-local `now`, `today`, `utcnow`, and a deterministic `clock_context`. Major agenda, review, notification, timer, completion, journal, invoice, standup, Web, MCP, and CLI boundaries use this shared clock rather than consulting the host clock independently.

This enables one frozen instant to be interpreted in different configured zones and makes midnight, DST fold/gap, and non-hour-offset tests deterministic.

## 10. Published schemas and release evidence

The Draft 2020-12 bundle contains 21 documents. The five new contracts are:

- `transaction-journal-v1.schema.json`;
- `transaction-recovery-v1.schema.json`;
- `timer-operation-v1.schema.json`;
- `support-bundle-v1.schema.json`;
- `revision-migration-evidence-v1.schema.json`.

The release gate validates all generated and published schemas, all representative instances, duplicate `$id` rejection, and every local `$ref` through a network-free `referencing.Registry`.

## 11. Remaining boundaries

This implementation does not complete real power-loss fault injection, every legacy CLI/TUI/fzf write migration, every attachment handler, compound work-session capability enforcement, or real terminal/browser/SMTP/platform verification. Those items remain explicit P0 work.
