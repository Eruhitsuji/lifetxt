# 定期 Markdown レポート

`lifetxt report` は、既存の `share --format markdown` レポートを named profile として
再現可能に実行するための CLI です。生成 Markdown は派生 artifact であり、authoritative
な記録は引き続き `life.txt` です。

## レポートを設定する

`.lifetxt.json` など有効な設定ファイルのトップレベルに `reports` を追加します。

```json
{
  "paths": ["life.txt"],
  "defaults": {"timezone": "Asia/Tokyo"},
  "reports": {
    "weekly": {
      "period": "weekly",
      "title": "Weekly Review",
      "output": "~/Documents/Obsidian/Life/Weekly/{iso_year}-W{iso_week}.md",
      "mode": "replace",
      "frontmatter": true
    }
  }
}
```

profile で使用できる設定は次のとおりです。

| Setting | 型 | 既定値 | 意味 |
| --- | --- | --- | --- |
| `period` | `daily|weekly|monthly` | 必須 | レポートの暦期間。週は月曜から日曜。 |
| `output` | string | なし | Markdown 出力 path template。`report run` では必須。相対 path は config file の directory を基準に解決。 |
| `title` | string | share の既定値 | 任意のレポート title。 |
| `project` | string | なし | 任意の project filter。 |
| `type` | string | なし | 任意の item type filter。 |
| `tag` | string | なし | 任意の tag filter。 |
| `open` | boolean | `false` | true の場合、未完了 workflow item のみに限定。 |
| `mode` | `replace|create|append` | `replace` | 生成 file の書き込み方式。 |
| `frontmatter` | boolean | `true` | Markdown 本文の前に生成レポート metadata を追加。 |

未知の profile key は profile 読み込み時に明示的な error になります。本文生成には既存の
`share --format markdown` を再利用し、具体的な `--after` / `--before` を渡すため、
period は見出しだけでなく実際に含まれる item の期間を制限します。

`output` では次の placeholder を使えます。

- `{date}` — period 開始日 (`YYYY-MM-DD`)
- `{year}` — period 開始日の4桁年
- `{month}` — 2桁月
- `{iso_year}` — ISO week year
- `{iso_week}` — 2桁 ISO week number

format specifier や任意式は placeholder に指定できません。

## コマンド

設定済み profile を一覧表示します。レポート生成や file write は行いません。

```sh
python -m lifetxt report list
```

stdout へ preview します。`preview` は設定された出力先へ書き込みません。

```sh
python -m lifetxt report preview weekly
```

設定された出力先へ生成します。

```sh
python -m lifetxt report run weekly
```

`replace` は派生 file を atomic に置換します。`create` は既存 target の上書きを拒否します。
`append` は既存 file と完全な1回分の生成レポートを合わせた内容を atomic に書き戻します。
必要な親 directory は自動作成します。

1つの profile、または `--all` ですべての profile の設定を、レンダリング・
書き込み・network access なしで検証します。

```sh
python -m lifetxt report validate weekly
python -m lifetxt report validate --all
```

profile が実際に何をするか -- 解決済みの period・出力先 path・scope、
（Report v2 profile であれば）provider 一覧 -- を、本文をレンダリングせず、
何も書き込まずに表示します。

```sh
python -m lifetxt report inspect weekly
python -m lifetxt report inspect weekly --format json
```

`validate`/`inspect`/`preview`/`run` の使い分けと完全な契約については、
下記の[「profile を validate / inspect する」](#profile-を-validate-inspect-する)
を参照してください。

## 生成 metadata

`frontmatter: true` の場合、出力の先頭には次のような metadata が入ります。

```yaml
---
generator: lifetxt
report_schema: lifetxt-report-v1
report: "weekly"
period: weekly
period_start: 2026-08-24
period_end: 2026-08-30
generated_at: "2026-08-25T18:05:00+09:00"
timezone: "Asia/Tokyo"
---
```

`append` では2回目以降の metadata block は document-level YAML frontmatter ではなく、
Markdown 内部の区切りとして扱われます。Obsidian で period ごとに1 file を作る用途では
`replace` または `create` を推奨します。

## Obsidian

Obsidian は生成 Markdown をそのまま読み込めます。例えば `output` を Vault 内へ向けます。

```json
{
  "period": "daily",
  "output": "~/Documents/MyVault/Life/Daily/{date}.md",
  "mode": "replace"
}
```

Obsidian plugin や API は不要です。lifetxt は通常の Markdown file を書き出すだけなので、
Obsidian は派生 artifact に対する交換可能な view のままです。

## Notion-compatible export

生成された `.md` file は通常の Markdown として Notion import に利用できます。この機能は
Notion API を呼び出さず、page の作成/upsert や自動同期も行いません。これらの network
side effect は今回の CLI-first report contract には含めません。

## 定期実行

lifetxt は named report が **何を生成するか** を定義します。**いつ実行するか** は OS の
scheduler に委譲します。lifetxt 内に常駐 scheduler daemon は追加しません。

例えば毎週月曜の cron は次のようにできます。

```cron
0 0 * * 1 cd /path/to/workspace && python -m lifetxt report run weekly
```

同じ考え方で systemd timer、Windows Task Scheduler、`launchd` を使用できます。手動実行と
定期実行の双方で同じ `report run NAME` を呼ぶことで、生成 contract を一つに保ちます。

## Report v2: 既存の集計を組み合わせる (`sections`)

profile に `sections` 配列があると **Report v2** が有効になります。これは上記の
`share --format markdown` への委譲ではなく、`review` / `stats` / `agenda` /
`command_center` / `portfolio` / `health` など既存の deterministic な domain
aggregation を組み合わせる composition layer です。v2 profile はこれらの意味を
再実装せず、選択・並び替え・rendering のみを行います。

```json
{
  "reports": {
    "weekly-review": {
      "period": "weekly",
      "output": "reports/{iso_year}-W{iso_week}.md",
      "compare": "previous",
      "sections": [
        {"type": "review"},
        {"type": "stats", "group": "daily"},
        {"type": "agenda", "range": "next-period"},
        {"type": "command-center", "horizon": 3},
        {"type": "project-health"},
        {"type": "next-actions"},
        {"type": "inbox"},
        {"type": "ticket-attention"},
        {"type": "health"}
      ]
    }
  }
}
```

各 section は `{"type": "<name>", ...options}` の形です。`title` は見出しの
上書き指定に使えます。利用できる type は次のとおりです。

| Type | 再利用先 | 主な option |
| --- | --- | --- |
| `review` | `lifetxt.review.build_review()` | `project` |
| `stats` | `lifetxt.stats.build_stats()` | `group` (`daily`/`weekly`/`monthly`) |
| `agenda` | `lifetxt.agenda.agenda_records()` | `range` (既定 `period`、`next-period`、`previous-period`) |
| `command-center` | `lifetxt.command_center.command_center()` | `horizon`、`next_actions_limit`、`inbox_limit`、`ticket_stale_after_days` |
| `project-health` | `lifetxt.projects.portfolio()` | `include_archived` |
| `next-actions` | 既存の actionable item 定義 | `limit` |
| `inbox` | Unified Inbox summary | `limit` |
| `ticket-attention` | Command Center の ticket-attention rule | `stale_after_days` |
| `health` | `lifetxt.health.build_health()`（`lifetxt health` と同一 rule） | `since_days`、`lookahead_days`、`ignore_codes`、`kinds` |

未知の `type`、あるいは provider が理解しない option は、profile を読み込んだ時点で
（rendering の前に）明示的な error になります。

### レポート全体の scope (`scope`)

```json
{
  "reports": {
    "research-weekly": {
      "period": "weekly",
      "scope": {"project": ["research"], "tag": ["experiment"], "open": false},
      "sections": [
        {"type": "review"},
        {"type": "stats", "group": "daily"},
        {"type": "agenda", "range": "next-period"}
      ]
    }
  }
}
```

`scope` は、section provider が実行される **前に一度だけ** parse 済み item set を
絞り込みます。各 provider が個別に `project`/`tag`/`open` option を持つのではなく、
すべての section が同じ「このレポートは何についてのものか」に合意する形です。
CLI `filter`/`agenda` command や `query` が既に使っている filtering primitive
`lifetxt.agenda.filter_items()` を再利用しており、report 専用の filter engine
ではありません。provider 自身の option（例えば `agenda` の `range`）で scope
された集合をさらに絞ることはできますが、`scope` が除外した item を provider が
見ることはありません。

対応 field は `project`、`tag`、`type`、`status`、`person`（それぞれ string
または string の array）、および `open`（boolean、v1 の `open` 相当）です。
複数 field を組み合わせるとすべての条件が AND で適用されます。

後方互換のため、v1 の top-level `project`/`type`/`tag`/`open` key は v2 profile
でも引き続き使え、`scope` への compatibility alias として取り込まれます。
同じ field に対して legacy key と `scope` で異なる値を指定した場合は、profile
読み込み時に silent に片方を採用せず明示的な error になります。

```json
{"project": "home", "scope": {"project": "work"}}
```

```text
Report profile weekly: legacy `project` and `scope.project` specify conflicting values.
```

既存の v1 profile（`sections` 無し）は影響を受けません。top-level の
`project`/`type`/`tag`/`open` は `scope` とは無関係に、上記のとおり
そのまま動作します。

### 出力 format

```json
{"format": "markdown", "sections": [...]}
```

`format` は `markdown`（既定）、`json`、`html` のいずれかです。3つとも同じ
Report Model を rendering するだけで、`life.txt` の再 parse や section の
再導出は行いません。1回だけ上書きするには `--format` を使います。

```sh
python -m lifetxt report preview weekly-review --format json
```

`--format` は `sections` を持つ profile でのみ有効で、v1 profile に対しては
拒否されます。

### 過去 period の指定 (`--date`, `--previous`)

```sh
python -m lifetxt report preview weekly-review --date 2026-07-15
python -m lifetxt report run weekly-review --previous
```

`--date YYYY-MM-DD` はその日付を含む period を生成します。`--previous` は
現在時刻から見て直近に完了した period を生成します（period が切り替わった
直後に scheduler から呼ぶ形）。`--date` と `--previous` は同時指定できません。
どちらも v1 profile に対しても有効です。

### 直前 period との比較 (`compare`)

```json
{"compare": "previous", "sections": [{"type": "stats"}]}
```

設定すると、各 section は直前 period についても計算され、一致する数値 field
ごとの汎用 diff（`{"current": ..., "previous": ..., "delta": ...}`）が
その section の `compare` として付与されます。section 固有の比較 logic は
一切書かれておらず、provider が返した結果を機械的に diff するだけです。

### External-safe レポート (`audience`)

```json
{
  "audience": "external",
  "sections": [{"type": "stats"}, {"type": "health"}]
}
```

`audience` は `private`（既定）または `external` です。`external` は意図的に
保守的で、aggregate のみの section type（`stats`、`health`、`project-health`）
のみ許可されます。`review`、`agenda`、`command-center`、`next-actions`、
`inbox`、`ticket-attention` を `audience: external` で使うと、profile 読み込み時に
拒否されます。許可された section の data も rendering 前に redaction されます。
title・path・抜粋などの生の個人情報を含みうる field は削除され（削除した list は
`<field>_count` に置き換え）、その結果はさらに lifetxt が他所でも使っている
`remote_access.redact_remote_value()` による path/token redaction を defense in
depth として通過します。これは既存 `share` renderer 全体の汎用 redaction switch
ではなく、lifetxt 環境の外へ共有するレポート専用の、より狭い contract です。

### メール送信 (`email`, `report send`)

```json
{
  "email": {
    "to": ["me@example.com"],
    "subject": "lifetxt weekly report {period_start} - {period_end}",
    "smtp_host_env": "LIFETXT_SMTP_HOST",
    "smtp_port": 587,
    "smtp_user_env": "LIFETXT_SMTP_USER",
    "smtp_pass_env": "LIFETXT_SMTP_PASS"
  }
}
```

```sh
python -m lifetxt report send weekly-review
python -m lifetxt report send weekly-review --date 2026-07-15
python -m lifetxt report send weekly-review --dry-run
```

`email` は v1・v2 いずれの profile でも使えます。`to` は必須で、`subject` は
`{period_start}`、`{period_end}`、`{report}` の placeholder を使え、既定値は
`lifetxt report: <name>` です。SMTP host/username/password は指定した環境変数
（既定 `LIFETXT_SMTP_HOST`/`LIFETXT_SMTP_USER`/`LIFETXT_SMTP_PASS`）から
STARTTLS 経由で読み込まれ、これは `digest --format email` および notification
email と同じ delivery primitive です。`report send` は2つ目の SMTP 実装を
追加しません。`smtp_port` は任意の明示的な整数 port（例: STARTTLS 送信の
`587`、`1`〜`65535`）で、実際の network 接続の前に検証されます。省略すると
既存の既定 SMTP port がそのまま維持されます。`--dry-run` は接続を開かず、
環境変数の設定も不要なまま、送信内容（port を指定した場合はそれも含む）を
表示するだけです。

`lifetxt digest` も、既存の built-in review summary の代わりに report profile
をメッセージ source として使え、digest の既存 file/email/Slack delivery
channel をそのまま再利用します。

```sh
lifetxt digest --report weekly-review --format email --to me@example.com
lifetxt digest --report weekly-review --format file --path weekly.md
lifetxt digest --report weekly-review --date 2026-07-15 --format slack-webhook --url-env LIFETXT_SLACK_WEBHOOK
```

`--report` を指定した場合、`--week`/`--month`/`--project` は無視され、
profile 自身の period と filter が適用されます。

## profile を validate / inspect する

`report` の4つの subcommand は、実際に何をするかの度合いが異なる、
4つの異なる問いに答えます。

| Command | 問い | body をレンダリングする? | 書き込み/送信する? |
| --- | --- | --- | --- |
| `report validate` | この profile の設定は構造的に valid か? | いいえ | いいえ |
| `report inspect` | 解決後、どの period/output/scope/provider が使われるか? | いいえ | いいえ |
| `report preview` | レンダリングされたレポートはどう見えるか? | はい（stdout へ） | いいえ |
| `report run` / `report send` | レポートを生成する（あるいは生成してメール送信する）。 | はい | はい |

### `report validate`

```sh
python -m lifetxt report validate weekly
python -m lifetxt report validate --all
python -m lifetxt report validate weekly --format json
```

指定した1つの profile、または `--all` で全 profile を、`preview`/`run`/
`send` が使うのとまったく同じ profile validator（period/mode、v1・v2 の
互換性、`sections`/`scope`/`compare`/`format`/`audience`/`email` の shape）に
加え、`output` placeholder template の構文チェックだけを通して検証します。
`life.txt` の parse、section provider の実行、レポート本文のレンダリング、
file への書き込み、network 接続のいずれも行いません。

`--all` は最初の失敗だけでなく、**すべての** profile の結果を報告します:

```text
$ python -m lifetxt report validate --all
broken: FAIL: Report profile broken: Unknown report section type: 'nope'. Known types: ...
v2weekly: OK
weekly: OK
```

チェックしたすべての profile が valid なら exit status は `0`、そうでなければ
`1` になるため、`server-init`/`server-report` が定期 job を deploy する前の
CI や systemd の preflight step として使えます。`--format json` は
（`--all` の場合はリストの）小さく決定的な結果 object を出力します。
これは `preview --format json` が出す Report Model とは異なります。

### `report inspect`

```sh
python -m lifetxt report inspect weekly
python -m lifetxt report inspect weekly --date 2026-07-15 --format json
```

指定した invocation に対して `preview`/`run` が実際に使う解決済みの plan --
schema（`lifetxt-report-v1`/`lifetxt-report-v2`）、解決済みの
`period.start`/`period.end`/`timezone`、（`output` が設定されていれば）
解決済みの `output.path`、legacy alias 解決後の実効 `scope`、（Report v2
profile であれば）各 section 自身の option を含む順序付き `sections` 一覧 --
を、section のレンダリングや provider の呼び出し、file への書き込み、
SMTP への接続を一切行わずに表示します。`--date`/`--previous` は
`preview`/`run` が解決するのと同じ period を選択します。invalid な
profile は `report validate` と同一の validator を通して失敗します。

`email` の有無は boolean の `email_configured` としてのみ報告されます。
設定された環境変数の *名前* と secret の *値* は `inspect` の出力に
一切含まれません。

## Ubuntu Server での定期実行

新規・再構築の deployment 向けの `server-init` の opt-in `reporting` section
（`report run <profile> --previous` を実行する systemd oneshot ＋
`Persistent=true` timer を job ごとに生成）と、`server-init` を再実行せずに
既存 deployment へ1つの report job を追加/削除する
`lifetxt server-report plan|install|remove` については
[`docs/deployment/ubuntu-server.md`](../deployment/ubuntu-server.md) を
参照してください。

## 互換性・migration・downgrade

`reports` は additive な設定です。`reports` が無い既存設定の動作は変わりません。
`life.txt` grammar の migration は不要です。report profile 非対応 version へ戻す場合は
`reports` section を削除または無視すればよく、生成 report は派生 output なので
`life.txt` 自体の変換は必要ありません。`sections` の無い profile は上記の v1 section の
とおり動作し続け、`sections` を追加した場合のみ Report v2 が有効になります。

登録済み設定 metadata は、例えば `lifetxt config explain reports.weekly.period` で確認できます。
