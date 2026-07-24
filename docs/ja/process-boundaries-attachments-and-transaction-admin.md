# 安全なプロセス境界・ディレクトリアタッチメント・トランザクション管理

このリリースでは、revision-aware write基盤を外部エディタ、ディレクトリ／パッケージアタッチメント、versioned transaction policy、プロセス強制終了ドリル、server-authoritative clock skewへ拡張します。

## 安全な外部エディタ

`lifetxt edit`は、authoritative fileをエディタへ直接渡しません。一時コピーを編集し、編集後のlife.txtを検証してからSHA-256 revision付きで反映します。

```bash
lifetxt edit life.txt --editor "code --wait" --show-diff
```

- `--review-only`: unified diffのみを返して書き込みません。
- `--reconcile`: 編集中にsourceが変化した場合、重複しない行範囲だけを保守的にthree-way reconcileします。
- `--keep-temp`: 手動復旧用に一時コピーを残します。
- `--dry-run`: 従来どおりeditor commandだけを表示します。

TUIとfzf/pecoのeditor handoffも同じ契約を使用します。

## ディレクトリ／パッケージアタッチメント

```bash
lifetxt attachment directory-reference life.txt \
  --id T-1 \
  --file ./attachments/specs \
  --item-revision LIFE_SHA256 \
  --require-revisions
```

```bash
lifetxt attachment package life.txt \
  --id T-1 \
  --source ./specs \
  --file ./attachments/specs.zip \
  --item-revision LIFE_SHA256 \
  --attachment-revision '<missing>' \
  --require-revisions
```

パッケージはpath順、固定ZIP metadata、fileごとのSHA-256、`lifetxt-package-manifest.json`を使用して決定的に生成されます。file数、合計size、1 file size、ignore、MIME allow/deny policyをcommit前に検証します。symlinkと非regular fileは既定で拒否します。

外部変更後のhash参照更新：

```bash
lifetxt attachment reconcile life.txt \
  --id T-1 \
  --file ./attachments/report.pdf \
  --recorded-revision PREVIOUS_SHA256 \
  --item-revision LIFE_SHA256 \
  --require-revisions
```

OS open commandの検証・計画：

```bash
lifetxt attachment open life.txt --file ./attachments/report.pdf
```

既定ではcommand planのみを返します。`--execute`でplatform openerを起動します。

## Versioned transaction policy

```bash
lifetxt safety transactions policy-write \
  --journal-dir .lifetxt-transactions \
  --operator alice \
  --set max_transactions=750 \
  --pretty
```

`--expected-revision`でpolicy fileのstrict CASを行えます。古いunversioned policyは明示的にmigrationします。

```bash
lifetxt safety transactions policy-migrate \
  --journal-dir .lifetxt-transactions \
  --operator alice \
  --expected-revision POLICY_SHA256 \
  --pretty
```

新しい未知versionは自動downgradeせず拒否します。

Startup相当のpreflight：

```bash
lifetxt safety transactions preflight \
  --journal-dir .lifetxt-transactions \
  --pretty
```

`transactions.preflight_on_startup: true`にすると、writable Web/MCPはversion、容量、owner、permissionが安全でない場合に起動を拒否します。

管理auditとarchive rotation：

```bash
lifetxt safety transactions audit \
  --journal-dir .lifetxt-transactions \
  --operator alice \
  --event policy-reviewed \
  --details-json '{"ticket":"OPS-42"}' \
  --pretty
```

```bash
lifetxt safety transactions rotate-archives \
  --archive-dir transaction-archive \
  --max-archives 100 \
  --max-archive-bytes 1073741824 \
  --force \
  --operator alice \
  --pretty
```

## プロセス強制終了ドリル

```bash
lifetxt safety transactions drill \
  --point after_journal_publish \
  --recovery resume \
  --pretty
```

```bash
lifetxt safety transactions drill \
  --point after_target_commit \
  --recovery compensate \
  --pretty
```

child processを`os._exit`で終了し、journalをinspectしてresume／compensateします。これはinterpreter強制終了の検証であり、電源断、Windows replace、antivirus、cloud sync、network filesystemの保証ではありません。

## Remote clock skew

`GET /api/time`とMCP `get_clock_status`はserver-authoritative UTC timeを返します。client timestampを渡すとskewを測定します。

```json
{
  "clock": {
    "skew_warning_seconds": 30,
    "skew_reject_seconds": 300
  }
}
```

UTC offsetがないnaive timestampは拒否します。結果は`ok`、`warning`、`reject`、`not_measured`で、remote write可否も明示します。

## 公開schema

- `editor-session-v1.schema.json`
- `directory-package-v1.schema.json`
- `attachment-open-v1.schema.json`
- `transaction-policy-admin-v1.schema.json`
- `transaction-preflight-v1.schema.json`
- `clock-skew-v1.schema.json`

実platform検証とremote write enforcementは、引き続き独立したrelease gateです。
