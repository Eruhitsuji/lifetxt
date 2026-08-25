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

## 互換性・migration・downgrade

`reports` は additive な設定です。`reports` が無い既存設定の動作は変わりません。
`life.txt` grammar の migration は不要です。report profile 非対応 version へ戻す場合は
`reports` section を削除または無視すればよく、生成 report は派生 output なので
`life.txt` 自体の変換は必要ありません。

登録済み設定 metadata は、例えば `lifetxt config explain reports.weekly.period` で確認できます。
