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
