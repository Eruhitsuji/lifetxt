# 開発チケット

lifetxt はデータベースを使わず、プレーンテキストの Task モデルも置き換えずに、
Redmine 風のチケット管理を追加します。チケットは `record:ticket` を付けた通常の
`T` レコードで、既存のフィルタ・アジェンダ・レポートがそのまま理解します。チケット層
は、正規フィールド・粗い `[ ]`/`[x]` の上に載る詳細な `ticket_status`・検証・集約を
加えます。

チケットワークフローを必要としない運用上の懸念には、汎用の `record:issue` レコードが
引き続き使えます。

## フィールド

チケットは次の正規フィールドを持てます（レジストリ管理のものは設定で検証）。

`tracker`・`ticket_status`・`priority`・`severity`・`reporter`・`assignee`・
繰り返し `watcher`・`component`・`category`・`version`・`milestone`・`sprint`・
`est`・`elapsed`・`story_points`・`resolution`・`closed_by`・`branch`・繰り返し
`commit`/`pr`・`build`、および共有リレーションキー `parent`・`depends_on`・
`blocks`・`related`・`duplicate_of`・`replaced_by`。

設定された型付きカスタムフィールドも通常のdetail keyとして保存されます。そのため、
レジストリを知らないツールでもlife.txt行を読みやすいまま保持できます。

## ステータス対応

`ticket_status` は詳細な状態で、粗い life.txt ステータスに対応づけられるため既存の
フィルタが機能し続けます。

| ticket_status                          | life.txt |
| -------------------------------------- | -------- |
| new, triaged, assigned                 | `[ ]`    |
| in_progress, review, testing           | `[/]`    |
| needs_info, blocked                    | `[?]`    |
| deferred                               | `[>]`    |
| resolved, closed                       | `[x]`    |
| rejected, duplicate, wont_fix          | `[-]`    |

矛盾する組（例: `[ ]` 行に `ticket_status:closed`）は `TK003` として報告されます。
対応は `ticketing.statuses` で上書き・拡張できます。

## 設定

```json
{
  "ticketing": {
    "id_prefix": "BUG",
    "trackers": ["bug", "feature", "task", "support"],
    "priorities": ["low", "normal", "high", "urgent"],
    "severities": ["minor", "major", "critical", "blocker"],
    "required_fields": ["assignee"],
    "defaults": { "tracker": "task", "priority": "normal" },
    "write": { "require_revision": true },
    "custom_fields": {
      "risk_score": {
        "type": "integer",
        "required": true,
        "default": 3,
        "minimum": 0,
        "maximum": 10,
        "filterable": true,
        "searchable": true,
        "privacy": "internal",
        "trackers": ["bug", "security"]
      },
      "customer_tier": {
        "type": "enum",
        "enum": ["free", "standard", "enterprise"],
        "default": "standard",
        "filterable": true,
        "privacy": "private",
        "editable_roles": ["manager"],
        "visible_roles": ["manager", "viewer"]
      },
      "security_label": {
        "type": "string",
        "repeatable": true,
        "pattern": "^[a-z0-9_-]+$",
        "privacy": "secret"
      }
    }
  }
}
```

`ticketing.write.require_revision` を有効にすると、既存チケットを変更するすべての操作で
正確なソースファイルrevisionが必須になります。ローカル利用との後方互換性のため既定では
任意ですが、スクリプトや将来のリモートアダプターでは有効化を推奨します。

## 型付きカスタムフィールド

`ticketing.custom_fields` はチケット専用のversioned registryです。未知のlife.txt keyを
グローバルに不正扱いするものではありません。設定されていないdetail keyは従来どおり
保持され、カスタムフィールド検証では無視されます。

対応する型は `string`・`integer`・`number`・`boolean`・`date`・`datetime`・
`duration`・`enum` です。さらに次を設定できます。

- `required`・`default`・`repeatable`
- `enum`/`values`、数値の `minimum`/`maximum`、文字列の `min_length`/`max_length`、
  正規表現 `pattern`
- `trackers`・`projects` による適用範囲
- `filterable`・`searchable` メタデータ
- `public`・`internal`・`private`・`secret` の `privacy`
- 将来のrole policy用 `editable_roles`・`visible_roles`

正規・relation・system ticket keyをカスタムフィールドとして再定義することはできません。
`ticket new` は適用対象のdefaultを自動設定します。既存チケットのexact-revision変更では、
共有lock内で変更後のカスタム値を検証し、不正なeditを置換前に拒否します。

有効なレジストリと診断を確認します。

```console
$ lifetxt ticket fields
$ lifetxt ticket fields --tracker bug --project web --role manager --format json --pretty
```

作成時は `--field` を使用します。repeatableな定義には繰り返し指定できます。

```console
$ lifetxt ticket new "Login fails" --tracker bug --project web \
    --field risk_score=7 \
    --field customer_tier=enterprise \
    --field security_label=auth \
    --field security_label=cve
```

既存チケットは通常の `--set`/`--unset` を使用するため、同じrevision契約が維持されます。

```console
$ lifetxt ticket edit BUG-1 --revision SHA256 --set risk_score=8
```

専用list filterで使用できるのは `filterable: true` のフィールドだけです。

```console
$ lifetxt ticket list --field risk_score=8 --has-field customer_tier
```

`searchable` は将来の共有query・Web・TUI・saved view・remote adapter向けに公開される
メタデータであり、無関係なglobal searchへ暗黙に追加されません。privacy・roleメタデータも
capability discoveryへ公開されますが、サーバー側の権限・履歴・clock・復旧契約が完成するまで
remote ticket writeは無効のままです。

## コマンド

```console
$ lifetxt ticket new "Login fails" --tracker bug --priority high --assignee alice --project web
$ lifetxt ticket list --tracker bug --open
$ lifetxt ticket show BUG-1
$ lifetxt ticket revision BUG-1
$ lifetxt ticket assign BUG-1 carol
$ lifetxt ticket edit BUG-1 --set severity=critical --set component=auth --unset milestone
$ lifetxt ticket link BUG-2 depends_on BUG-1
$ lifetxt ticket unlink BUG-2 depends_on BUG-1
$ lifetxt ticket close BUG-1 --status resolved --resolution "fixed in v2"
$ lifetxt ticket reopen BUG-1
$ lifetxt ticket validate
```

`ticket new` は `id_prefix` から次の id を採番します。`ticket show` は現在のレコード・
設定済みカスタムフィールド・リレーション・被参照リンクを、何も変更せずに集約します。
`close` は終端ステータス・`closed_by`・`--resolution` を設定し、`reopen` は解除します。

## 正確なrevisionを使用した書き込み

`ticket revision ID` は、対象チケットを含む権威ソースファイルの正確なバイト列から計算した
小文字SHA-256を表示します。その値を `edit`・`assign`・`close`・`reopen`・`link`・
`unlink` に渡します。

```console
$ lifetxt ticket revision BUG-1
f28c83d4c0f17a3f...
$ lifetxt ticket edit BUG-1 --revision f28c83d4c0f17a3f... --set priority=urgent
Edited BUG-1 in life.txt
  revision: f28c83d4c0f17a3f... -> 74108639317b8870...
```

`--expected-revision` は `--revision` の別名です。弱いETagや引用符付きETagも同じtokenへ
正規化されます。tokenの取得後にファイルが変更されていた場合、コマンドは競合を報告し、
新しいファイル内容を変更しません。revision確認・チケット再検索・意味的変換・検証・置換は、
すべて共通のsidecar lock/CAS mutation契約の中で実行されます。

1回の操作だけtokenを必須にする場合は `--require-revision`、6種類すべての変更操作で
必須にする場合は `ticketing.write.require_revision` を使用します。`--dry-run` でも指定した
revisionを検証し、ファイルを書き換えずに変更後の予測revisionを表示します。

```console
$ lifetxt ticket link BUG-2 depends_on BUG-1 \
    --revision f28c83d4c0f17a3f... --dry-run
```

機械可読形式で取得する場合は次を使用します。

```console
$ lifetxt ticket revision BUG-1 --json --pretty
```

JSONにはチケットID、所有ファイル、ハッシュアルゴリズム、revisionが含まれます。

## 検証

`ticket validate` は次を報告します。

- `TK001` id の無いチケット
- `TK002` 未知の `ticket_status`
- `TK003` `ticket_status` が粗い life.txt ステータスと矛盾
- `TK004` 設定レジストリに無い値（tracker/priority/severity/component）
- `TK005` 設定された必須フィールドの欠落
- `TK006` カスタムフィールドレジストリの設定不備
- `TK007` 適用対象の必須カスタムフィールド欠落
- `TK008` 非repeatableフィールドの重複
- `TK009` 型または制約に違反するカスタム値
- `TK010` tracker/project適用範囲外のカスタムフィールド

## MCP

読み取り専用ツール: `list_tickets`・`get_ticket`・`validate_tickets`。チケットの
書き込みは CLI 経由です（ワークフロー強制のリモート書き込みは後続トラック）。
capability discoveryはローカルのチケットrevision契約と型付きカスタムフィールド契約を
公開しますが、リモートのチケット書き込みを有効とは通知しません。チケットは
`ticket-v1.schema.json`、組み込みフィールドは `ticket-field-registry-v1.schema.json`、
カスタム定義は `ticket-custom-field-registry-v1.schema.json` に従います。


## ワークフロー・追記専用履歴・時間記録

監査履歴付きの操作は `ticket-workflow-v1` を使用します。既定の遷移グラフは、
トリアージ・担当・作業中・レビュー・テスト・情報待ち／ブロック・終端状態・
再オープンを扱います。`ticketing.workflow.transitions` では、遷移元、許可role、
必須フィールド、必須コメント／resolution、固定のset/unset副作用、追記する
event種別を設定できます。

```json
{
  "ticketing": {
    "activities": ["development", "review", "testing"],
    "workflow": {
      "local_role": "administrator",
      "transitions": {
        "review": {
          "from": ["in_progress", "testing"],
          "roles": ["developer", "manager"],
          "required_fields": ["pr"],
          "comment_required": true
        },
        "resolved": {
          "from": ["review", "testing"],
          "roles": ["manager"],
          "resolution_required": true,
          "event": "closed"
        }
      }
    }
  }
}
```

変更前に有効な遷移を確認できます。

```console
$ lifetxt ticket workflow --role manager --format json --pretty
```

監査履歴付きの書き込みでは、チケットを所有するファイルの正確なrevisionが常に
必要です。現在のチケット更新と `record:ticket_event` Note の追記を、1回の
sidecar lockと1回のatomic replaceで確定します。

```console
$ REV=$(lifetxt ticket revision BUG-1)
$ lifetxt ticket transition BUG-1 in_progress \
    --revision "$REV" --actor alice --comment "Started" \
    --at 2026-07-25T10:00:00+09:00

$ REV=$(lifetxt ticket revision BUG-1)
$ lifetxt ticket comment BUG-1 "Root cause identified" \
    --revision "$REV" --author alice

$ REV=$(lifetxt ticket revision BUG-1)
$ lifetxt ticket reassign BUG-1 bob --revision "$REV" --actor alice
$ lifetxt ticket change BUG-1 --revision "$REV" --actor alice \
    --set severity=critical --unset milestone
$ lifetxt ticket watch BUG-1 carol --revision "$REV" --actor alice
$ lifetxt ticket unwatch BUG-1 carol --revision "$REV" --actor alice
```

`--dry-run` はファイルを書き換えず、生成eventと変更後revisionを計算します。
`--transaction-id` では再試行／監査用の安定IDを指定でき、重複transactionは拒否
されます。event IDとsequenceはlock中に採番されるため、同一timestampでも順序は
決定的です。古いrevisionではチケットと履歴の両方が変更されません。

`record:ticket_event` は追記専用で、安定ID、親チケット、event種別、author、
offset付きUTC timestamp、チケット単位のsequence、transaction ID、変更前の
ticket revision、変更フィールド要約、コメント、任意のprovider／参照情報を
保持します。

```console
$ lifetxt ticket activity BUG-1
$ lifetxt ticket validate-history --format json --pretty
```

新しい監査履歴付きコマンドは追加機能です。互換性のため従来の
`ticket edit|assign|close|reopen|link|unlink` も残りますが、event追記を保証する
操作とは扱いません。履歴が必要な運用では `ticket transition`、`ticket reassign`、
`ticket change`、および新しいcomment・watch・planning・time操作を使用します。

時間は追記専用の `record:time_entry` Noteとして保存します。

```console
$ REV=$(lifetxt ticket revision BUG-1)
$ lifetxt ticket log-time BUG-1 90m \
    --revision "$REV" --user alice --activity development \
    --date 2026-07-25 --comment "Implemented validation"

$ lifetxt ticket time BUG-1 --format json --pretty
```

修正は既存entryを書き換えず、`--corrects TIME-ID` を付けた新しいentryとして
記録します。参照されたentryは履歴に残りますが、権威ある合計では置き換えられます。
従来のチケット `elapsed:` は別値として返され、二重計上されません。timer／
work-sessionからの変換は後続のproposal／transaction統合であり、自動実行しません。

## バージョン・スプリント・バックログ・ロードマップ

バージョンとスプリントは、`record:version`／`record:sprint` を付けた通常のNoteです。
書き込みには正確なファイルrevisionが必要です。

```console
$ REV=$(lifetxt ticket file-revision)
$ lifetxt version new "v1.0" --project web --due 2026-08-15 \
    --revision "$REV"

$ REV=$(lifetxt ticket file-revision)
$ lifetxt sprint new "Sprint 12" --project web \
    --start 2026-07-20 --end 2026-08-02 \
    --version VER-1 --capacity 30 --revision "$REV"

$ REV=$(lifetxt ticket revision BUG-1)
$ lifetxt ticket plan BUG-1 --sprint SPR-1 \
    --revision "$REV" --actor alice

$ lifetxt ticket backlog --project web
$ lifetxt ticket roadmap --project web --format json --pretty
```

version stateは `open`・`locked`・`released`・`closed`、sprint stateは
`planned`・`active`・`closed` です。未完了ticketがあるversionのrelease／close、
またはsprintのcloseは拒否されます。範囲／carry-overを確認したうえでのみ
`--force` を指定できます。membershipはticketと同じprojectに限定され、
capacity警告は任意のstory pointsを使用します。sprintにversionが設定されている
場合、`ticket plan` でversionも推論されます。

```console
$ REV=$(lifetxt ticket file-revision)
$ lifetxt version release VER-1 --revision "$REV"
$ lifetxt sprint start SPR-1 --revision "$REV"
$ lifetxt sprint close SPR-1 --revision "$REV"
$ lifetxt ticket validate-planning
```

現時点のatomic保証は、同じ権威life.txtファイル内のrecordが対象です。
ticket/event/time/planningを別ファイルへ分割する場合はrevision setと既存の
multi-target journal／recovery契約が必要なため、書き込み可能とは通知しません。
リモートticket書き込み、認証済みrole強制、watcher配信、timer副作用も無効のままです。

読み取り専用MCPには `get_ticket_workflow`・`get_ticket_activity`・
`get_ticket_time`・`get_ticket_planning`・`validate_ticket_history`・
`validate_ticket_planning` を追加します。capability discoveryは7つのworkflow／
event／time／planning schemaと、exact-revision・同一ファイルcompound境界を
公開します。
