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
python -m lifetxt serve "projects/**/*.life.txt" --write-file life.txt --read-only
```

公開用 dashboard や常時表示 display など、閲覧と行 validation は許可しつつ
source file を変更させたくない場合は `--read-only` を使います。

## MCP Server

MCP-compatible AI client から使う場合は、外部依存なしの stdio MCP server を起動できます。

```sh
python -m lifetxt mcp life.txt
python -m lifetxt mcp life.txt .generated/google_calendar.life.txt --write-file life.txt
python -m lifetxt serve life.txt --mcp
```

MCP tool は `list_items`、`get_item`、`create_item`、`update_item`、
`mark_done`、`delete_item`、`get_agenda`、`get_graph`、`get_blockers`、
`list_links`、`list_status`、`list_notifications`、type `M` message 操作を提供します。
読み込んだ source file は `lifetxt://source/N` resource としても参照できます。
複数 file を読み込む場合、read tool は全 file を走査し、write tool は `--write-file` のみを変更します。
`--read-only` を付けると write tool は無効になります。

## REST API

| Method | Path | 目的 |
|---|---|---|
| `GET` | `/api/health` | 読み込み path と書き込み先を表示 |
| `GET` | `/api/config` | Web UI が使う公開 runtime config を表示 |
| `GET` | `/api/items` | item 一覧。filter 指定可能 |
| `POST` | `/api/items/parse` | raw life.txt 行または body block を解析し、書き込まずに parsed item を返す |
| `POST` | `/api/items/raw` | 検証済み raw life.txt 行を書き込み先ファイルへ追記 |
| `GET` | `/api/items/id/{id}` | exact `id:` で item を取得 |
| `PUT` | `/api/items/id/{id}` | writable file 内の exact `id:` 一致 item を更新 |
| `DELETE` | `/api/items/id/{id}` | writable file 内の exact `id:` 一致 item を削除 |
| `GET` | `/api/links` | `parent:` / `ref:` / `depends_on:` / `blocks:` / `related:` / `duplicate_of:` / `replaced_by:` の ID link を表示 |
| `GET` | `/api/graph` | Graph UI 用の `nodes` / `edges` を返す。参照先が見つからない node は `missing: true` |
| `GET` | `/api/blockers` | `?id=ID` の推移的 blocker chain を返す(level 1..N、`depth` で深さ制限、既定 5) |
| `GET` | `/api/messages` | type `M` message item を一覧表示。message filter 指定可能 |
| `GET` | `/api/messages/id/{id}` | exact `id:` で Message を取得 |
| `PUT` | `/api/messages/id/{id}` | writable file 内の exact `id:` 一致 Message を更新 |
| `DELETE` | `/api/messages/id/{id}` | writable file 内の exact `id:` 一致 Message を削除 |
| `POST` | `/api/messages/id/{id}/ack` | writable file 内の Message に `ack:` を設定 |
| `POST` | `/api/messages/id/{id}/snooze` | writable file 内の Message に `snooze_until:` を設定 |
| `GET` | `/api/messages/thread/{id}` | `id:` または `parent:` が一致する Message thread を取得 |
| `POST` | `/api/messages/id/{id}/reply` | `parent:{id}` を持つ返信 Message を作成 |
| `POST` | `/api/messages` | message-oriented payload から type `M` item を追記 |
| `POST` | `/api/items` | 書き込み先ファイルに item を追記 |
| `PUT` | `/api/items/{line}` | 書き込み先ファイルの指定行 item を置換 |
| `DELETE` | `/api/items/{line}` | 書き込み先ファイルの指定行 item を削除 |
| `GET` | `/api/agenda` | 日時範囲に関連する agenda record を表示 |
| `GET` | `/api/review` | 日付範囲の review report(完了 task、habit 達成率、journal、mood 推移、elapsed 集計) |
| `GET` | `/api/commands` | TUI と共有する slash command の catalog |
| `GET` | `/api/timer` | 実行中の timer |
| `POST` | `/api/timer` | timer 操作。body: `{"action": "start", "id": "t1"}`、`stop`、`cancel` |
| `GET` | `/api/status` | 最新 status / presence record を表示 |
| `POST` | `/api/status` | 直前の open な status を閉じて presence を記録。body: `{"state": "busy"}`、`{"end": true}`、同じ状態を繰り返す場合は `"force": true` |
| `POST` | `/api/items/capture` | plain text から task を追記。`@project #tag !priority ^due` を展開 |
| `POST` | `/api/shorthand/parse` | 書き込まずに省略記法の展開を確認 |
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
curl -X POST http://127.0.0.1:8000/api/status \
  -H "Content-Type: application/json" -d '{"state": "busy"}'
curl -X POST http://127.0.0.1:8000/api/items/capture \
  -H "Content-Type: application/json" -d '{"text": "Buy milk @home ^tomorrow"}'
curl "http://127.0.0.1:8000/api/review?week=true"
curl "http://127.0.0.1:8000/api/review?month=2026-07&project=research"
curl "http://127.0.0.1:8000/api/review?from=2026-06-29&to=2026-07-05"
```

`GET /api/review` は CLI `review` コマンド・MCP `get_review` tool と同じ
report を返します: `completed_tasks` / `open_tasks` の件数、`completed`
一覧(title、done 日付、project、id)、habit ごとの達成率、抜粋付き journal
一覧、`mood_trend`、`elapsed_by_project` 集計。範囲指定は CLI と同じ優先順で
`week=true`、`month=YYYY-MM`、`from`/`to`(default は今週の開始日と今日)を
解釈し、不正な値には `400` を返します。

## GUI

ブラウザGUIは以下に対応します。

- item 一覧と filter
- line、time、title、type、status、source による item 並び替え
- URL parameter による filter、順序、件数、view 指定
- 1画面1コンテンツの view bar: Dashboard、Items、Agenda、Timeline、Calendar、Focus、
  Review、Messages、Team、Status、Notifications、Stats、Graph、Display、Kiosk —
  常に 1 つの view だけを全画面表示
- Dashboard view: クリック可能な KPI tile(open / due today / overdue /
  blocked / 直近完了数)、今日の agenda、要対応一覧、14日間の完了 chart、
  project 別進捗。`web.dashboard.cards` と `web.dashboard.limits` で
  card の表示/非表示、順序、件数上限を設定可能
- Focus view: overdue・今日期限・進行中の作業 item をワンクリック done
  (undo 付き)で処理。今日の timed event、`at:`/`on:` が今日の reminder、
  日付なしの「anytime」reminder も表示し、quick-add 入力から `due:` 今日の
  task を view を離れずに追加可能
- Review view: `GET /api/review` を使い、今週 / 先週 / 今月 / 先月 preset、
  project filter、custom from/to date、`id:` がある完了 task のクリック詳細表示、
  Markdown copy に対応。CLI の weekly-review workflow をブラウザで扱える
- Timeline view: agenda record を時系列に並べたボード。赤い「now」ライン、
  type 別の色付きレールノード、時刻ラベル、all-day 行、日付ヘッダー、過去
  record の減光、URL に保存される Today / Next 24h / Week の範囲プリセット、
  選択範囲に dated record がない場合の guided empty state、選択範囲より前に
  開始して現在も重なっている record の `ongoing` badge に対応し、card
  クリックで record detail modal を開く
- Calendar view: 月または単一週のグリッドに agenda record(繰り返し
  occurrence の展開を含む)を該当日へ配置。各セルは先頭数件を表示し
  `+N more` で残りを展開、type と overdue/due-soon で色分け、today を強調、
  日別件数を表示。entry クリックで record detail modal、日付番号クリックで
  その日を Agenda で開く。Prev/Next/Today と Month/Week 切り替えはキー操作
  (`,` `.` で前後の期間、`t` で today、`m` でモード切替)に対応し、
  `?view=calendar&calmode=month|week&cal=YYYY-MM-DD` として URL に保存される。
  週の先頭曜日は `web.week_start`(既定 `monday`、`sunday` も可)に従う
- Team view: 在席ボード。人ごとの最新 status record(色付き presence dot と
  state badge)、その人宛ての open message、assignee としての open/overdue
  件数を 1 枚の card に集約 — `?view=team&refresh=60` と fullscreen の
  組み合わせで壁掛けディスプレイに向く
- Status / Team view の色付き在席インジケーター: state 値を dot と badge の
  色に対応付け(available/free/online → 緑、busy/meeting → 赤、focus/dnd →
  紫、away/lunch → 黄、out/offline や終了済み → グレー枠、その他 → 青)。
  state のテキストも常に表示するため、色だけに依存しない
- fullscreen 切り替え(header の ⛶ ボタン、`f` キー、command palette):
  ブラウザの Fullscreen API を使用し、kiosk / display mode と組み合わせて
  常時表示画面に使える
- Display workspace tab と command palette action。常時表示向けに編集UIを隠し、
  Exit Display ボタンだけを残す。light theme では明るい常時表示palette、dark theme
  では暗色paletteを使い、ブラウザの戻る/進むによる URL 状態にも追従する
- blocked filter 付きの agenda 表示
- active な status / presence 表示
- Message 通知候補と browser notification
- repeat から生成された agenda occurrence の badge 表示
- record detail modal 内の Message thread 表示
- record detail modal からの Message thread 返信
- Help / Git / Undo history / record detail / record editor の keyboard-trapped modal
- fuzzy command palette(action、view 切替、最近開いた record)
- `parent:` / `ref:` / `depends_on:` / `blocks:` / `related:` / `duplicate_of:` / `replaced_by:` の Graph 表示
- sanitized Markdown title / body / note preview の描画
- title、detail、body/note preview の検索語 highlight
- 中央の record editor modal での item 作成(`＋ New` または `n`)。New ボタンと
  editor の Status / Type / Title / Details には viewport 内に収まる hover/focus help を表示
- raw life.txt 行を server parser で解析して preview してから editor へ取り込み
- 編集可能な item の選択と保存
- 編集可能な item 行の削除
- browser session 内の直近5件の undo history。command palette の
  `Show undo history` から表示

編集可能なのは書き込み先ファイル由来の item です。
`.generated/google_calendar.life.txt` など生成ファイル由来の item は read-only として
表示します。

layout は「1画面1コンテンツ」を基本とします。header の view bar で選んだ
1 つの page(Items、Dashboard、Agenda、Timeline、Focus、Review、Messages、
Team、Status、Notifications、Stats、Graph、Display、Kiosk)だけが全幅で表示され、他の
コンテンツと画面を奪い合いません。record editor は `＋ New` から中央 modal として開き、item を
クリックした詳細表示も中央の record detail modal として表示します。

## Web UI configuration

`/api/config` は browser に公開してよい `web.*` 設定だけを返します。GUI は
起動時に以下のような値を読み取り、見た目と Dashboard を調整します。

```json
{
  "web": {
    "theme": {
      "accent": "#0e7a65",
      "accent_hover": "#0a6252",
      "accent_soft": "#e0f0ea",
      "accent_ink": "#ffffff"
    },
    "dashboard": {
      "cards": ["today", "needs_attention", "completions", "projects"],
      "limits": {"today": 7, "needs_attention": 7, "projects": 7}
    }
  }
}
```

theme token 名は CSS 変数名から先頭の `--` を除いたものです。例:
`bg`、`panel`、`panel_2`、`soft`、`ink`、`muted`、`line`、
`line_strong`、`accent`、`accent_hover`、`accent_soft`、`accent_ink`、
`danger`、`warn`、`ok`、`info`、`violet`、`shadow_1`、`shadow_2`、
`shadow_3`、`r_sm`、`r_md`、`r_lg` と各 semantic `*_soft` token。
flat な config generator 向けに `"theme.accent"` や `"dashboard.cards"` の
ような dotted key も利用できます。

## 補完

テキスト入力欄では、ファイル内で既に使っている値が補完されます。
`project:research` の隣に `project:reserach` を作ってしまう事故を防げます。
候補は shell completion script・TUI・MCP の `complete` tool と同じ層から
取得するため、すべての面で一致します。

quick-add bar はトークンごとに補完します:

| 入力 | 補完対象 |
|---|---|
| `@` | project |
| `#` | tag |
| `!` | priority |
| `^` | 日付語（`tomorrow`、`next_friday`、`+3d`） |
| `KEY:` | その key の値。例えば `assignee:` は人名 |
| title の後の裸の語 | detail の key 名 |

presence bar では presence state を、レコード編集の Details 欄でも補完します。

キー操作: `↑`/`↓` で移動、`Tab` または `Enter` で確定、`Esc` で閉じる、
`Ctrl+Space` で入力を増やさずに候補を要求。スマートフォンではタップで確定できます。
`Enter` は bar の送信ではなく候補の確定に使われるため、入力途中の語が
誤って登録されることはありません。

### `GET /api/complete`

上記の裏側にある endpoint です。単体でも利用できます:

```bash
curl 'http://127.0.0.1:8000/api/complete?kind=project&prefix=re&limit=10'
```

```json
{"kind": "project", "prefix": "re", "candidates": ["research"]}
```

| parameter | 意味 |
|---|---|
| `kind` | `state`、`project`、`tag`、`person`、`id`、`type`、`status`、`context`、`priority`、`key`、`team`、`service`、`channel` |
| `prefix` | 任意の絞り込み。前方一致が部分一致より上位 |
| `limit` | 最大件数。200 に制限（既定 20） |

`person` は `person:`・`owner:`・`assignee:`・`attendee:`・`sender:`・
`recipient:`・`user:` をまとめて対象にします。`state` と `priority` は
文書化された値を先に並べ、その後にファイル固有の値を続けます。未知の `kind` は
対応一覧を添えて 400 を返します。

## 表示言語

GUI は英語を原文とし、翻訳はブラウザ側で行います。セッションごとに切り替える
場合は `?lang=ja`、workspace の既定にする場合は `.lifetxt.json` の
`web.language` を設定します。

```json
{"web": {"language": "ja"}}
```

`?lang=` は config の値より優先されるため、共有 config でも `?lang=en` で
英語表示に戻せます。未対応の値を指定した場合は英語になります。

翻訳対象は次の 2 つの規則で決まります。

- **UI の chrome は翻訳されます。** button、tab、view の説明文、keyboard help
  の行、select の選択肢に加えて、その `title` / `placeholder` / `aria-label`
  attribute も対象です。`View all 63 (55 more)`、`Open 2026-07-20 in Agenda`、
  `3d overdue` のように値を含む label は pattern で照合するため、数値や日付は
  そのまま保持されます。
- **レコードは翻訳されません。** title、details、project、tag、人名は
  `life.txt` の内容そのものなので、そのまま表示されます。`Done` という名前の
  タスクは `Done` のままで、status 語の訳語に書き換えられることはありません。

view は非同期に描画されるため、新しく描画された内容も監視して随時翻訳します。
view の切り替え、更新、カレンダーの前後移動を行っても英語が残りません。

## URL parameter

GUI は読み込み時に query parameter を読みます。bookmark、常時表示ディスプレイ、
固定viewの共有に使えます。

例:

```txt
http://127.0.0.1:8000/?kind=T&open_only=true&sort=time&order=asc
http://127.0.0.1:8000/?view=dashboard&refresh=60
http://127.0.0.1:8000/?view=agenda&around=now&window=1d
http://127.0.0.1:8000/?view=timeline&range=week&refresh=120
http://127.0.0.1:8000/?view=focus&theme=dark
http://127.0.0.1:8000/?mode=display&window=12h&sort=time&order=asc&limit=20&refresh=60
http://127.0.0.1:8000/?mode=display&type=S&person=self&refresh=30
```

対応parameter:

| Parameter | 意味 |
|---|---|
| `view=dashboard\|agenda\|timeline\|focus\|review\|messages\|team\|status\|notifications\|stats\|graph` | 全画面 view を開く。`view=messages` は type `M` を default filter にする |
| `mode=display` または `view=display` | 常時表示mode。編集UIを隠し、自動更新を有効化 |
| `mode=kiosk` または `view=kiosk` | 常時表示向け kiosk board。auto-scroll と card grid を使う |
| `preset=NAME` | config `views.NAME` のURL parameterを適用 |
| `workspace=agenda\|status\|notifications\|stats\|graph` | `view=...` の旧alias。`workspace=new` は record editor modal を開く |
| `refresh=SECONDS` | 自動更新間隔。display mode の既定値は 60 秒 |
| `kind=E` または `type=E` | life.txt type で filter |
| `text=VALUE` または `q=VALUE` | title、元行、detail 値を検索 |
| `fuzzy=true` | `text`/`q` を完全な部分一致だけでなく、小さな typo・編集距離の範囲でも一致させる。opt-in、Unicode 正規化済み |
| `open_only=true` または `open=true` | 未完了 workflow item のみ |
| `status=todo` | status または status alias で filter |
| `project=VALUE`、`tag=VALUE`、`tag_all=VALUE`、`exclude_tag=VALUE` | project / tag で filter |
| `user=VALUE`、`team=VALUE`、`person=VALUE` | user / team / presence target で filter |
| `owner=VALUE`、`assignee=VALUE`、`attendee=VALUE` | people detail で filter |
| `sender=VALUE`、`recipient=VALUE` | message detail で filter |
| `sort=line\|time\|title\|type\|status\|source` | item 並び替え key |
| `order=asc\|desc` | item 並び順 |
| `limit=N` | item と agenda の表示件数上限 |
| `around=now`、`window=1d` | agenda 範囲 |
| `from=YYYY-MM-DD`、`to=YYYY-MM-DD` | agenda 範囲 |
| `range=today\|24h\|week` | `view=timeline` 時の Timeline 範囲。UI の範囲ボタンを押すとこの値も更新 |
| `calmode=month\|week` | `view=calendar` 時の Calendar グリッドモード。Month/Week ボタンで更新 |
| `cal=YYYY-MM-DD` | 表示中の Calendar 期間の基準日。Prev/Next/Today 操作で更新 |
| `after=VALUE`、`before=VALUE` | item の時刻filter |
| `notify_refresh=SECONDS` | 通知 polling 間隔 |
| `notify_lookahead=DURATION` | 通知の future lookahead |
| `kiosk_cols=N` | kiosk card の固定列数。最大 8 |
| `kiosk_filter=kind:T,status:[/]` | kiosk mode 専用の compact filter |
| `kiosk_title=TEXT` | kiosk mode 時だけ表示する header title |
| `theme=dark` または `theme=light` | theme を強制。`localStorage` を設定できない kiosk / 常時表示ディスプレイ向け |
| `lang=ja` または `lang=en` | 表示言語。config の `web.language` より優先。レコードは翻訳されません |
| `graph_root=ID`、`graph_depth=N` | Graph panel の初期 root/depth |

## Command Palette

`Ctrl+K` で Command Palette を開けます。fuzzy matching、recently opened records、
view 切り替え(`Go to Dashboard` など)、quick-add、export、theme toggle、
kiosk mode、agenda blocked filter の切り替えに対応しています。

### スマートフォンでの利用

ブラウザ UI はデスクトップだけでなくタッチ操作にも対応しています。

**record の選択。** タッチデバイスでは checkbox が常に表示されます。
デスクトップでは hover 時に表示されますが、指では hover できないため、
この対応がないと何も選択できず、一括操作も slash command も対象を持てません。
checkbox をタップすると選択され、一括操作の toolbar が画面下部の
親指が届く位置に固定表示されます。

**⌘ ボタン。** スマートフォンには `Ctrl+K`、`n`、`q`、`x` が存在しないため、
右下のフローティングボタンから同じ入口をまとめて開けます。
command、クイック追加、新規 record、status 設定、再読み込みが並び、
「Commands」は palette を `/` 入力済みの状態で開きます。

**レイアウト。** 要素が多い行（toolbar、view tab、filter）は
全幅ボタンが縦に積み上がる代わりに横スクロールします。
ページ自体が横に動くことはありません。
dialog と record 詳細は中央の箱ではなくボトムシートとして開きます。

**細部。** 小さい画面では入力欄を 16px にしています。
iOS Safari はこれより小さい入力欄に focus すると拡大し、元に戻さないためです。
タッチ対象は最低 44px を確保しています。
固定要素は `env(safe-area-inset-*)` でノッチとホームインジケータを避け、
全画面高の要素は `dvh` を使うため、URL バーの伸縮で内容が隠れません。

デスクトップの表示は変わりません。
フローティングボタンは非表示、一括操作 toolbar は通常配置、dialog は中央のままです。

### slash command

`Ctrl+K` を押して `/` を入力すると、TUI と同じ command を実行できます。
catalog は `/api/commands` から取得され、TUI の command registry を元に生成されるため、
command 名・別名・意味は両者で完全に一致します。

```
/done                 選択した record を完了
/status active        選択に status を設定
/set owner dana       選択に任意の detail を設定
/due +3d              共有の日付トークンで due: を設定
/assign carol         assignee: を設定
/add Buy milk @home   記号記法付きでキャプチャ
/state focus          直前の status を閉じて presence を記録
/timer start          選択 record で共有 timer を開始
/project work         project で filter
/export csv           現在の表示を書き出し
```

command は**チェックボックスの選択**に対して実行され、
何も選択していない場合は現在選択中の record が対象になります。
`/mark all` と `/mark none` で選択を操作でき、`x` で 1 行ずつ切り替えられます。

端末でしか意味を持たない command (`/edit`、`/quit`、`/limit`、`/window`、`/undo`) も
「Terminal only」として一覧に残り、ブラウザでの代替手段を短く説明します。
隠してしまうより分かりやすいためです。

Enter を押したときは引数が保持されるため、
palette が別の行を強調していても `/due tomorrow` は引数付きで実行されます。
日付トークンはサーバ側で解決されるため、`tomorrow`、`monday`、`+3d` は
ブラウザ・TUI・CLI で同じ意味になります。

### クイック追加の省略記法と presence

クイック追加の入力欄は、`[` で始まる完全な life.txt 行と、
キャプチャ記号を含む plain text の両方を受け付けます。

```
Buy milk @home #errand !high ^tomorrow
```

`@` は `project:`、`#` は `tag:`、`!` は `priority:`、`^` は共有の相対日付トークン
(`today`、`tomorrow`、曜日名、`+3d`) を使って `due:` を設定します。
入力欄の下に実際に書き込まれる内容がリアルタイムで表示されます。
展開はサーバ側で行われるため `lifetxt quick` と挙動がずれることはありません。

`p` で presence バーを開きます。状態 (`busy`、タイトルを付けるなら `focus Deep work`)
を入力して Enter で記録され、直前の open な status は同じ request 内で閉じられます。
`End` は新しい status を開かずに現在の status を閉じます。
すでに開いている状態と同じ状態を指定した場合は何も書き込まず、その旨を表示します。
どちらも command palette の `Set status` / `End status` からも実行できます。


browser 側の「Save View」機能はありません。共有したい view はそのまま URL として
共有でき(filter、sort、view 選択はすべて query string に反映されます)、再利用する
preset は config `views.NAME` に定義して `?preset=NAME` で適用します。

## Browser notification

GUI は `/api/notifications` を polling し、due になった type `M` record を
Notifications view に表示します。上部 toolbar の `Notifications` または view tab
から開けます。browser notification はユーザが許可したあとに使えます。

通知許可が blocked の場合、JavaScript から再許可ダイアログを出すことはできません。
その場合は panel に browser の site settings から通知を許可し直す案内を表示します。

email 配信は browser ではなく CLI watcher が担当します:
`python -m lifetxt notify life.txt --watch --email --email-to me@example.com`。
SMTP host/user/password は `notifications.email.*` が指す環境変数から読みます。

## Graph と Message thread

Graph workspace panel は `/api/graph` を読み、外部ライブラリなしの SVG graph として表示します。
node をクリックすると該当 record を detail modal で開けます。modal 内にも選択 item の
小さな依存 graph を表示します。modal graph は depth 2 の subgraph を読み込むため、
間接的な blocker や related record も modal 内で確認できます。

Message item (`type:M`) で `id:` がある場合、detail modal に thread section を表示します。
modal には返信 form も表示されます。返信は root message の `id:` を `parent:` に
持つ record として扱います。

## Chart

Chart endpoint は browser 描画用に安定した `labels` と `datasets` 配列を返します。
`GET /api/chart/elapsed` は `from`、`to`、`project`、`group` などの実用的な
filter を受け付けます。

```sh
curl "http://127.0.0.1:8000/api/chart/elapsed?from=2026-06-01&to=2026-06-30&project=research"
```

## Display mode

補足:

- Display mode / Kiosk mode は URL 状態に追従します。ブラウザの戻る/進む操作で mode が外れた場合、専用 CSS、時計、auto-scroll、Exit ボタンも解除されます。
- `display_title=TEXT` を付けると、Display mode 中だけ subtitle を差し替えられます。
- Timeline view は表示中に now line を定期的に更新します。対象期間に dated record がない場合は、`due:` / `from:` / `notify_at:` などの追加例を含む empty state を表示します。
- Header button、workspace tab、Timeline / Calendar control、sort/group/export、record editor には viewport-aware な hover/focus help が表示されます。

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

## Message API Details

Message type (`M`) は main REST API table の endpoint に加え、以下のような
message-oriented payload と filter を使えます。

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

## ID / Thread / Notification Notes

主要 endpoint は main REST API table に含まれています。この節では、ID 操作、
thread、notification の実用上の注意点をまとめます。

| Method | Path | 目的 |
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

## Link API Details

`GET /api/links` は `parent:`、`ref:`、`depends_on:`、`blocks:`、`related:`、`duplicate_of:`、`replaced_by:` の ID 参照を一覧表示します。

```sh
curl "http://127.0.0.1:8000/api/links"
curl "http://127.0.0.1:8000/api/links?id=task_001&direction=incoming"
curl "http://127.0.0.1:8000/api/links?relation=depends_on,blocks"
```

query parameter:

| Parameter | 意味 |
|---|---|
| `id` | 指定 ID に接続する link だけを表示 |
| `direction=incoming\|outgoing\|both` | `id` 指定時の方向 |
| `limit` | 最大件数 |

### port を bind できない場合

`serve` がすぐ終了する場合、port を bind できていません。
`lifetxt` は起動前に確認し、原因を明示します。

```
ERROR: Cannot bind 127.0.0.1:8000 ([WinError 10013] ...).
Windows is reserving that port, so nothing can bind it even though nothing is listening.
```

**Windows の予約 port。** Hyper-V、WSL、Docker は port の範囲を予約します。
予約された port は誰も listen していなくても bind できないため、
`netstat` では何も見えず原因が分かりにくくなります。
予約範囲は次で確認できます。

```powershell
netsh interface ipv4 show excludedportrange protocol=tcp
```

port 8000 は予約範囲に入っていることがよくあります。範囲外で起動してください。

```sh
lifetxt serve life.txt --port 8080
```

毎回指定しなくて済むよう config に既定値を設定することもできます。

```json
{ "web": { "port": 8080 } }
```

**port が使用中の場合。** 別のプロセスが掴んでいます。
そのプロセスを止めるか、別の port を使ってください。

**1024 未満の port。** macOS や Linux では管理者権限が必要です。
1024 より大きい port を使ってください。

