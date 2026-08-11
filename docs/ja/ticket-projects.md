# チケット・プロジェクトレポート

`lifetxt.ticket_projects` は、開発チケット（`record: ticket` を持つ `T` レコード）を対象とした共通の読み取り専用集計レイヤーです。Project Hub、Portfolio、メインCLI、MCP、および今後の各画面は同じレポートオブジェクトを再利用するため、チケット件数や注意一覧を表面ごとに別の計算式で算出しません。

レポート契約は `schemas/ticket-project-report-v1.schema.json` として公開され、capability discovery の `ticket_project_report` から確認できます。

チケットのレコードモデル、relation key（`depends_on`／`blocks`／`parent`／
`related`／`duplicate_of`／`replaced_by`）、型付きカスタムフィールド、および
不正なticketやcyclicなticketがこのレポートに到達する前に検出する
`ticket validate`／`check`診断については[tickets.md](./tickets.md)を参照してください。
ticketのrelation keyに適用されるreference／cycle診断（`W215`〜`W229`）は
[cli.md](./cli.md)の`links`セクション（3.2）を参照してください。done／canceledな
ticket（およびその`record:ticket_event`／`record:time_entry`履歴）を
`lifetxt project archive`がこのレポートの入力集合から除外する方法については
[projects.md](./projects.md)のArchivingセクションを参照してください。

## メインCLIコマンド

通常の `lifetxt` コマンドツリーから共通レポートを利用できます。

```console
lifetxt ticket summary life.txt
lifetxt ticket board life.txt
lifetxt ticket attention life.txt
lifetxt project tickets lifetxt life.txt
```

`project tickets` は `--view summary|board|attention` を受け付けます。各コマンドではワークスペース解決済みの入力ファイル、必要に応じた `--project`、`--at`、`--stale-after`、繰り返しまたはカンマ区切りの `--terminal-status`・`--high-severity`、`--format text|json`、`--pretty` を使用できます。

JSON出力は、選択したテキスト表示が `board` または `attention` の場合でも、常に完全な `ticket-project-report-v1` 文書を返します。

```console
lifetxt ticket attention life.txt \
  --project lifetxt \
  --at 2026-07-25T12:00:00+09:00 \
  --stale-after 21

lifetxt project tickets lifetxt life.txt \
  --view board \
  --format json \
  --pretty
```

設定済みのプロジェクト別名は、チケット集計前に正規プロジェクト名へ変換されます。これにより、Project Hub、Portfolio、CLI、MCPのプロジェクト件数が一致します。

## 単独診断コマンド

既存の単独モジュールは、スクリプトおよび診断用途として引き続き利用できます。

```console
python -m lifetxt.ticket_projects summary life.txt
python -m lifetxt.ticket_projects board life.txt
python -m lifetxt.ticket_projects attention life.txt
```

1つのプロジェクトだけに限定できます。

```console
python -m lifetxt.ticket_projects summary life.txt --project lifetxt
```

再現可能な基準時刻と停滞判定日数を指定できます。

```console
python -m lifetxt.ticket_projects attention life.txt \
  --at 2026-07-25T12:00:00+09:00 \
  --stale-after 21
```

完全なバージョン付きレポートをJSONで出力します。

```console
python -m lifetxt.ticket_projects summary life.txt --format json --pretty
```

終端ステータスと高重大度を明示的に置き換える場合は、オプションを繰り返します。

```console
python -m lifetxt.ticket_projects summary life.txt \
  --terminal-status shipped \
  --terminal-status rejected \
  --high-severity sev1 \
  --high-severity sev2
```

## 有効設定

統合された各表面は、1つの有効なレポート設定を解決します。

```json
{
  "ticketing": {
    "statuses": {
      "shipped": {"life_status": "[x]"},
      "wont_fix": {"life_status": "[-]"}
    },
    "high_severities": ["critical", "blocker"],
    "report": {
      "stale_after_days": 14
    }
  }
}
```

- 有効な `life_status` が `[x]` または `[-]` の詳細ステータスを終端として扱います。
- `ticketing.report.high_severities` が存在する場合は `ticketing.high_severities` より優先します。
- `ticketing.report.stale_after_days` は `ticketing.stale_after_days` より優先し、0以上の整数でなければなりません。
- CLIまたはMCPの明示的な上書きは、その呼び出しに限り対応する設定集合を置き換えます。

すべてのレポートに、実際に使用した終端ステータス、高重大度、停滞期間、計算式、注意事項が含まれます。

## Project HubとPortfolio

`project show`／Project Hubの応答には、対象プロジェクトだけの完全な `ticket_report` が追加されます。Portfolioの応答には次が追加されます。

- 最上位の `ticket_report`: 全プロジェクトを対象にした完全なレポート
- 各プロジェクトの `ticket_summary`: 同じレポート内の該当プロジェクト集計。開発チケットがない場合は `null`

汎用のプロジェクト `record:issue` は開発チケットとは分離されたままであり、チケットレポートには含めません。

## MCP

次の読み取り専用MCPツールが、完全な共通レポート契約を返します。

- `get_ticket_project_report`
- `get_ticket_board`
- `get_ticket_attention`

各ツールは任意の `project`、`at`、`stale_after`、`terminal_statuses`、`high_severities` を受け付けます。既存の `get_project` と `get_portfolio` の応答にも、前述の埋め込みレポート項目が含まれます。3つのレポートツールはMCP annotationsで、読み取り専用・非破壊・冪等として公開されます。

クライアントは `get_capabilities` または `lifetxt://capabilities` の `ticket_project_report` を確認することで、スキーマバージョン、CLI操作、MCPツール、有効設定を利用前に検出できます。

## 集計項目

全体およびプロジェクト別に次を集計します。

- 全件数、未完了件数、終端件数
- ステータス、優先度、重大度、トラッカー、担当者、コンポーネント別件数
- ブロック、依存関係不明、期限超過、未割当、高重大度、停滞の注意件数
- 見積時間と経過時間、および値を取得できたチケット数
- 見積と経過時間の両方を解釈できるチケットだけを対象とした差分

注意カテゴリは排他的ではありません。1件のチケットが、ブロック・期限超過・未割当・高重大度・停滞のすべてに同時該当する場合があります。

## チケット行のフィールド

`tickets`・`board`・`attention` の各チケットは、すべて同じ`ticket`形状の行です
（`schemas/ticket-project-report-v1.schema.json` の `$defs.ticket`）。

`id`・`title`・`project`・`status`・`tracker`・`priority`・`severity`・
`assignee`・`reporter`・`component`・`due`・`updated`・`estimate_hours`・
`elapsed_hours`・`depends_on`・`blocks`・`terminal`・`blocked`・
`dependency_unknown`・`unresolved_dependencies`・`unevaluated_dependencies`・
`unevaluated_dependency_reasons`・`overdue`・`unassigned`・`high_severity`・
`stale`・`variance_hours`。

`depends_on` と `blocks` は、そのチケット自身が持つ生のrelation値です
（何に依存しているか、何をブロックしているか）。`unresolved_dependencies` は
別物で、「他の未完了チケットがこのチケットを止めている」ことを表す計算済みの
集合です。これは2つの出所から構築されます。1つはこのチケット自身の未完了な
`depends_on` 対象、もう1つは集計範囲内の他の未完了チケットのうち`blocks:`で
このチケットを名指ししているものです（`blocks:`はblocker側に宣言されるため、
あるチケット自身のblockerを評価するには、そのチケット自身のdetailだけでなく
他のすべてのチケットの`blocks:`をスキャンする必要があります）。`blocked` は
`ticket_status` が `blocked` であるか、`unresolved_dependencies` が空でない
場合に `true` になります。

`unevaluated_dependencies`／`unevaluated_dependency_reasons` は、レポートが
まったく解決できなかったid（選択済み・project絞り込み後の読み取り集合に
存在しないid）を対象とします。各idは次のいずれかの理由にマッピングされます。

- `out_of_scope`: そのidが、絞り込み前の全読み取り集合に直接存在すると分かって
  いる場合（別の、選択されていないprojectのチケット、またはこのチケットを
  名指しするopenな`blocks:`参照の発信元）です。レポートはすでにそれを見て
  いるため、存在はするがフィルタで除外されたと開示しても安全です。
- `missing`: それ以外のすべての場合です。実際に存在しない、private、範囲外に
  archiveされた、workspace解決で拒否された、などです。レポートはこれらを
  意図的に区別しません。区別すると、本来見えないはずのチケットが存在するか
  どうかを開示してしまうためです。

実例: `ticket attention` を1つのprojectに絞り込むと、project間の
`depends_on` は `blocked` ではなく `out_of_scope` になります。これは、
対象チケットが（open dependencyの解決に使う）`by_id` からは除外される
一方で、この開示判定にのみ使う絞り込み前の `all_ticket_ids` には残っている
ためです。

```console
$ lifetxt ticket attention life.txt --project mobile --format json --pretty
```

```json
{
  "id": "BUG-102",
  "project": "mobile",
  "depends_on": ["BUG-100"],
  "blocked": false,
  "dependency_unknown": true,
  "unresolved_dependencies": [],
  "unevaluated_dependency_reasons": {"BUG-100": "out_of_scope"},
  "unevaluated_dependencies": ["BUG-100"]
}
```

（`BUG-100` はproject `web` に実在するチケットです。`--project` を指定しない
場合、同じ行は代わりに `blocked: true` を報告し、`unresolved_dependencies` に
`BUG-100` が含まれます。そのときは解決可能だからです。）

## 計算式と欠損値の扱い

- **未完了**: 正規化した `ticket_status` が有効な終端ステータスに含まれないチケットです。
- **進捗率**: 終端チケット数÷全チケット数です。件数ベースであり、納期予測ではありません。
- **ブロック**: 未完了チケットの `ticket_status` が `blocked`、集計範囲内の未完了チケットに依存している、または集計範囲内の他の未完了チケットの`blocks:`参照で名指しされている状態です。
- **依存関係不明**: `depends_on` のID、またはこのチケットを名指しするopenな`blocks:`参照が集計範囲内に存在しない状態です。`out_of_scope`／`missing`の理由の区別は上の「チケット行のフィールド」を参照してください。それ以外は、欠けているチケットが未完了か終端かを推測しません。
- **期限超過**: 未完了チケットの期限時刻が基準時刻以前の状態です。日付だけの期限は、そのUTC暦日の終了まで有効です。オフセット付き日時は明示されたオフセットを使います。
- **停滞**: `updated`、`modified`、`changed`、`created`、`opened` のうち取得できる最新時刻が設定日数より古い状態です。時刻がないチケットを停滞とは判定しません。
- 数値だけの期間は時間として扱います。短縮表記は `w`、`d`、`h`、`m` に対応し、1日=8時間、1週=40時間です。無効値や一部しか解釈できない値は推測せず集計から除外します。

## ボードと注意一覧の順序

ボード列は固定の標準ステータス順、その後に未知のカスタムステータスを辞書順で並べます。チケットは優先度、期限、チケットID、タイトルの順で安定して並びます。プロジェクト一覧と注意一覧も決定的です。

## ライブラリからの利用

公開CLIおよびMCPと同じ結果が必要な場合は、設定解決を含む表面非依存アダプターを使用します。

```python
from lifetxt.ticket_project_surfaces import build_configured_ticket_project_report

report = build_configured_ticket_project_report(
    items,
    config=config,
    project="lifetxt",
)
```

呼び出し側がすべての設定を明示する場合は、低レベルのビルダーも引き続き利用できます。

```python
from lifetxt.ticket_projects import build_ticket_project_report

report = build_ticket_project_report(
    items,
    project="lifetxt",
    stale_after_days=14,
)
```

入力にはlifetxtのItemオブジェクトまたは辞書形式のレコードを使用できます。チケット判定には項目種別 `T` と `record: ticket` の両方が必要なため、通常のTaskやカウンターマシン用Noteは集計対象になりません。
