# life.txt CLI ガイド

この文書は、次のコマンドで提供される CLI の詳細な使い方を説明します。

```sh
python -m lifetxt
```

CLI は外部依存なしで動作し、UTF-8 の `life.txt`、JSON、JSONL、CSV を扱います。
多くの読み込み系コマンドは、1 つ以上の path を受け取れます。path に `-` を指定するか
path を省略すると標準入力から読み込みます。

## 1. コマンド一覧

```sh
python -m lifetxt tour
python -m lifetxt check [path ...]
python -m lifetxt integrity [path ...]
python -m lifetxt ids [path ...]
python -m lifetxt links [path ...]
python -m lifetxt sources [path ...]
python -m lifetxt notes [path ...]
python -m lifetxt convert --from FORMAT --to FORMAT [path ...]
python -m lifetxt to-json [path ...]
python -m lifetxt to-jsonl [path ...]
python -m lifetxt to-csv [path ...]
python -m lifetxt demo [options]
python -m lifetxt markdown [path ...]
python -m lifetxt import-ics [path ...]
python -m lifetxt import [path ...]
python -m lifetxt sync-ics --url-env ENVVAR
python -m lifetxt filter [path ...]
python -m lifetxt from-json [path ...]
python -m lifetxt from-jsonl [path ...]
python -m lifetxt from-csv [path ...]
python -m lifetxt status [path ...]
python -m lifetxt notify [path ...]
python -m lifetxt agenda [path ...]
python -m lifetxt assist [options]
python -m lifetxt tui [path ...]
python -m lifetxt fzf [path ...]
python -m lifetxt timer start path --id ID
python -m lifetxt timer pause
python -m lifetxt timer resume
python -m lifetxt timer stop
python -m lifetxt timer summary [path ...]
python -m lifetxt stats [path ...]
python -m lifetxt lifecycle-stats [path ...]
python -m lifetxt git-hook install
python -m lifetxt completion bash
python -m lifetxt serve [path ...]
python -m lifetxt web [path ...]
python -m lifetxt mcp [path ...]
python -m lifetxt config init
python -m lifetxt config show
python -m lifetxt init
python -m lifetxt doctor
python -m lifetxt quick "Title"
python -m lifetxt add "Title"
python -m lifetxt done [path ...]
python -m lifetxt complete [path ...]
python -m lifetxt assign [path ...]
python -m lifetxt batch [path ...]
python -m lifetxt archive [path ...]
python -m lifetxt undo [path ...]
python -m lifetxt summary [path ...]
python -m lifetxt inbox [path ...]
python -m lifetxt cleanup [path ...]
python -m lifetxt health [path ...]
python -m lifetxt review [path ...]
python -m lifetxt who [path ...]
python -m lifetxt search PATTERN [path ...]
python -m lifetxt find TERM [path ...]
python -m lifetxt snapshot [path ...]
python -m lifetxt lint [path ...]
python -m lifetxt diff FILE_A FILE_B
python -m lifetxt plot [path ...]
python -m lifetxt export-heatmap [path ...]
python -m lifetxt migrate [path ...]
python -m lifetxt from-markdown [path ...]
python -m lifetxt deps [path ...]
python -m lifetxt tag list [path ...]
python -m lifetxt watch [path ...] -- COMMAND
python -m lifetxt encrypt [path ...]
python -m lifetxt decrypt [path ...]
python -m lifetxt share [path ...]
python -m lifetxt digest [path ...]
python -m lifetxt template list
python -m lifetxt help
python -m lifetxt workspace list
python -m lifetxt project list
python -m lifetxt portfolio [path ...]
python -m lifetxt today [path ...]
python -m lifetxt area list [path ...]
python -m lifetxt backlinks ID [path ...]
python -m lifetxt temporal ID [path ...]
python -m lifetxt timeline ID [path ...] [--since ISO] [--until ISO] [--event TYPE] [--limit N] [--as-of TIMESTAMP] [--json]
python -m lifetxt timeline --workspace-timeline [path ...] [--since ISO] [--until ISO] [--event TYPE] [--project NAME] [--limit N] [--json]
python -m lifetxt history-check [path ...] [--id ID] [--commit-limit N] [--json]
python -m lifetxt freebusy [path ...] --from START --to END
python -m lifetxt flow [path ...] --date YYYY-MM-DD --day-start HH:MM --day-end HH:MM [--format text|json]
python -m lifetxt item-uri format ID [--base-url URL] [--json]
python -m lifetxt item-uri parse URI [--json]
python -m lifetxt backup verify BACKUP
python -m lifetxt backup verify --latest [--destination DIR]
python -m lifetxt query "QUERY" [path ...] [--explain]
python -m lifetxt view list
python -m lifetxt group list [path ...]
python -m lifetxt message recipients [path ...]
python -m lifetxt person list [path ...]
python -m lifetxt proposal list
python -m lifetxt ticket list [path ...]
python -m lifetxt version list [path ...]
python -m lifetxt sprint list [path ...]
python -m lifetxt rrule daily
python -m lifetxt update-check
python -m lifetxt update
python -m lifetxt server-init --server-config server-init.json
python -m lifetxt server-update --server-config server-update.json
python -m lifetxt remote profile-list
python -m lifetxt vm run program.life.txt --entry s1
```

| Command | 目的 |
|---|---|
| `check` | life.txt の構文と意味的な警告を検査 |
| `ids` | item ID の存在、欠落、重複を監査 |
| `links` | item 間の ID 参照を表示 |
| `sources` | 各 item を所有する入力ファイルを表示 |
| `convert` | 共有item modelを経由して入力・出力formatを明示的に変換 |
| `to-json` | life.txt を JSON 配列へ変換 |
| `to-jsonl` | life.txt を JSONL へ変換 |
| `to-csv` | life.txt を CSV へ変換 |
| `demo` | demo、test、screenshot 用の有効な life.txt record を生成 |
| `markdown` | safe Markdown field を HTML / text / JSON / JSONL として描画 |
| `import-ics` | iCalendar `.ics` の予定を life.txt event item に変換 |
| `import` | `import-ics` の ics/markdown/todoist/github preset を束ねる統一エントリポイント |
| `sync-ics` | iCalendar URL を取得して life.txt event item を再生成 |
| `filter` | item を絞り込み、life.txt / JSON / JSONL で出力 |
| `from-json` | JSON を life.txt へ変換 |
| `from-jsonl` | JSONL を life.txt へ変換 |
| `from-csv` | CSV を life.txt へ変換 |
| `status` | `person:` ごとの最新 `S` status / presence を表示 |
| `state` (`s`) | 直前の open な status を閉じて新しい presence status を記録 |
| `files` | `file:` / `dir:` attachment の確認・検証・hash 付与 |
| `start` | 作業開始: task を進行中に、timer 開始、presence を記録 |
| `stop` | 作業終了: timer 停止して `elapsed:` を記録、presence を閉じる |
| `notify` | type `M` の通知対象を表示、または常駐監視 |
| `agenda` | 日時範囲に関連する item を表示 |
| `assist` | 対話またはフラグで item を作成・更新 |
| `tui` | task、agenda、status を対話的な端末 workspace で操作 |
| `fzf` | `fzf` または `peco` で item を選択し action を実行 |
| `timer` | item の作業時間を計測し `elapsed:` に記録 |
| `stats` | task、habit、mood、project の統計を表示 |
| `git-hook` | life.txt 検査用 Git hook を導入または確認 |
| `completion` | shell completion script を生成 |
| `serve` | 任意機能の FastAPI REST API とブ�