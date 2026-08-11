# Safe writes, attachments, and compound work sessions

この文書は durable transaction foundation の後に追加された revision-aware write routes を説明します。`life.txt` を authoritative に保ち、authoritative mutation は single-file semantic CAS または journal-backed multi-target transaction として扱います。

## Semantic write contract

shared write layer は target lock を保持した状態で transformations を実行します。strict conflict detection が必要な caller は expected SHA-256 revision を渡します。

対象例:

- append-only captures and journal entries
- ID-addressed item updates and deletion
- TUI/fzf/peco actions grouped by source file
- revision-checked restore and undo
- tag merge across `life.txt` and configuration aliases
- digest/template append operations
- multi-file archive operations

stale expected revision は structured mutation conflict です。multi-file operation は first commit 前に replacements を stage し、durable transaction journal を記録します。partial commit 後の failure は transaction commands で recover できます。

## Attachment transactions

attachment files は configured attachment root に confined されます。file operation と `life.txt` reference は一緒に commit されます。

- `put`: bytes を attachment root へ copy し item reference を add/update
- `reference`: confined existing file を revision validation 後に attach
- `delete`: file と item reference を一緒に remove
- `status`: mutation なしで item/attachment revisions を report

default では path escape、symlink、executable/script-like files、stale revisions を reject します。`--allow-symlink`、`--allow-executable` は unsafe-policy overrides であり、untrusted paths/content には使わないでください。

## Compound work sessions

work session は task state、timer state、presence を one recoverable operation として update します。start は task を in-progress にし、timer state と presence record を作れます。stop は timer state を delete し、elapsed time を追加し、必要なら task を complete し、presence を close できます。

CLI、Web、MCP は同じ item/timer revision contract を使います。

```bash
lifetxt start T-1 life.txt \
  --item-revision <life-sha256> \
  --timer-revision '<missing>' \
  --require-revisions
```

```bash
lifetxt stop life.txt \
  --item-revision <life-sha256> \
  --timer-revision <timer-sha256> \
  --require-revisions
```

response には transaction ID、journal path、recovery state、new target revisions が含まれます。

## Verified operator notes

- revision precondition は、後で mutate する同じ source set から取得した場合だけ意味があります。
- attachment bytes と life.txt metadata の両方を触る write は transaction として扱ってください。
- Workflow の日付・時刻判断には shared context-local timezone clock を使います。
