# ユースケース別導入・運用ガイド

このガイドは、現在の lifetxt に実装されている機能だけを使って、用途ごとの導入方法と日常運用をまとめたものです。コマンドの全オプションは [CLI ガイド](./cli.md)、Web API / GUI は [Web ガイド](./web.md)、文法は [形式仕様](./life_txt_format_spec.md) を参照してください。

## 1. 共通セットアップ

```sh
git clone https://github.com/Eruhitsuji/lifetxt.git
cd lifetxt
python -m pip install -e .
python -m lifetxt init
python -m lifetxt doctor
python -m lifetxt check life.txt
```

Web UI も使う場合は追加依存を導入します。

```sh
pip install -r requirements-web.txt
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
```

推奨ディレクトリ構成です。

```text
workspace/
├── life.txt                         # 手書き・手動更新する主ファイル
├── .lifetxt.json                   # 設定
├── projects/                       # プロジェクト別ファイル
├── .generated/                     # ICS 同期などの生成物
├── archive/                        # 完了・過去データ
└── .cache/lifetxt/                 # 通知状態、undo、backup など
```

Git 管理する場合、通常は `life.txt`、`projects/`、必要に応じて `.lifetxt.json` を追跡します。秘密の URL、トークン、SMTP パスワードは追跡せず、環境変数を使ってください。`.generated/` と `.cache/lifetxt/` は再生成可能な場合は `.gitignore` に追加します。

## 2. 個人のタスク・GTD

### 導入

```sh
python -m lifetxt init
python -m lifetxt assist --interactive --append life.txt
```

例:

```txt
[ ] T Submit_Report id:task_report project:university due:2026-08-01 priority:A tag:next
[?] T Learn_New_Framework id:task_someday project:personal tag:someday
[ ] N Buy_Milk tag:inbox context:errands
```

### 日常運用

素早い入力には `quick`、整理には `inbox`、確認には `agenda`、`health`、`review` を使います。

```sh
echo "Call the clinic" | python -m lifetxt quick - --append life.txt
python -m lifetxt inbox life.txt
python -m lifetxt agenda life.txt --around now --window 1d --open
python -m lifetxt health life.txt
python -m lifetxt review life.txt --format markdown
```

項目に `id:` を付けると、完了、更新、依存関係の操作が安定します。

```sh
python -m lifetxt ids life.txt --assign --dry-run
python -m lifetxt ids life.txt --assign
python -m lifetxt done life.txt task_report
```

### 推奨ルーチン

- 朝: `agenda --around now --window 1d --open`
- 随時: `quick` で inbox へ記録
- 夕方: `health` で期限超過・blocked を確認
- 週末: `review --format markdown` で週次レビュー

## 3. 学生・研究者

### ファイル構成

```text
workspace/
├── life.txt
└── projects/
    ├── thesis.life.txt
    ├── experiments.life.txt
    └── papers.life.txt
```

```txt
[ ] T Thesis id:proj_thesis project:thesis due:2027-02-01
  [ ] T Literature_Review id:task_lit project:thesis due:2026-08-15
  [ ] T Run_Experiment_A id:task_exp_a project:thesis depends_on:task_lit est:4h
[N] N Paper_Memo id:note_paper_001 project:thesis ref:paper_001 body:"Main finding and limitations"
[N] J Research_Log on:2026-07-25 project:thesis mood:focused
| Reproduced the baseline.
| Next: inspect failure cases.
```

### 運用

```sh
python -m lifetxt check life.txt projects/
python -m lifetxt agenda life.txt projects/ --project thesis --window 2w
python -m lifetxt links life.txt projects/ --id proj_thesis
python -m lifetxt timer start projects/thesis.life.txt --id task_exp_a
python -m lifetxt timer stop
python -m lifetxt stats life.txt projects/ --project thesis
python -m lifetxt to-csv projects/papers.life.txt --type note -o papers.csv
```

実験や論文メモには `body:` と継続行 `|` を使い、タスク間の前後関係は `depends_on:` と `blocks:` で記録します。Web UI の Graph、Timeline、Review は研究計画全体の確認に向いています。

## 4. 小規模チームを Git で共有

### 導入

各項目に担当者、責任者、チーム、ID を付けます。

```txt
[ ] T Implement_Search id:task_search project:app team:core assignee:alice owner:bob due:2026-08-05
[/] S Working_Remotely person:alice state:busy from:2026-07-25T09:00+09:00 team:core
[ ] M Review_Request id:msg_review sender:alice recipient:bob channel:lifetxt notify_at:2026-07-25T16:00+09:00
```

Git hook を有効にすると commit 前に検証できます。

```sh
python -m lifetxt git-hook install
python -m lifetxt git-hook status
```

### 運用

```sh
python -m lifetxt filter "projects/**/*.life.txt" --assignee alice --open
python -m lifetxt status "projects/**/*.life.txt" --active
python -m lifetxt notify "projects/**/*.life.txt" --recipient bob
python -m lifetxt check life.txt projects/
```

運用ルールとして、1項目1行を基本にし、安定した `id:` を必須にし、生成ファイルと手編集ファイルを分けます。競合が起きた場合は両方の変更を確認してから `check` を再実行してください。複数人の同時書き込みを保証するサーバ型共同編集ではないため、Git の短い branch と小さい commit を推奨します。

## 5. Google Calendar などの ICS 同期

### 一度だけ取り込む

```sh
python -m lifetxt import-ics calendar.ics -o .generated/calendar.life.txt --tag calendar
```

### 定期同期

秘密の ICS URL はファイルに書かず環境変数へ入れます。

```sh
export LIFETXT_GOOGLE_CAL_ICS='https://example.invalid/private.ics'
python -m lifetxt sync-ics \
  --url-env LIFETXT_GOOGLE_CAL_ICS \
  -o .generated/google_calendar.life.txt \
  --cache-dir .cache/lifetxt \
  --tag google \
  --merge-existing \
  --soft-delete-missing
```

手書き項目は `life.txt`、同期項目は `.generated/` に分離します。

```sh
python -m lifetxt agenda life.txt .generated/google_calendar.life.txt --around now --window 1w
python -m lifetxt serve life.txt .generated/google_calendar.life.txt --write-file life.txt
```

## 6. Web UI をローカルまたはリモートで使う

### ローカル専用

```sh
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
```

### LAN・リモート公開

書き込み可能な状態で無認証公開しないでください。トークンは環境変数から渡します。

```sh
export LIFETXT_API_TOKEN='replace-with-a-long-random-value'
python -m lifetxt serve life.txt \
  --host 0.0.0.0 \
  --port 8000 \
  --token-env LIFETXT_API_TOKEN
```

閲覧専用のダッシュボードや壁面表示では `--read-only` を使います。

```sh
python -m lifetxt serve life.txt .generated/google_calendar.life.txt \
  --host 0.0.0.0 \
  --read-only
```

インターネットへ公開する場合は、HTTPS、アクセス制限、バックアップ、プロセス再起動、ログ管理を提供する reverse proxy またはホスティング基盤の背後で運用してください。`Dockerfile`、`railway.toml`、`render.yaml` は配置の出発点として利用できます。

## 7. 家族・共有ディスプレイ

共有端末では編集を無効にし、Kiosk / Display view を使います。

```sh
python -m lifetxt serve life.txt --host 0.0.0.0 --read-only
```

家族向けの項目例:

```txt
[ ] E School_Event on:2026-08-03 loc:school attendee:family
[ ] R Take_Out_Trash at:2026-07-28T07:00+09:00 repeat:weekly tag:home
[ ] N Shopping_List project:home body:"Milk, rice, detergent"
```

ブラウザ通知は画面上の `Enable Notifications` から許可します。端末のスリープ無効化、起動時の URL 自動表示、read-only の確認を行ってください。

## 8. AI クライアントから使う

stdio MCP server を起動します。

```sh
python -m lifetxt mcp life.txt
python -m lifetxt mcp life.txt .generated/google_calendar.life.txt --write-file life.txt
```

AI には最初は一覧、検索、agenda、graph などの読み込み操作だけを許可し、更新系 tool は対象ファイルと変更内容を確認してから使う運用が安全です。複数入力時は `--write-file` で書き込み先を固定してください。詳しくは [AI / MCP 連携ガイド](./ai-integration.md) を参照してください。

## 9. バックアップと保守

```sh
python -m lifetxt check life.txt projects/
python -m lifetxt doctor
python -m lifetxt health life.txt projects/
```

- Git を使う場合も、remote repository とは別の定期バックアップを持つ
- `.cache/lifetxt/` の状態ファイルを別環境へ不用意に共有しない
- `.generated/` を手編集しない
- `ids --assign` や一括更新は先に `--dry-run` を使う
- 更新後は `check` と必要な smoke test を実行する

## 10. 用途の選び方

| 用途 | 主な機能 | 推奨入口 |
| --- | --- | --- |
| 個人タスク | `quick`, `inbox`, `agenda`, `health`, `review` | CLI / TUI |
| 研究・学習 | hierarchy, links, timer, stats, journal | CLI + Web |
| Git共有チーム | assignee, owner, status, message, git-hook | Git + CLI / Web |
| カレンダー統合 | `import-ics`, `sync-ics`, multi-file | CLI + Web |
| 共有表示 | `serve --read-only`, Kiosk, Display | Web |
| AI連携 | `mcp`, API, fixed `--write-file` | MCP / Web API |
