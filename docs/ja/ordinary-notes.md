# 通常のメモ

`N` は保存形式上の種類です。すべての `N` が日常的に読むメモとは限りません。
通常のメモ（ordinary Note）は、解析済みの `N` から共通の判定で取得する
読み取り用の一覧です。移行や `ordinary:true` / `planner:true` は不要です。

既存の専用判定を利用し、`person:` が指定されたPersonal Context
（`is_personal_context_item(person=None)`）、Native Historyの
`record:item_event`、チケット監査記録の `record:ticket_event`、
作業時間記録の `record:time_entry`、進捗監査記録の `record:progress_event`
を除外します。未知の `record:` や「History」等のタイトルでは除外しません。
`assignee:` だけでPersonal Contextと判定することもありません。

## 一覧・検索の使い方

| 利用箇所 | 通常のメモ | raw N（すべてのN） |
| --- | --- | --- |
| CLI | `lifetxt notes life.txt --limit 5 --offset 0 --date 2031-02-03` | `lifetxt to-json life.txt --type N`、既存query/show |
| CLI JSON/JSONL | `lifetxt notes life.txt --format json` / `--format jsonl` | 既存の変換コマンド |
| エクスポート・Markdown・fzf/peco | 既存の項目フィルターに `--ordinary-notes` を追加 | 既存の `--type N` |
| Web API | `GET /api/notes?date=2031-02-03&limit=5&offset=0` | `GET /api/items?type=N` |
| 既存Web UI | 種類で「通常のメモ」を選択。検索・並べ替え・詳細表示も利用可能 | 「すべてのメモ（N）」を選択 |
| Planner | メモ欄で初期5件、「さらに表示」で5件追加 | Web UI全体 → すべてのメモ（N） |
| ローカル／Remote TUI | `/view notes`。既存検索・詳細欄、`/limit 20` で表示上限を拡張 | `/view raw-notes` |
| Remote Safe Mode | `GET /api/remote/v1/resources/notes` / `lifetxt remote get PROFILE notes --param limit=5` | 既存の `items` リソース |
| MCP | `list_notes` にdate/text/offset/limit/sort/orderを指定 | `list_items` のtype N、既存get/search |

CLIは `--text 検索語`、APIとMCPは `text` で検索できます。
分類と検索を終えてからページを切り出します。
汎用の `/api/items?ordinary_notes=true` とMCP `list_items` の
`ordinary_notes: true` でも同じ共通判定を利用し、既存のフィルター・並び順を
維持します。rawのクエリ文法や項目の直接参照も変わりません。

Remote TUIはサーバ側のprojectionからページ単位で取得します。
`/api/notes` 対応サーバが必要です。未対応・オフライン・取得中の変更時は
エラーを表示して再読み込みを求め、rawのキャッシュをクライアント側で
独自分類しません。通常のメモに含まれる集合は全surfaceで一致します。

## 並び順とページ

標準の `relevance` は、既存Agendaの日付判定で選択 `date` に関連するメモを
優先します。有効な日時区間や繰り返しも同じ判定を利用します。
続いて `updated:` の新しい順、`created:` の新しい順です。
日時がない／無効な場合はID・タイトル・内容・出典・行番号で安定的に
並べます。日時・時差の比較は既存の方針に従います。
日付未指定なら更新・作成日時と安定順のみを使い、独自スコアは計算しません。
`sort=title|line|updated|created` と `order=asc|desc` も指定できます。
relevanceの日時は常に新しい順です。既存Web UIや汎用項目クエリは選択中の
項目ソートを維持します。

CLI notes・`/api/notes`・MCP `list_notes` は初期5件、`limit` は1～100、
`offset` は0以上です。JSON/API出力には `items`、`count`、`total`
（検索条件に合う通常のメモの総数）、`offset`、`limit`、`has_more`、
`next_offset`、`date`、`sort`、`order`、`revision` を含みます。
JSONLは既存の項目単位変換形式です。テキスト出力は件数・総数・次のoffsetを
表示します。通常のメモの内容が変わるとprojectionの指紋 `revision` も
変わるため、ページ間で変化した場合はoffset 0から取得し直してください。

Plannerは表示件数／総数を示し、5件ずつ追加します。
読み取り専用でも「さらに表示」を使え、最後のページではボタンを隠します。
作成・編集は従来の標準 `N` を使います。作成・編集・日付変更やprojectionの
変更時は最初のページへ戻り、異なる状態のページ混在を防ぎます。
EN/JAと320・360・390・430 CSS pxをヘッドレスブラウザで検証します。
実機での確認は別途必要です。

Remote Safe Modeは閲覧権限で絞った後に分類・集計し、既存のパス秘匿を維持します。

`/remote` のブラウザにも「通常のメモ」「次のメモページ」（1ページ20件）を追加しています。rawデータは「snapshotを更新」で表示できます。
