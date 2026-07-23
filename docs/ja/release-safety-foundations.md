# リリース安全性とFormat 1.0基盤

この実装では、remote writeやFormat 1.0を安定版とする前に必要な、依存なしで動作する安全性サービスを追加します。

## revision必須操作

`lifetxt.safe_ops` は次の7操作契約を提供します。

- `quick_capture`
- `item_update`
- `mcp_write`
- `notification_acknowledgement`
- `timer_state`
- `archive`
- `undo`

すべての操作で `expected_hash` が必須です。省略時は `ExpectedRevisionRequired`、古いhashを渡した場合は `MutationConflict` が発生します。text transformはlock取得後の最新textに対して実行されます。timerのJSON stateにも同じ規則を適用します。

```python
from lifetxt.mutation import read_text_snapshot
from lifetxt.safe_ops import quick_capture

snapshot = read_text_snapshot("life.txt")
quick_capture(
    "life.txt",
    "[ ] T Review release id:T-review",
    expected_hash=snapshot.content_hash,
)
```

## safetyコマンド

### mutation lockの確認

```bash
lifetxt safety locks life.txt --stale-after 300 --pretty
```

lock所有者metadata、経過時間、ローカルで確認できる場合のPID生存状態、staleであることが証明できるかを表示します。このコマンドはlockを削除しません。

### serverのread/write対象診断

```bash
lifetxt safety serve-target life.txt --write-file shared/life.txt --pretty
```

serverが読み込むfileと書き込むfileが異なる場合に警告します。また、`C:relative\life.txt` のようなWindowsのdrive-relative pathも検出します。

### timezone precedence

```bash
lifetxt safety timezone life.txt --timezone Asia/Tokyo --pretty
```

timezoneの優先順位は次の通りです。

1. CLI override
2. `#! timezone:` file directive
3. configの `defaults.timezone`
4. host timezone

IANA timezone名は `zoneinfo` で検証します。datetime値自身に明示的offsetがある場合、そのoffsetは該当値について優先されます。

### write route監査

```bash
lifetxt safety write-routes --root . --pretty
lifetxt safety write-routes --root . --strict
```

Python ASTを解析し、低レベルmutation境界以外にある直接 `os.replace`、`atomic_write_bytes`、write modeの `open` を報告します。`--strict` ではfindingがある場合にnon-zeroで終了します。

### release gate

```bash
lifetxt safety release-gate life.txt --root . --pretty
```

次の項目をまとめて確認します。

- 古いhashを拒否する実行可能CAS probe
- timezone-aware datetimeのround trip
- golden corpusの存在
- packaging metadataの存在
- 公開schema bundleの存在
- write routeのfinding
- 指定fileの安定format diagnostics

## Format 1.0 draftコマンド

### versionとpolicyの確認

```bash
lifetxt format info life.txt --pretty
```

現在のdirectiveは次の通りです。

```text
#! format_version: 1
```

version未指定fileはcompatibility modeで引き続き読み込めます。未対応versionは診断され、migration前に書き換えてはいけません。

Draft canonical formの名称は `LIFETXT_CANON_V1` です。

- BOMなしUTF-8
- LF line ending
- Unicode NFC normalization
- 行末space/tabなし
- 非空file末尾にLFを1つ
- identifier/valueはcase-sensitive
- canonical detail keyはlowercase
- metadata precedenceはCLI、file directive、config、built-in default

### 安定JSON diagnostics

```bash
lifetxt format check life.txt --pretty
```

各diagnosticは `severity`、`code`、`message`、`source`、`line`、`column`、`span`、`hint` を持ちます。parser diagnosticsとFormat 1.0 policy diagnosticsを同じresponse shapeで返します。

### canonical checkとrepair

```bash
lifetxt format canon life.txt --pretty
lifetxt format canon life.txt --write --pretty
```

`--write` は検査時の正確なhashを使って修復します。検査後に別の変更が入った場合は上書きせずconflictになります。

### schema bundle

```bash
lifetxt format schemas dist/schemas --pretty
```

初期versioned schemaは次を対象にします。

- item payload
- diagnostic
- capability document
- conflict response

各schemaはJSON Schema draft 2020-12とHTTPS `$id`を使用します。

## capability document

```bash
lifetxt capabilities --authentication token --pretty
lifetxt capabilities --read-only --authentication session --pretty
```

versioned responseには、format・canonical・schema version、対応operation、authentication mode、read-only状態、writable target、optional feature、SHA-256 revision precondition対応を含みます。これは今後のremote clientの基礎契約です。
