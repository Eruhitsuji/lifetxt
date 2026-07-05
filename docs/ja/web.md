# life.txt Web API / GUI

Web interface は任意機能です。FastAPI と uvicorn を使いますが、core parser と
CLI は外部依存なしのままです。

## install

```sh
pip install -r requirements-web.txt
```

## 起動

```sh
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
```

ブラウザで開きます。

```txt
http://127.0.0.1:8000/
```

複数ファイルを同時に読めます。作成、更新、削除は既定では最初のファイルに対して
行います。変更先を明示したい場合は `--write-file` を使います。
path には `projects/**/*.life.txt` のような glob も指定できます。ディレクトリを指定した場合は、
life.txt 風の `.txt` ファイルを読み込みます。

```sh
python -m lifetxt serve life.txt .generated/google_calendar.life.txt --write-file life.txt
python -m lifetxt serve "projects/**/*.life.txt" --write-file life.txt
```

## REST API

| Method | Path | 目的 |
|---|---|---|
| `GET` | `/api/health` | 読み込み path と書き込み先を表示 |
| `GET` | `/api/items` | item 一覧。filter 指定可能 |
| `POST` | `/api/items/parse` | raw life.txt 行または body block を解析し、書き込まずに parsed item を返す |
| `POST` | `/api/items/raw` | 検証済み raw life.txt 行を書き込み先ファイルへ追記 |
| `POST` | `/api/items` | 書き込み先ファイルに item を追記 |
| `PUT` | `/api/items/{line}` | 書き込み先ファイルの指定行 item を置換 |
| `DELETE` | `/api/items/{line}` | 書き込み先ファイルの指定行 item を削除 |
| `GET` | `/api/links` | `parent:` / `ref:` / `depends_on:` / `blocks:` / `related:` の ID link を表示 |
| `GET` | `/api/graph` | Graph UI 用の `nodes` / `edges` を返す。参照先が見つからない node は `missing: true` |
| `GET` | `/api/blockers` | `?id=ID` の推移的 blocker chain を返す(level 1..N、`depth` で深さ制限、既定 5) |
| `GET` | `/api/messages/thread/{id}` | `id:` または `parent:` が一致する Message thread を返す |
| `GET` | `/api/agenda` | 日時範囲に関連する agenda record を表示 |
| `GET` | `/api/status` | 最新 status / presence record を表示 |
| `GET` | `/api/notifications` | Message 通知候補を表示 |
| `GET` | `/api/chart/tasks` | task chart data |
| `GET` | `/api/chart/habits` | habit chart data |
| `GET` | `/api/chart/mood` | journal mood chart data。空 bucket は `null` |
| `GET` | `/api/chart/elapsed` | elapsed time chart data |
| `GET` | `/api/chart/habits-heatmap` | habit heatmap data |

`GET /api/agenda` は CLI `agenda` と同じ record を返します。open item が
open な `depends_on:` または `blocks:` 関係で block されている場合、
record に `blocked: true` と `blocked_by` が含まれます。`?blocked=only` /
`?blocked=hide` で blocked record のみ表示 / 非表示にできます。request 時に展開された
repeat record には、可能な場合 `generated: true`、`source_id`、
`occurrence_start`、`occurrence_end`、`occurrence_index`、`repeat_rule` が
含まれます。API は生成された occurrence を source file へ書き戻しません。

item payload 例:

```json
{
  "status": "[ ]",
  "type": "T",
  "title": "Write Report",
  "details": {
    "due": ["2026-06-12"],
    "project": ["university"]
  }
}
```

item response には、Markdown を含みやすい field 用に sanitized HTML を入れた
`markdown` object が含まれます。

```json
{
  "title": "Research **day**",
  "details": {"body": ["**Done**"]},
  "markdown": {
    "title": "Research <strong>day</strong>",
    "details": {
      "body": ["<p><strong>Done</strong></p>"]
    }
  }
}
```

raw の `title` と `details` は変更されません。`markdown` HTML は safe life.txt
Markdown subset から生成され、raw HTML は escape されます。

例:

```sh
curl "http://127.0.0.1:8000/api/items?kind=T&open_only=true"
curl -X POST "http://127.0.0.1:8000/api/items/parse" \
  -H "Content-Type: application/json" \
  -d '{"line":"[N] J \"Research day\" on:2026-06-23\n| Wrote notes"}'
curl "http://127.0.0.1:8000/api/graph?root=task_001&depth=2"
curl "http://127.0.0.1:8000/api/messages/thread/msg_001"
curl "http://127.0.0.1:8000/api/agenda?around=now&window=1d"
curl "http://127.0.0.1:8000/api/status?active=true"
```

## GUI

ブラウザGUIは以下に対応します。

- item 一覧と filter
- line、time、title、type、status、source による item 並び替え
- URL parameter による filter、順序、件数、表示mode指定
- New Record、Agenda、Status、Notifications、Statistics、Graph を切り替える
  上部 workspace bar
- 現在時刻付近の agenda 表示
- active な status / presence 表示
- Message 通知候補と browser notification
- repeat から生成された agenda occurrence の badge 表示
- drawer 内の Message thread 表示
- drawer からの Message thread 返信
- `parent:` / `ref:` / `depends_on:` / `blocks:` / `related:` の Graph 表示
- sanitized Markdown title / body / note preview の描画
- title、detail、body/note preview の検索語 highlight
- item 作成
- raw life.txt 行を server parser で解析して preview してから editor へ取り込み
- 編集可能な item の選択と保存
- 編集可能な item 行の削除

編集可能なのは書き込み先ファイル由来の item です。
`.generated/google_calendar.life.txt` など生成ファイル由来の item は read-only として
表示します。

layout は responsive です。item list は読みやすい 1 カラムに固定し、従来の右側
tool 群は上部 workspace bar に集約しています。New Record、Statistics、Graph、
Agenda、Status、Notifications は 1 つずつ開くため、狭い画面でも内容が隠れにくく
なります。

## URL parameter

GUI は読み込み時に query parameter を読みます。bookmark、常時表示ディスプレイ、
固定viewの共有に使えます。

例:

```txt
http://127.0.0.1:8000/?kind=T&open_only=true&sort=time&order=asc
http://127.0.0.1:8000/?workspace=agenda&around=now&window=1d
http://127.0.0.1:8000/?mode=display&window=12h&sort=time&order=asc&limit=20&refresh=60
http://127.0.0.1:8000/?mode=display&type=S&person=self&refresh=30
```

対応parameter:

| Parameter | 意味 |
|---|---|
| `mode=display` または `view=display` | 常時表示mode。編集UIを隠し、自動更新を有効化 |
| `mode=kiosk` または `view=kiosk` | 常時表示向け kiosk board。auto-scroll と card grid を使う |
| `view=messages` | Message専用に近いlayout。type `M` をdefault filterにする |
| `view=status` | Status専用に近いlayout。active status表示を強調する |
| `preset=NAME` | config `views.NAME` のURL parameterを適用 |
| `workspace=new|agenda|status|notifications|stats|graph` | item list 上部の workspace panel を開く |
| `refresh=SECONDS` | 自動更新間隔。display mode の既定値は 60 秒 |
| `kind=E` または `type=E` | life.txt type で filter |
| `text=VALUE` または `q=VALUE` | title、元行、detail 値を検索 |
| `open_only=true` または `open=true` | 未完了 workflow item のみ |
| `status=todo` | status または status alias で filter |
| `project=VALUE`、`tag=VALUE`、`tag_all=VALUE`、`exclude_tag=VALUE` | project / tag で filter |
| `user=VALUE`、`team=VALUE`、`person=VALUE` | user / team / presence target で filter |
| `owner=VALUE`、`assignee=VALUE`、`attendee=VALUE` | people detail で filter |
| `sender=VALUE`、`recipient=VALUE` | message detail で filter |
| `sort=line|time|title|type|status|source` | item 並び替え key |
| `order=asc|desc` | item 並び順 |
| `limit=N` | item と agenda の表示件数上限 |
| `around=now`、`window=1d` | agenda 範囲 |
| `from=YYYY-MM-DD`、`to=YYYY-MM-DD` | agenda 範囲 |
| `after=VALUE`、`before=VALUE` | item の時刻filter |
| `notify_refresh=SECONDS` | 通知 polling 間隔 |
| `notify_lookahead=DURATION` | 通知の future lookahead |
| `kiosk_cols=N` | kiosk card の固定列数。最大 8 |
| `kiosk_filter=kind:T,status:[/]` | kiosk mode 専用の compact filter |
| `kiosk_title=TEXT` | kiosk mode 時だけ表示する header title |
| `graph_root=ID`、`graph_depth=N` | Graph panel の初期 root/depth |

## Browser notification

GUI は `/api/notifications` を polling し、due になった type `M` record を
Notifications workspace panel に表示します。上部 toolbar の `Notifications` または
workspace tab から開けます。browser notification はユーザが許可したあとに使えます。

通知許可が blocked の場合、JavaScript から再許可ダイアログを出すことはできません。
その場合は panel に browser の site settings から通知を許可し直す案内を表示します。

## Graph と Message thread

Graph workspace panel は `/api/graph` を読み、外部ライブラリなしの SVG graph として表示します。
node をクリックすると該当 record を drawer で開けます。drawer 内にも選択 item の
小さな依存 graph を表示します。drawer graph は depth 2 の subgraph を読み込むため、
間接的な blocker や related record も drawer 内で確認できます。

Message item (`type:M`) で `id:` がある場合、drawer に thread section を表示します。
drawer には返信 form も表示されます。返信は root message の `id:` を `parent:` に
持つ record として扱います。

## Chart

Chart endpoint は browser 描画用に安定した `labels` と `datasets` 配列を返します。
`GET /api/chart/elapsed` は `from`、`to`、`project`、`group` などの実用的な
filter を受け付けます。

```sh
curl "http://127.0.0.1:8000/api/chart/elapsed?from=2026-06-01&to=2026-06-30&project=research"
```

## Display mode

Display mode は常時表示ディスプレイ向けです。read-only 表示にし、文字を大きくし、
editor と filter controls を隠し、自動更新します。

推奨例:

```txt
/?mode=display&around=now&window=8h&sort=time&order=asc&limit=20
/?mode=display&kind=T&open_only=true&sort=time&order=asc&refresh=120
/?mode=display&type=S&active=true&refresh=30
/?mode=kiosk&kiosk_cols=3&kiosk_filter=kind:T,status:[ ]&kiosk_title=Today&refresh=60
/?view=messages&recipient=self&open_only=true
/?view=status&active=true
/?preset=my_messages
```

Kiosk mode は共有ディスプレイや常時表示ディスプレイ向けです。editor controls を隠し、
item grid を auto-scroll します。`kiosk_cols` で列数を固定し、`kiosk_filter` で
表示専用の短い filter を指定できます。config `views` の named preset からもこれらを
設定できます。auto-refresh で新規または変更された record が入った場合、kiosk mode は
変更された card だけを短時間強調表示します。

config の `sync_ics.generated_paths` または `sync_ics.output` に含まれるファイルは
API response で `generated: true` になり、GUIではread-onlyとして扱われます。

## 追加: Message API

Message type (`M`) 用に以下の API も提供します。

| Method | Path | 目的 |
|---|---|---|
| `GET` | `/api/messages` | type `M` message item を一覧表示 |
| `POST` | `/api/messages` | message-oriented payload から type `M` item を追記 |

例:

```sh
curl "http://127.0.0.1:8000/api/messages?recipient=alice&open_only=true"
```

payload 例:

```json
{
  "title": "Review slides",
  "sender": "self",
  "recipients": ["alice", "bob"],
  "notify_at": "2026-06-06T09:00",
  "channel": "teams"
}
```

GUI と `/api/items`、`/api/agenda` では `sender=VALUE` と `recipient=VALUE` の URL parameter でも絞り込めます。
## Additional API: id, thread, notifications

以下の endpoint を追加しています。

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/config` | Web UI が使う公開設定を返す |
| `GET` | `/api/items/id/{id}` | `id:` で item を取得 |
| `PUT` | `/api/items/id/{id}` | writable file 内の `id:` 一致 item を更新 |
| `DELETE` | `/api/items/id/{id}` | writable file 内の `id:` 一致 item を削除 |
| `GET` | `/api/messages/id/{id}` | `id:` で Message を取得 |
| `PUT` | `/api/messages/id/{id}` | `id:` で Message を更新 |
| `DELETE` | `/api/messages/id/{id}` | `id:` で Message を削除 |
| `POST` | `/api/messages/id/{id}/ack` | writable file 内の Message に `ack:` を設定 |
| `POST` | `/api/messages/id/{id}/snooze` | writable file 内の Message に `snooze_until:` を設定 |
| `GET` | `/api/messages/thread/{id}` | `id:` または `parent:` が一致する Message thread を取得 |
| `POST` | `/api/messages/id/{id}/reply` | `parent:{id}` を持つ返信 Message を作成 |
| `GET` | `/api/notifications` | `notify_at:` または `notify_from/to:` に基づく通知候補を取得 |

config で `ids.auto: true` の場合、`POST /api/items`、`POST /api/messages`、
`POST /api/messages/id/{id}/reply` は payload に `id:` がないとき自動付与します。
採番前に読み込み対象の全ファイルと writable file を走査するため、複数 `life.txt` 構成でも既存IDとの衝突を避けます。
重複IDは item list response の diagnostics で warning `W213` として報告されます。
id-based operation は曖昧なIDを拒否します。

ブラウザでは `Enable Notifications` を押すと Notification API の許可を要求し、許可後に `/api/notifications` を定期 polling して通知します。対象は type `M`、open workflow status、`recipient:` が現在ユーザに一致する item です。
`ack:` がある Message と、未来の `snooze_until:` がある Message は通知対象から外れます。
通知パネルの `Ack` / `Snooze ...` は writable file の対象 Message を更新します。
Snooze duration は `notifications.snooze_default` で指定できます。

## Additional API: links

`GET /api/links` は `parent:`、`ref:`、`depends_on:`、`blocks:`、`related:` の ID 参照を一覧表示します。

```sh
curl "http://127.0.0.1:8000/api/links"
curl "http://127.0.0.1:8000/api/links?id=task_001&direction=incoming"
curl "http://127.0.0.1:8000/api/links?relation=depends_on,blocks"
```

query parameter:

| Parameter | 意味 |
|---|---|
| `id` | 指定 ID に接続する link だけを表示 |
| `direction=incoming|outgoing|both` | `id` 指定時の方向 |
| `limit` | 最大件数 |
