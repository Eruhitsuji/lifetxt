# チケット・プロジェクトレポート

`lifetxt.ticket_projects` は、開発チケット（`record: ticket` を持つ `T` レコード）を対象とした共通の読み取り専用集計レイヤーです。Project Hub、Portfolio、CLI、MCP、Web、TUI、コマンドセンターが別々の計算式を実装しないよう、同じレポート契約を再利用できます。

レポート契約は `schemas/ticket-project-report-v1.schema.json` として公開します。

## コマンド

1個以上の life.txt ファイルを直接集計します。

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

終端ステータスと高重大度の既定値を置き換える場合は、オプションを繰り返します。

```console
python -m lifetxt.ticket_projects summary life.txt \
  --terminal-status shipped \
  --terminal-status rejected \
  --high-severity sev1 \
  --high-severity sev2
```

## 集計項目

全体およびプロジェクト別に次を集計します。

- 全件数、未完了件数、終端件数
- ステータス、優先度、重大度、トラッカー、担当者、コンポーネント別件数
- ブロック、依存関係不明、期限超過、未割当、高重大度、停滞の注意件数
- 見積時間と経過時間、および値を取得できたチケット数
- 見積と経過時間の両方を解釈できるチケットだけを対象とした差分

注意カテゴリは排他的ではありません。1件のチケットが、ブロック・期限超過・未割当・高重大度・停滞のすべてに同時該当する場合があります。

## 計算式と欠損値の扱い

- **未完了**: 正規化した `ticket_status` が設定済み終端ステータスに含まれないチケットです。
- **進捗率**: 終端チケット数÷全チケット数です。件数ベースであり、納期予測ではありません。
- **ブロック**: 未完了チケットの `ticket_status` が `blocked`、または集計範囲内の未完了チケットに依存している状態です。
- **依存関係不明**: `depends_on` のIDが集計範囲内に存在しない状態です。欠けているチケットが未完了か終端かは推測しません。
- **期限超過**: 未完了チケットの期限時刻が基準時刻以前の状態です。日付だけの期限は、そのUTC暦日の終了まで有効です。オフセット付き日時は明示されたオフセットを使います。
- **停滞**: `updated`、`modified`、`changed`、`created`、`opened` のうち取得できる最新時刻が設定日数より古い状態です。時刻がないチケットを停滞とは判定しません。
- 数値だけの期間は時間として扱います。短縮表記は `w`、`d`、`h`、`m` に対応し、1日=8時間、1週=40時間です。無効値や一部しか解釈できない値は推測せず集計から除外します。

JSON出力には、計算式、注意事項、実際に使用した終端ステータス、高重大度が含まれます。

## ボードと注意一覧の順序

ボード列は固定の標準ステータス順、その後に未知のカスタムステータスを辞書順で並べます。チケットは優先度、期限、チケットID、タイトルの順で安定して並びます。プロジェクト一覧と注意一覧も決定的です。

## ライブラリからの利用

```python
from lifetxt.ticket_projects import build_ticket_project_report

report = build_ticket_project_report(
    items,
    project="lifetxt",
    stale_after_days=14,
)
```

入力にはlifetxtのItemオブジェクトまたは辞書形式のレコードを使用できます。チケット判定には項目種別 `T` と `record: ticket` の両方が必要なため、通常のTaskやカウンターマシン用Noteは集計対象になりません。
