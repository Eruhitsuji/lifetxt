# 公開surfaceのrevision契約

Web APIとMCPによるlife.txt書き込みは、`lifetxt.mutation` と同じ楽観的並行制御契約を利用できます。

revision対応clientは、最初に現在の書き込み対象fileのrevisionを読み取ります。次の書き込みは、そのrevisionが現在も完全に一致する場合にだけ成功します。これにより、古いbrowser tabやMCP clientが新しいfileを黙って上書きすることを防ぎます。

## Web API

成功したすべての `/api/` 読み取りresponseには次が含まれます。

```http
ETag: "<sha256>"
X-Lifetxt-Revision: <sha256>
```

ETagはresponse作成時に使用した書き込み対象life.txtのsnapshotを示します。次のいずれかを読み取ると、clientはstrict revision契約へ移行します。

```http
GET /api/revision
GET /api/capabilities
```

その後、対応するlife.txt書き込みendpointでは次のいずれかが必須です。

```http
If-Match: "<sha256>"
```

または次を使用します。

```http
X-Lifetxt-Expected-Revision: <sha256>
```

最初のrequestからstrict動作を要求する場合は次を指定できます。

```http
X-Lifetxt-Require-Revision: true
```

組み込みWeb UIには小さな `fetch` bridgeを追加しています。revisionを取得し、対応する書き込みへ `If-Match` を追加し、response ETagから保持中のrevisionを更新します。

### Compatibility transition

revision契約をまだ取得しておらずrevisionも送信しないlegacy clientは、一時的に受け入れます。serverはrequest直前のrevisionを取得し、1つのCAS transactionとして処理し、次のwarningを返します。

```http
Warning: 299 lifetxt "Legacy write without client revision; fetch /api/revision and send If-Match."
```

このfallbackは既存local API clientを維持しますが、clientがさらに古いresponseを基に変更を作ったことまでは検出できません。新しいcodeは必ずrevisionを取得して送信してください。fallbackの削除は、client移行状況を確認した後のP0として残します。

### Strict modeでrevisionがない場合

strict書き込みにrevisionがない場合はHTTP 428を返します。

```json
{
  "error": "PRECONDITION_REQUIRED",
  "message": "An expected revision is required for this write.",
  "expected_revision": null,
  "current_revision": "...",
  "attempted_change": {
    "operation": "web.create",
    "path": "/absolute/path/life.txt"
  }
}
```

### 古いrevisionの場合

古い書き込みは、安定したconflict response形式でHTTP 409を返します。

```json
{
  "error": "CONFLICT",
  "message": "...",
  "expected_revision": "...",
  "current_revision": "...",
  "current_item": null,
  "attempted_change": {
    "operation": "web.update",
    "path": "/absolute/path/life.txt"
  }
}
```

現在状態をreloadし、新しいitemを確認してから意図的に再実行してください。lifetxtはこれを自動的なthree-way mergeとして扱いません。

### 複合書き込み

1回のWeb requestが複数の既存helperを呼び出す場合があります。例えばrepeat completionでは、完了itemを更新し、その次のoccurrenceを追加します。これらはmemory上でstageされ、最後に1回だけcommitされます。そのため、他のwriterが処理途中の半端な状態を観測することはありません。

## MCP

公開JSON-RPC書き込み前に `get_file_state` を呼び、返された `file_hash` を保持します。

```json
{
  "writable_path": "life.txt",
  "file_hash": "<sha256>"
}
```

revision保護対象toolの公開input schemaでは `expected_file_hash` が必須です。対象にはitem作成・更新・完了・削除、message作成・返信・acknowledgement・snooze、status変更、captureが含まれます。

```json
{
  "id": "T-42",
  "status": "[/]",
  "expected_file_hash": "<sha256>"
}
```

成功したJSON-RPC resultには新しい `revision` と `file_hash` が含まれます。revision不足・競合時はWeb APIと同じprecondition/conflict fieldを返します。

埋め込み用途の直接Python APIである `mcp.call_tool` は後方互換を維持します。strict契約は外部clientが使用する実際のMCP JSON-RPC `tools/call` 境界へ適用します。

MCP serverには次も追加しています。

- `get_capabilities`
- `lifetxt://capabilities`

format/schema version、operation matrix、read-only状態、書き込み対象、revision precondition対応を取得できます。

## Format version mutation guard

共有mutation入口は、現在textと置換後textの `#! format_version:` を確認します。未対応versionはinspectionのために読み取れますが、明示的なmigrationを実行するまでは `UNSUPPORTED_FORMAT_VERSION` としてmutationを拒否します。

version未指定fileはcompatibility modeで引き続き書き込み可能です。Format 1.0では次を使用します。

```text
#! format_version: 1
```

## Server target検証

Web application起動時に、設定されたread targetとwrite targetを検査します。

- 書き込み対象が読み込み対象と異なる場合、最初のrequestより前にwarningを出します。
- `C:relative\\life.txt` のようなWindows drive-relative targetは拒否します。`C:\\work\\life.txt` のようなabsolute targetを使用してください。

## Named review ranges

共有review resolverは次をサポートします。

- `last-week`
- `last-month`
- `year`

Web例：

```http
GET /api/review?range=last-week
GET /api/review?range=year&year=2026
```

MCP例：

```json
{
  "range": "last-month"
}
```

両surfaceは個別にdate計算を実装せず、`review.resolve_named_review_range` を使用します。

## 現在の境界

operation matrixでは、timerとattachment操作について完全なrevision enforcementを主張していません。これらはtimer JSON stateやattachment storageなど、書き込み対象life.txt以外も変更する可能性があります。同じatomicityを保証するにはmulti-target transaction設計が必要です。

実terminalでのTUI/fzf確認、SMTP配送test、browser engineを使ったaccessibility smoke test、全date境界へのtimezone適用、release gateのCI必須化、legacy Web fallbackの削除は別roadmap項目として残しています。
