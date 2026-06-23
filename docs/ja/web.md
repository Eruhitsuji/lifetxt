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
| `POST` | `/api/items` | 書き込み先ファイルに item を追記 |
| `PUT` | `/api/items/{line}` | 書き込み先ファイルの指定行 item を置換 |
| `DELETE` | `/api/items/{line}` | 書き込み先ファイルの指定行 item を削除 |
| `GET` | `/api/agenda` | 日時範囲に関連する agenda record を表示 |
| `GET` | `/api/status` | 最新 status / presence record を表示 |

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

例:

```sh
curl "http://127.0.0.1:8000/api/items?kind=T&open_only=true"
curl "http://127.0.0.1:8000/api/agenda?around=now&window=1d"
curl "http://127.0.0.1:8000/api/status?active=true"
```

## GUI

ブラウザGUIは以下に対応します。

- item 一覧と filter
- line、time、title、type、status、source による item 並び替え
- URL parameter による filter、順序、件数、表示mode指定
- 現在時刻付近の agenda 表示
- active な status / presence 表示
- item 作成
- 編集可能な item の選択と保存
- 編集可能な item 行の削除

編集可能なのは書き込み先ファイル由来の item です。
`.generated/google_calendar.life.txt` など生成ファイル由来の item は read-only として
表示します。

layout は responsive です。広い画面では item 一覧と editor を横並びにし、狭い
ブラウザウィンドウでは縦並びに切り替えます。

## URL parameter

GUI は読み込み時に query parameter を読みます。bookmark、常時表示ディスプレイ、
固定viewの共有に使えます。

例:

```txt
http://127.0.0.1:8000/?kind=T&open_only=true&sort=time&order=asc
http://127.0.0.1:8000/?mode=display&window=12h&sort=time&order=asc&limit=20&refresh=60
http://127.0.0.1:8000/?mode=display&type=S&person=self&refresh=30
```

対応parameter:

| Parameter | 意味 |
|---|---|
| `mode=display` または `view=display` | 常時表示mode。編集UIを隠し、自動更新を有効化 |
| `view=messages` | Message専用に近いlayout。type `M` をdefault filterにする |
| `view=status` | Status専用に近いlayout。active status表示を強調する |
| `preset=NAME` | config `views.NAME` のURL parameterを適用 |
| `refresh=SECONDS` | 自動更新間隔。display mode の既定値は 60 秒 |
| `kind=E` または `type=E` | life.txt type で filter |
| `text=VALUE` または `q=VALUE` | title、元行、detail 値を検索 |
| `open_only=true` または `open=true` | 未完了 workflow item のみ |
| `status=todo` | status または status alias で filter |
| `project=VALUE`、`tag=VALUE`、`tag_all=VALUE`、`exclude_tag=VALUE` | project / tag で filter |
| `user=VALUE`、`team=VALUE`、`person=VALUE` | user / team / presence target で filter |
| `owner=VALUE`、`assignee=VALUE`、`attendee=VALUE` | people detail で filter |
| `sort=line|time|title|type|status|source` | item 並び替え key |
| `order=asc|desc` | item 並び順 |
| `limit=N` | item と agenda の表示件数上限 |
| `around=now`、`window=1d` | agenda 範囲 |
| `from=YYYY-MM-DD`、`to=YYYY-MM-DD` | agenda 範囲 |
| `after=VALUE`、`before=VALUE` | item の時刻filter |

## Display mode

Display mode は常時表示ディスプレイ向けです。read-only 表示にし、文字を大きくし、
editor と filter controls を隠し、自動更新します。

推奨例:

```txt
/?mode=display&around=now&window=8h&sort=time&order=asc&limit=20
/?mode=display&kind=T&open_only=true&sort=time&order=asc&refresh=120
/?mode=display&type=S&active=true&refresh=30
/?view=messages&recipient=self&open_only=true
/?view=status&active=true
/?preset=my_messages
```

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
```

query parameter:

| Parameter | 意味 |
|---|---|
| `id` | 指定 ID に接続する link だけを表示 |
| `direction=incoming|outgoing|both` | `id` 指定時の方向 |
| `limit` | 最大件数 |
