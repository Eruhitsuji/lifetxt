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

`config.write.audit_log` を設定すると、境界付きの `.bak`/`.rejected` ローテーション
が保持しきれない範囲まで、設定書き込みの試行記録を永続的に残せます。

```json
{
  "config": {
    "write": {
      "audit_log": ".cache/lifetxt/config-write-audit.jsonl",
      "audit_max_bytes": 5242880
    }
  }
}
```

書き込みが成功・拒否のどちらの場合も、タイムスタンプ・パス・結果・関連する
revision のみを 1 行記録します。設定内容やキーの値は一切含まれないため、
シークレットを参照する設定の漏えい経路にはなりません。ファイルは
`audit_max_bytes` を超えると古い側から切り詰められます。`audit_log` を
未設定のままにすると、この記録は無効のままです。

## update check

`lifetxt update-check` は実行中の version を、repository の最新 GitHub
Release (未公開なら最新 tag) と比較します。既定値はこの project 自身の
repository ですが、fork では upstream ではなく自分自身の repository と
比較すべきです。

```json
{
  "update": { "repository": "your-github-username/your-fork" }
}
```

`--repo OWNER/NAME` flag を使うと、保存された既定値を変えずに1回だけ
上書きできます。

## 認証情報

パスワードやトークンを設定に直接書かないでください。代わりに環境変数名を参照します。
たとえば SMTP は `smtp_pass_env: "LIFETXT_SMTP_PASS"` を使います。`config effective`、
`config sources`、サポートバンドルは、秘密情報らしいキーをマスクします。

## サンプル

実行可能なサンプルは `examples/config/` にあります。

- `personal.lifetxt.json`
- `work.lifetxt.json`
- `project-multi-file.lifetxt.json`

## 最近の設定互換メモ

この節は英語版の追加内容に合わせた要約です。

- 設定値は、コマンドライン引数、環境変数、明示された設定ファイル、workspace 内の設定、既定値の順に解決します。`config show` と `config explain` は、値だけでなく由来も確認するために使います。
- `config init` は最小構成の作成に使います。既存ファイルを壊さないことを優先し、上書きが必要な場合は dry-run や差分確認を先に行います。
- `config set`、`config unset`、`config migrate` は revision を確認してから書き込みます。`--expected-revision` が合わない場合や workspace 境界を越える場合は拒否されます。
- `config.write.audit_log` を設定すると、設定書き込みの成功、拒否、関連 revision を JSONL で記録できます。秘密情報の値は記録対象にしません。
- timezone、release、remote、archive の設定は、安全な workspace 解決に依存します。設定変更後は `lifetxt check`、必要に応じて `doctor --check-update` を実行して、実行環境と文書化された前提が一致していることを確認します。

## 定期 Markdown レポートのプロファイル

名前付き定期レポートは、任意のトップレベル `reports` オブジェクトに定義します。
各プロファイルには `period`（`daily`、`weekly`、`monthly` のいずれか）が必須で、
`output`、`title`、`project`、`type`、`tag`、`open`、`mode`、`frontmatter`
を任意で指定できます。具体的なプロファイルキーの登録情報は
`lifetxt config explain reports.<name>.<key>` で確認できます。

完全なプロファイル契約、出力パスのプレースホルダ、生成される frontmatter、
Obsidian/Notion での利用方法は [reports.md](reports.md) を参照してください。
実行可能な設定例として `examples/report_profiles.config.json` も追加しています。

`lifetxt config init` は空の `reports` オブジェクトを意図的に追加しません。
lifetxt には組み込みのレポートプロファイルや出力先がなく、意味のある既定値が存在しないためです。
任意設定の契約は、公開 `config-v1` schema と `config explain` が利用する設定 registry で
定義します。

これは config version 1 に対する追加的な拡張です。`reports` を持たない既存設定は
従来どおり動作し、migration は不要です。downgrade 時は任意の `reports` セクションを
削除すれば、この機能追加前の設定動作に戻ります。

## 名前付き capture preset

`quick`/`q`/`add` の capture 既定値は、任意のトップレベル `capture.presets`
オブジェクトに定義します：

```json
{
  "capture": {
    "presets": {
      "work-task": {
        "type": "T",
        "project": "work",
        "tags": ["work"],
        "priority": "normal"
      },
      "idea": {
        "type": "N",
        "tags": ["idea"]
      }
    }
  }
}
```

```sh
lifetxt quick --preset work-task "Prepare proposal"
lifetxt add --preset idea "Try local-first sync"
```

preset は `type`、`status`、`project`、`tags`、`priority` を設定できます。
これは `quick` がすでに受け付けている `--type`/`--status`/`--project`/
`--tag`/`--priority` と同じ field です。preset はあくまで既定値の layer で
あり、見えない override にはなりません：

```text
既存 config 既定値 < 選択した capture preset < 明示的な shorthand / 明示的な CLI 引数
```

同じ field に対する明示的な `--project`/`--priority`/`--status`/`--type`
flag や capture shorthand の sigil（`@`/`!`/`^`）は、常に preset より優先されます。
`#tag` sigil と `--tag` の値は、preset の `tags` と merge され重複排除されます
（置き換えではありません）。`q` と `add` も同じ `quick` command contract の
alias であるため `--preset` を受け付けます。未知の preset 名は明示的に失敗し、
設定済みの preset 名を一覧表示します。不正な preset 定義（未対応 field、
空の値、非配列または非文字列の `tags` など）は configuration validation で
拒否され、黙って無視されることはありません。

`lifetxt config explain capture.presets`（または個々の field について
`capture.presets.<name>.<field>`）で登録済みのメタデータを確認できます。

`lifetxt config init` は上記の `reports` と同じ理由で、空の
`capture.presets` オブジェクトを意図的に追加しません: 意味のある既定 preset
が存在しないためです。これは config version 1 に対する追加的な拡張です。
`capture` を持たない既存設定は従来どおり動作し、migration は不要です。
downgrade 時は任意の `capture.presets` セクションを削除すれば元に戻ります。
これは既存の `template` command を置き換えるものではありません。`template`
は固定・複数行の record 生成に引き続き使用し、capture preset は
タイトルが可変で metadata が共通する `quick`/`add` capture 向けです。
