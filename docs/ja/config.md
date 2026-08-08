# 設定とワークスペース

lifetxt は、読み書きする life.txt ファイルや、タイムゾーン・名前などの既定値を
選ぶ JSON 設定ファイルを読み込みます。本ガイドは操作中心です。各キーの詳細は
`lifetxt config explain <path>` で確認できます。

## 探索順序

設定ファイルは次の順で探索されます。

1. コマンドラインの `--config PATH`
2. 環境変数 `LIFETXT_CONFIG`
3. カレントディレクトリの `.lifetxt.json`
4. カレントディレクトリの `lifetxt.config.json`

いずれも見つからない場合は `life.txt` を読み込みます。

## 最小構成

従来のトップレベル形式がそのまま使えます。

```json
{
  "paths": ["life.txt"],
  "write_file": "life.txt",
  "defaults": { "timezone": "Asia/Tokyo" }
}
```

トップレベルの `paths` と `write_file` は、暗黙のワークスペース `default` として
扱われます。既存の設定を変更する必要はありません。

## 優先順位

有効値は、低い順から高い順へ次のように解決されます。

1. 組み込みの既定値
2. 読み込んだ設定ファイル
3. 選択したプロファイル（`--profile NAME`）
4. 環境変数による上書き（`LIFETXT_TIMEZONE` などの明示的な許可リスト）
5. コマンドラインのフラグ

結果と各値の由来は次で確認します。

```console
$ lifetxt config effective            # マージ済み JSON（秘密情報はマスク）
$ lifetxt config sources              # 各キーとその由来
$ lifetxt config get defaults.timezone
$ lifetxt config explain web.port
```

## 名前付きワークスペース

ワークスペースは、ソースファイル群と書き込み先をまとめた名前付きの単位です。
`workspaces` に定義し、`default_workspace` で既定を選びます。

```json
{
  "default_workspace": "personal",
  "workspaces": {
    "personal": {
      "sources": [
        "life.txt",
        { "path": ".generated/calendar.life.txt", "role": "generated" }
      ],
      "write_file": "life.txt"
    },
    "work": {
      "sources": [{ "path": "work.life.txt", "role": "primary", "required": true }]
    }
  }
}
```

任意のコマンドでグローバルな `--workspace` フラグを使えます。

```console
$ lifetxt --workspace work agenda
$ lifetxt workspace list
$ lifetxt workspace show work
$ lifetxt workspace files --resolved
$ lifetxt workspace validate --all
```

## ソースマニフェストの項目

`sources` の各要素はパス文字列、またはオブジェクトです。オブジェクト形式は次を
サポートします。

| 項目             | 既定値           | 意味                                                 |
| ---------------- | ---------------- | ---------------------------------------------------- |
| `path`           | （必須）         | ファイル・ディレクトリ・グロブ                       |
| `role`           | `primary`        | `primary`/`input`/`generated`/`archive`/`readonly`/`reference`/`ticket_event`/`time_entry` |
| `required`       | `false`          | 必須ソースが無い場合はエラー                         |
| `writable`       | ロール依存       | generated/archive/readonly/reference は読み取り専用  |
| `default_visible`| ロール依存       | generated/archive は既定で非表示                     |
| `format`         | `life`           | ソース形式のヒント                                   |
| `priority`       | `100`            | 小さいほど入力順で先頭に来る                         |
| `watch`          | `true`           | ファイル監視の対象にするか                           |
| `privacy`        | `normal`         | 秘匿処理のためのプライバシー分類                     |
| `generated_by`   | `null`           | 生成ソースを作るツール名                             |
| `exclude`        | `[]`             | ディレクトリ/グロブ結果から除外するパターン          |

## ワークスペースの安全上限

ワークスペース解決では、unique な解決済みソースファイル全体に
`workspace.max_total_source_bytes` を適用します。既定値は `67108864` bytes
（64 MiB）です。広い glob を絞る、または生成ディレクトリを除外したうえで必要な場合だけ
引き上げます。

```json
{
  "workspace": { "max_total_source_bytes": 67108864 }
}
```

link-cycle 検出は glob 展開前に source path の prefix を確認し、recursive glob では
静的な glob root 配下の directory link も確認します。合計サイズ上限は、決定的な展開後に
unique な物理ソースファイルを `stat` して確認します。

## パス解決

相対パスは、カレントディレクトリではなく**設定ファイルのあるディレクトリ**を基準に
解決されます。そのため、どこから実行しても同じ結果になります。グロブは決定的に
（ソートして）展開されます。解決時には、必須ソース欠落（`WS001`）、物理ファイルの
重複（`WS002`）、設定ディレクトリ外のパス（`WS003`）、未知のロール（`WS005`）、
不正な書き込み先（`WS006`/`WS007`）、自己参照する symlink/junction cycle
（`WS014`）、`workspace.max_total_source_bytes` を超える合計ソース bytes（`WS015`）、
不正なサイズ上限設定（`WS016`）を診断として報告します。

## プロファイル

プロファイルは、基本設定の上に重ねる名前付きオーバーレイです。

```json
{
  "profiles": {
    "remote": { "defaults": { "timezone": "UTC" } }
  }
}
```

```console
$ lifetxt config effective --profile remote
```

## 設定の安全な編集

JSON を手で編集せずに、個別のキーを読み書きできます。

```console
$ lifetxt config set web.port 8080
$ lifetxt config unset web.port
```

値は可能なら JSON として解釈され（`8080` は数値、`"text"` は文字列）、
解釈できない場合は文字列として保存されます。

設定を書き戻すコマンドは、読み込んだファイルへ書く場合に compare-and-set を使います。
CLI が現在のファイル revision を読み取り、書き込みの前提条件として渡すため、
並行編集があれば上書きせずに拒否されます。

すべての設定書き込みに revision 前提条件を必須にする場合は
`config.write.require_revision` を設定します。

```json
{
  "config": { "write": { "require_revision": true } }
}
```

通常の `lifetxt config set|unset|migrate` で読み込んだファイルへ書く場合は、
コマンドが revision を自動検出するため動作は変わりません。別の `--output`
ファイルへ `--expected-revision` なしで書くなど、revision が無い書き込みは拒否されます。

## 認証情報

パスワードやトークンを設定に直接書かないでください。代わりに環境変数名を参照します。
たとえば SMTP は `smtp_pass_env: "LIFETXT_SMTP_PASS"` を使います。`config effective`、
`config sources`、サポートバンドルは、秘密情報らしいキーをマスクします。

## サンプル

実行可能なサンプルは `examples/config/` にあります。

- `personal.lifetxt.json`
- `work.lifetxt.json`
- `project-multi-file.lifetxt.json`
