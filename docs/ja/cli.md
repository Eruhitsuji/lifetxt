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
python -m lifetxt check [path ...]
python -m lifetxt ids [path ...]
python -m lifetxt links [path ...]
python -m lifetxt sources [path ...]
python -m lifetxt to-json [path ...]
python -m lifetxt to-jsonl [path ...]
python -m lifetxt to-csv [path ...]
python -m lifetxt demo [options]
python -m lifetxt markdown [path ...]
python -m lifetxt import-ics [path ...]
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
python -m lifetxt git-hook install
python -m lifetxt completion bash
python -m lifetxt serve [path ...]
python -m lifetxt mcp [path ...]
python -m lifetxt config init
python -m lifetxt config show
python -m lifetxt init
python -m lifetxt doctor
python -m lifetxt quick "Title"
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
```

| Command | 目的 |
|---|---|
| `check` | life.txt の構文と意味的な警告を検査 |
| `ids` | item ID の存在、欠落、重複を監査 |
| `links` | item 間の ID 参照を表示 |
| `sources` | 各 item を所有する入力ファイルを表示 |
| `to-json` | life.txt を JSON 配列へ変換 |
| `to-jsonl` | life.txt を JSONL へ変換 |
| `to-csv` | life.txt を CSV へ変換 |
| `demo` | demo、test、screenshot 用の有効な life.txt record を生成 |
| `markdown` | safe Markdown field を HTML / text / JSON / JSONL として描画 |
| `import-ics` | iCalendar `.ics` の予定を life.txt event item に変換 |
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
| `serve` | 任意機能の FastAPI REST API とブラウザGUIを起動 |
| `mcp` | AI client 向けの stdio MCP server を起動 |
| `config` | 外部 JSON config を作成または表示 |
| `init` | 対話形式の初回セットアップ。life.txt と .lifetxt.json を作成 |
| `doctor` | Python version、file、dependency、data の問題を検査 |
| `quick` (`q`) | 新規 item をすばやく作成して file に追記。title に `-` を渡すと stdin から読み込む |
| `done` (`d`) | task を完了にし `done:TODAY` を追記。habit (`H`) item では status を変えず、完了ログに `done:DATE` を追記する |（`--now` で時刻も記録）
| `complete` | repeat 付き task のインスタンスを完了し、次回インスタンスを生成。repeat が無ければ `done` と同じ動作 |
| `assign` | 既存 item の `assignee:` を変更 |
| `batch` | 複数の life.txt file に対して単純な操作を一括適用 |
| `archive` | 完了/中止済み item を別 file へ移動またはコピー |
| `undo` | 直前の書き込み操作前の状態に file を復元 |
| `summary` | life.txt file の概要を素早く表示 |
| `inbox` | project / due / assignee が未設定の open task を一覧表示 |
| `cleanup` | 問題を報告し、次に実行すべき command を提案するガイド付きナビゲーター |
| `health` | 停滞した task、未実施の habit、迫った deadline などの健全性チェック |
| `review` | 完了 task、habit、mood、elapsed time の期間サマリーを表示 |
| `who` | 各 person の最新 `S` item によるチーム presence サマリー |
| `search` | title や field 値の部分一致・正規表現で item を検索 |
| `snapshot` | life.txt file をタイムスタンプ付きで point-in-time backup |
| `lint` | key 名の typo、tag の大小文字、重複 key など style を検査 |
| `diff` | 2つの life.txt file の意味的な差分を表示 |
| `plot` | task/habit/mood/elapsed の統計を bar chart で表示 (text/SVG/PNG) |
| `export-heatmap` | task/habit の活動量を dependency-free SVG heatmap として出力 |
| `migrate` | life.txt file に in-place で format migration を適用 |
| `from-markdown` | Markdown task list (`- [ ] title`) を life.txt item に変換 |
| `deps` | `depends_on:`/`blocks:` の依存関係を tree 表示 |
| `tag` | tag 管理: list、rename、merge |
| `watch` | life.txt file の変更を監視し、変更のたびに command を再実行 |
| `encrypt` | passphrase で選択した field 値を in-place で暗号化 |
| `decrypt` | `enc:` 付き field 値を in-place で復号 |
| `share` | filter + review + chart をまとめた自己完結型 HTML/Markdown report を出力 |
| `digest` | `review` のサマリーを Slack、email、または local file へ送信 |
| `template` | 再利用可能な named item template を list / apply |

## 2. 共通仕様

### 2.0 外部 config

任意のコマンドで、subcommand の前に `--config FILE` を指定できます。省略時は
`LIFETXT_CONFIG`、`.lifetxt.json`、`lifetxt.config.json` の順で探索します。

```sh
python -m lifetxt config init -o .lifetxt.json
python -m lifetxt --config .lifetxt.json check
python -m lifetxt agenda --config .lifetxt.json --around now --window 1d
```

`paths` は life.txt 読み込み系 command の default input files、`write_file` は
`serve` の writable file、`message` は type `M` の作成 default、`sync_ics` は
calendar sync の default source / output を指定します。

### 2.1 入力 path

ファイルを読むコマンドでは、`path ...` は省略可能で、複数指定できます。
複数入力は指定順に読み込まれます。
`*.life.txt` や `projects/**/*.life.txt` のような glob も指定できます。
ディレクトリを指定した場合は、その直下の life.txt 風 `.txt` ファイルを読み込みます。

```sh
python -m lifetxt check life.txt
python -m lifetxt check work.life.txt home.life.txt
python -m lifetxt check "projects/**/*.life.txt"
python -m lifetxt check examples
python -m lifetxt check -
type life.txt | python -m lifetxt check
```

path を省略するか `-` を指定した場合、標準入力から読み込みます。
ファイル入力の場合、診断には line / column の前に source path が付きます。
stdin のみの場合は source path を省略します。

### 2.2 出力 path

`-o` / `--output` を持つコマンドでは、指定したファイルに出力します。
指定しない場合は標準出力へ出力します。

`assist` の作成モードでは、`--output FILE` は生成した 1 行を `FILE` に追記します。
ファイル全体を上書きしません。`assist --update` では、`--output FILE` は更新後の
ファイル全体を `FILE` に書き込みます。

### 2.3 出力形式

| Format | 意味 |
|---|---|
| `text` | 人間向けの表または診断 |
| `life` | life.txt 行 |
| `json` | JSON 配列 |
| `jsonl` | 1 行 1 JSON object |

### 2.4 入れ子 item

インデントされた item 行は、階層化 record として parse されます。子 item に
`parent:` がない場合、nearest less-indented ancestor の ID key、通常は `id:`、
から `parent:` を推論します。

```txt
[ ] T Research_Project id:proj_research
  [ ] T Literature_Review id:task_lit
    [N] N Reading_Memo
```

JSON / JSONL では、インデントされた item に `indent` field が含まれます。
life output は既定で元の行を保持します。`--canonical` を使うと、推論された
`parent:` が detail として展開される場合があります。

階層の canonical form は明示的な `parent:` です。`--canonical` は indentation を除去し、推論できる場合は `parent:` を保持または追加します。

### 2.5 終了コード

| Code | 意味 |
|---|---|
| `0` | 成功 |
| `1` | 検証エラーまたはコマンドエラー |
| `2` | サブコマンド不足などの CLI usage error |

### 2.6 フォーマット互換性

CLI は [life_txt_format_spec.md](./life_txt_format_spec.md) のファイル文法に従います。互換性で重要な点は次の通りです。

- life.txt ファイル内の detail は `key:value` のみです。
- `key=value` は `assist -d`、`assist --add-detail`、対話 detail prompt などの helper 入力だけで使える便宜記法です。
- JSON / JSONL では、detail は値が 1 つでも常に配列です。
- CSV 変換では `status`、`type`、`title` 列が必須です。それ以外の非空列は detail になり、JSON 配列セルは同じ key の複数値になります。
- `filter`、`agenda`、`stats`、`to-json`、`to-jsonl`、`to-csv`、`markdown` は status、type、project、tag、user、team、detail、text、time filter の実装を共有します。
- `check`、`ids`、`links`、各 converter は同じ parser を使うため、ある読み込み command が受け付ける構文は他の読み込み command でも受け付けます。
- 複数入力ファイルは ID 重複と参照検査では 1 つの論理集合として扱われます。

command 対応表:

| Command | life.txt 読み込み | life.txt 書き込み | 構文検証 | item filter |
|---|---:|---:|---:|---:|
| `check` | yes | no | yes | no |
| `ids` | yes | `--assign` 時のみ | yes | no |
| `links` | yes | no | yes | relation filter |
| `to-json`, `to-jsonl`, `to-csv`, `markdown` | yes | no | yes | yes |
| `from-json`, `from-jsonl`, `from-csv` | no | yes | serializer rule | no |
| `demo` | no | optional | generated item validation | type selection only |
| `filter` | yes | yes | yes | yes |
| `status` | yes | no | yes | `--person`, `--active` |
| `notify` | yes | no | yes | notification 固有 |
| `agenda` | yes | `--format life -o` 時のみ | yes | yes |
| `assist` | update 時は yes | yes | `--no-check` 以外 yes | no |
| `import-ics`, `sync-ics` | `.ics` | yes | generated item validation | no |
| `tui` | yes | no | yes | dashboard 固有 |
| `fzf` | yes | `done` と `delete` action | yes | yes |
| `timer` | yes | `start` と `stop` が 1 item を更新 | yes | summary filter |
| `stats` | yes | no | yes | yes |
| `git-hook` | no | Git hook のみ | no | no |
| `completion` | no | 任意の script output | no | no |
| `serve` | yes | API/UI 経由で yes | yes | URL/API filter |

### 2.x format compatibility note

life.txt の detail は file 内では `key:value` です。`key=value` は `assist`
などの helper input でのみ受け付けます。行末の `\` は次の物理行と結合され、
`check`、`filter`、`agenda`、converter などすべての読み取り系 command で
同じ logical-line parser により扱われます。

### 2.y Cross-file input set

1 回の command で読み込まれたファイル群は、ID check と reference 解決では 1 つの logical input set として扱われます。`parent:`、`ref:`、`depends_on:`、`blocks:`、`related:` は、同時に読み込まれた任意のファイル内の ID を参照できます。cross-file reference を解決したい場合は、関連ファイルをすべて path / glob / config paths で渡してください。

## 2.7 省略記法

よく使う操作には短い書き方があります。CLI、TUI、Web UI で共有されているため、
同じ記法はどこでも同じ意味になります。

### キャプチャ記号

`quick`、TUI の `/add`、Web のクイック追加欄は、タイトル中の 4 つの記号を展開します。

| 記号 | 展開結果 | 例 |
| --- | --- | --- |
| `@NAME` | `project:NAME` | `@home` |
| `#NAME` | `tag:NAME` | `#errand` |
| `!VALUE` | `priority:VALUE` | `!high` |
| `^DATE` | `due:DATE` | `^tomorrow` |

```sh
lifetxt q "Buy milk @home #errand !high ^tomorrow"
# [ ] T "Buy milk" project:home tag:errand priority:high due:2026-07-20 id:task_...
```

空白で区切られた単語全体のみが対象なので、`Mail a@b.com about it` はアドレスを保持し、
`Compute 10 ^ 2` はキャレットを保持します。
`\@literal` のように backslash を前置すればそのまま残り、`--no-shorthand` で
そのキャプチャだけ展開を無効にできます。
`#tag` は複数指定すると累積し、単一値の key は `--project` などの明示的な flag が優先されます。

記号だけのタイトルはタイトルなしの record を作らずに拒否され、
未知の `^date` は解釈不能な値を書き込まずに明示的に失敗します。

### 相対日付トークン

日付を受け取るすべての箇所（`--due`、`--do`、`--until`、`^` 記号、TUI の `/due`）で
以下のトークンが ISO 日付に解決されます。

| トークン | 意味 |
| --- | --- |
| `today` / `tomorrow` / `yesterday` | そのままの暦日 |
| `monday` 〜 `sunday` | 次に来るその曜日 |
| `next_monday` 〜 `next_sunday` | 翌週のその曜日 |
| `next_week` | 次の月曜日 |
| `+3d` `-1w` `+2m` `+1y` | 日・週・月・年単位の符号付きオフセット |

月単位のオフセットは有効な日に丸められるため、1 月 31 日の `+1m` は 2 月 28 日になります。
トークンは閉じた集合です。安全な箇所では未知の値をそのまま通し、
実際の日付が必要な箇所では拒否します。

### コマンドの短縮名

| 短縮名 | コマンド |
| --- | --- |
| `q` | `quick` |
| `d` | `done` |
| `s` | `state` |
| `a` | `agenda` |
| `f` | `filter` |

TUI の command palette にも 1 文字の別名があります: `/d` `/s` `/a` `/f` `/t` `/e`
`/u` `/n` `/q`。別名の完全一致は fuzzy 順位より優先されるため、
`/d` は必ず `/done` であり `/detail` や `/delete` にはなりません。

---

## 2.8 プレゼンス status

`status` は現在の状態を読み、`state`（別名 `s`）が書き込みます。

```sh
lifetxt s busy                          # 直前の status を閉じて新しい status を開く
lifetxt state focus --title "Deep Work" # タイトルを明示
lifetxt state busy --note "in the lab" --project research
lifetxt state --end                     # 現在の status を閉じる
lifetxt status                          # 現在の status を読む
```

1 回の遷移で 2 つの編集を行います。その人の open な `S` record に `to:` と `[x]` を付け、
`from:` を持つ新しい `[/]` record を追記します。
手作業だとこの「閉じる」を忘れ、現在有効に見える record が 2 つ残ります。

すでに開いている状態と同じ状態に切り替えた場合は何も書き込まずにその旨を表示します。
`lifetxt s busy` を繰り返すと長い busy の区間が切れ端と新 record に分割され、
本当の開始時刻が失われるためです。新しい record を作りたい場合は `--force` を渡します。
`--at YYYY-MM-DDTHH:MM` で過去日時の遷移、`--person` で他人の status を扱えます。
同じ人物の open な record が既に 2 つある場合は、3 つ目を足さずに両方を閉じます。

---

## 2.9 完了時刻

`done` は task を閉じるときに `done:` を追記します。精度は設定できます。

```sh
lifetxt done life.txt t1              # done:2026-07-19
lifetxt done life.txt t1 --now        # done:2026-07-19T14:32
lifetxt done life.txt t1 --date-only  # config が datetime でも日付のみを強制
```

```json
{ "done": { "precision": "datetime" } }
```

`precision` は `date`（既定）または `datetime` を受け付け、それ以外は明示的に失敗します。
flag は config より優先されます。
habit（`H`）の完了ログはどの設定でも日付のみです。ログは 1 暦日 1 件であり、
時刻を入れると同日重複の検出が壊れるためです。

format 仕様では `done:` は元から日付または日時を許容しているため、
この設定を変えても file format は変わりません。

---

## 2.10 start と stop

`start` と `stop` は作業セッションの前後に必要な 3 つの編集をまとめます。

```sh
lifetxt start life.txt t1     # task を [/] に、timer 開始、presence を busy に
lifetxt stop                  # timer 停止して elapsed: を書き、presence を閉じる
lifetxt stop --done           # さらに task を完了して done: を書く
```

`start` は `--state` で `busy` 以外を指定でき、`--no-timer` / `--no-presence` で
どちらかを省略できます。`stop` は実行中の timer から file と item を読むため引数不要です。
どちらも `--dry-run` に対応します。

timer は `lifetxt timer` と共有され同時に 1 つだけなので、
`start` は 2 つ目の開始を拒否し、実行中の task 名を表示します。

---

## 2.11 外部ファイルとディレクトリ

`file:` と `dir:` は item をディスク上の対象と関連付けます。
path は forward slash で保存され、shell の作業ディレクトリではなく
**life.txt file** を基準に解決されるため、どこから実行しても同じ結果になります。

```sh
lifetxt files life.txt                 # 全 attachment と状態を一覧
lifetxt files life.txt --update        # #sha256= hash を記録・更新
lifetxt files life.txt --check         # 欠落や変更があれば exit 1
lifetxt files life.txt --problems      # 対応が必要なものだけ表示
lifetxt files life.txt --format json   # 機械可読出力
```

| status | 意味 |
| --- | --- |
| `ok` | 存在し、記録された hash と一致 |
| `unhashed` | 存在するが hash 未記録 |
| `changed` | 存在するが内容が hash と異なる |
| `missing` | その path に何もない |
| `wrong_type` | `file:` がディレクトリ、または `dir:` が file を指している |
| `error` | 値を解析・読み取りできない |

`--update` は同時に path を正規化するため、Windows 形式の `.\docs\spec.md` は
`./docs/spec.md` になります。
存在しない対象には誤解を招く hash を付けず、path のみを残します。

`check` は attachment の診断を含みます。
存在確認と移植性の検査は軽いため既定で行い、
hash 検証は参照先 file を読みディレクトリを走査するため任意です。

```sh
lifetxt check life.txt                  # W401 欠落、W403 種別違い、W404 移植性
lifetxt check life.txt --verify-files   # W402 内容変更を追加
lifetxt check life.txt --no-files       # attachment の検査を省略
lifetxt check life.txt --category files # attachment の診断のみ
```

ディレクトリの hash は version control や build のディレクトリを除外します。
設定は次のとおりです。

```json
{
  "attachments": {
    "ignore": [".git", "node_modules", "__pycache__"],
    "max_files": 2000,
    "max_bytes": 209715200
  }
}
```

上限は `dir:` が巨大な場所を指したときに、固まらず明示的に失敗するためのものです。

---

## 3. `check`

life.txt の構文と意味的なルールを検査します。

```sh
python -m lifetxt check [path ...] [--format text|json] [--warnings-as-errors]
python -m lifetxt check life.txt --severity warning --category reference
python -m lifetxt check life.txt --code E010,W213 --format json
```

| Option | 意味 |
|---|---|
| `path ...` | 入力ファイル。`-` なら標準入力 |
| `--format text` | 人間向けの診断を表示 |
| `--format json` | 診断を JSON で表示 |
| `--warnings-as-errors` | warning がある場合も非ゼロ終了 |
| `--severity error|warning` | severity で絞り込み。複数回指定または comma-separated |
| `--code CODE` | `E010` や `W213` などの診断 code で絞り込み。複数回指定または comma-separated |
| `--category CATEGORY` | 診断 category で絞り込み。複数回指定または comma-separated |

診断 filter は出力と終了コードの両方に適用されます。たとえば
`--category reference` は reference category に一致した診断だけで終了コードを決め、
無関係な syntax や style の診断は対象外にします。

Category:

| Category | 主な診断 |
|---|---|
| `syntax` | status、type、title、detail syntax などの parser error |
| `schema` | core status/type value の不正 |
| `style` | key style と custom-key recommendation |
| `time` | date/time value format と range warning |
| `status` | presence/status item rule |
| `message` | message item sender/recipient/notification rule |
| `id` | duplicate ID と unsafe ID-like value |
| `reference` | missing/self/cyclic/ambiguous reference |
| `recurrence` | `repeat:`、`RRULE:`、`interval:`、`count:` recommendation |
| `workflow` | status/detail workflow と dependency-state recommendation |
| `semantic` | 上記に含まれない semantic diagnostic |

例:

```sh
python -m lifetxt check life.txt
python -m lifetxt check life.txt --warnings-as-errors
python -m lifetxt check life.txt --format json
python -m lifetxt check life.txt --category id,reference
```

### 3.1 `ids`

item ID を監査します。既定ではファイルを変更しません。`--assign` を指定した場合だけ、ID がない item に ID を追加できます。

```sh
python -m lifetxt ids [path ...] [--only all|present|missing|duplicates]
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt。`-` なら標準入力 |
| `--key KEY` | 監査する detail key。省略時は config の `ids.key`、`api.id_key`、または `id` |
| `--only all` | summary、duplicate IDs、missing IDs を表示 |
| `--only present` | 存在する ID 一覧を表示 |
| `--only missing` | ID がない item だけ表示 |
| `--only duplicates` | 重複 ID だけ表示 |
| `--format text|json|jsonl` | 出力形式 |
| `--pretty` | JSON を整形して出力 |
| `--assign` | ID がない item へ ID を付与 |
| `--dry-run` | ファイルを書き換えず予定だけ表示 |
| `--backup` | `--assign` で変更前に `FILE.bak` を作成 |
| `--prefix PREFIX` | `--assign` で使う ID prefix。省略時は type 別 config prefix |

例:

```sh
python -m lifetxt ids life.txt
python -m lifetxt ids life.txt archive.life.txt --only duplicates
python -m lifetxt ids life.txt --only missing --format json --pretty
python -m lifetxt ids life.txt --assign --dry-run
python -m lifetxt ids life.txt --assign --backup
python -m lifetxt ids "projects/**/*.life.txt" --assign --prefix item --dry-run
```

### 3.2 `links`

`parent:`、`ref:`、`depends_on:`、`blocks:`、`related:` など、item ID を指す関係を表示します。

```sh
python -m lifetxt links [path ...]
python -m lifetxt links life.txt --id task_report --direction incoming
python -m lifetxt links life.txt --id task_report --direction outgoing --format json --pretty
python -m lifetxt links life.txt --relation depends_on --relation blocks
python -m lifetxt links life.txt --chain task_report
python -m lifetxt links life.txt --chain task_report --format json --pretty
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt。`-` なら標準入力 |
| `--id ID` | この ID に接続する link だけ表示 |
| `--chain ID` | この ID の dependency blocker chain を表示 |
| `--direction incoming|outgoing|both` | `--id` 使用時の向き。既定値は `both` |
| `--relation RELATION` | `depends_on` などの relation key で絞り込み。複数回指定または comma-separated |
| `--key KEY` | ID として扱う detail key。省略時は config の `ids.key`、`api.id_key`、または `id` |
| `--format text|json|jsonl|mermaid|dot` | 出力形式。`--chain` は `text`、`json`、`jsonl` に対応 |
| `--pretty` | JSON を整形して出力 |

`check` は存在しない参照 (`W215`)、自己参照 (`W216`)、`parent:` cycle (`W217`)、曖昧な参照 (`W218`)、完了済み item の `depends_on:` prerequisite がまだ open な場合 (`W224`) も報告します。

依存関係の動作:

- `depends_on:ID` は `ID` が open の間、現在の item を block します。
- `blocks:ID` は現在の item が open の間、`ID` を block する独立した主張です。
- `health` は block されている open item を `W305` として報告します。
- `links --chain ID` と `deps --root ID` は同じ blocker chain を terminal 向け tree として表示します。
  direct `depends_on:` blocker と inverse `blocks:` blocker の両方を含めます。

### 3.3 `sources`

parse された item の source ownership を表示します。手書きファイル、generated calendar
file、archive file を同時に読むとき、どの item がどのファイル由来か確認するために使います。

```sh
python -m lifetxt sources [path ...]
python -m lifetxt sources "projects/**/*.life.txt" --format json --pretty
python -m lifetxt sources life.txt archive.life.txt --missing-id
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt、directory、glob、または標準入力の `-` |
| `--key KEY` | item ID として表示する detail key。省略時は config の `ids.key`、`api.id_key`、または `id` |
| `--missing-id` | 選択した ID key がない item だけ表示 |
| `--format text|json|jsonl` | 出力形式 |
| `--pretty` | JSON を整形して出力 |

report には source path、line range、選択 ID、parent ID、type、status、title、
indentation level、detail count が含まれます。同じ論理入力集合に対する duplicate ID
と reference check も実行し、warning は stderr に出力します。

## 4. 変換と rendering

### 4.1 `to-json`

life.txt を JSON 配列へ変換します。

```sh
python -m lifetxt to-json [path ...] [-o output.json] [--pretty] [filter options]
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt。`-` なら標準入力 |
| `-o`, `--output` | 出力ファイル。省略時は標準出力 |
| `--pretty` | JSON を整形して出力 |
| `--occurrences` | 保存済み item ではなく、計算された agenda occurrence record を出力 |
| `filter options` | `filter` と同じ item filter |

ファイル由来の入力では、各 JSON object に `_source_file` と `_source_line` が含まれます。複数行 record では `_source_end_line` も含まれます。これらは tool 用 metadata であり、`from-json` では life.txt の detail key として扱われません。

`--occurrences` を指定すると、`to-json` は保存済み source item ではなく
計算済み agenda record を出力します。この mode では `--after` と `--before` が
両方必要です。範囲内の対応済み `repeat:` / `RRULE:` を展開し、`agenda` と同じ
filter を適用します。生成された record には、可能な場合 `generated: true`、
`source_id`、`occurrence_start`、`occurrence_end`、`occurrence_index`、
`repeat_rule` が含まれます。

### 4.2 `to-jsonl`

life.txt を JSONL へ変換します。

```sh
python -m lifetxt to-jsonl [path ...] [-o output.jsonl] [--occurrences] [filter options]
```

JSONL の各行は `to-json` と同じ shape で、ファイル由来の入力では `_source_file` と line metadata を含みます。
`--occurrences` 時は各行が 1 つの計算済み agenda occurrence record になり、
`--after` と `--before` が必要です。

### 4.3 `from-json`

JSON item、JSON item 配列、または `{ "items": [...] }` を life.txt に変換します。

```sh
python -m lifetxt from-json [path ...] [-o life.txt]
```

`--canonical` を指定すると、JSON の `indent` から推論できる階層を明示的な `parent:` に変換し、unindented な life.txt を出力します。

### 4.4 `from-jsonl`

JSONL を life.txt に変換します。

```sh
python -m lifetxt from-jsonl [path ...] [-o life.txt]
```

`from-jsonl` も `from-json` と同じ `--canonical` option を受け付けます。

### 4.5 `to-csv`

life.txt を CSV に変換します。CSV は `status`、`type`、`title` と、選択された item に含まれる detail key の列を持ちます。同じ detail key の複数値はセル内 JSON 配列として保存します。複数行の `body:` は quoted CSV cell として保存します。

```sh
python -m lifetxt to-csv [path ...] [-o output.csv] [--occurrences] [filter options]
python -m lifetxt to-csv life.txt --type journal --project research -o journal.csv
```

`--occurrences` を指定すると、`to-csv` は安定した列 schema の agenda
occurrence CSV を出力します。列は `when`、`key`、`line`、`source_id`、
`occurrence_start`、`occurrence_end`、`occurrence_index`、`repeat_rule`、
`status`、`type`、`title`、`blocked`、`blocked_by`、`details`、`text` です。
この mode でも `--after` と `--before` が両方必要です。

### 4.6 `from-csv`

CSV を life.txt に戻します。CSV には `status`、`type`、`title` 列が必要です。それ以外の非空列は detail key として扱います。セルが JSON 配列の場合は、同じ key の複数値として読み込みます。

```sh
python -m lifetxt from-csv [path ...] [-o life.txt]
```

`from-csv` も `--canonical` を受け付けます。

### 4.7 `demo`

有効な demo life.txt を生成します。Web UI demo、screenshot、CLI example、smoke test、空のローカル環境の初期データ作成に使えます。`--count` は item record 数です。`J` record の body continuation がある場合、物理行数は指定件数より多くなることがあります。

```sh
python -m lifetxt demo
python -m lifetxt demo --count 50 --date 2026-07-12 -o demo.life.txt
python -m lifetxt demo --count 20 --date 2026-07-12T09:30 --types T,E,S,M,J
python -m lifetxt demo --count 10 --date 2026-07-13 -o demo.life.txt --append
```

| Option | 意味 |
|---|---|
| `-n`, `--count N` | 生成する item record 数。既定値は 30 |
| `--date VALUE` | 基準 date/datetime。省略時は現在日時 |
| `--types VALUES` | 生成 type を制限。comma-separated または複数回指定 |
| `--seed N` | 決定的な variation seed。既定値は 1 |
| `--project NAME` | 既定の `project:`。既定値は `demo` |
| `--person NAME` | status、message、assignee、attendee、owner で使う person 名。複数回指定可能 |
| `--start-index N` | demo ID の開始番号。省略時は 1、append 時は既存 demo ID の次番号 |
| `-o`, `--output FILE` | stdout ではなく FILE に出力 |
| `--append` | `--output` に追記。`--output` が必須 |
| `--no-check` | 生成 record の validation を省略 |

既定では、出力前に生成 record を validation します。既存 demo file へ追記する場合は `demo_*_NNN` ID を走査し、`--start-index` が未指定なら次の番号から生成します。

### 4.8 `markdown`

選択した field の safe Markdown subset を描画します。この command はファイルを変更しません。raw の title / body / note を読み取り、HTML、plain text、JSON、JSONL として出力します。

```sh
python -m lifetxt markdown [path ...] [--field body] [--format html|text|json|jsonl]
python -m lifetxt markdown life.txt --field all --format json --pretty
python -m lifetxt markdown examples/markdown_life.txt --type journal -o body.html
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt file、directory、glob、または stdin 用の `-` |
| `--field title|body|note|all` | 描画する field。複数回指定または comma-separated。既定は `body` |
| `--format html|text|json|jsonl` | 出力形式。既定は `html` |
| `-o`, `--output` | 出力 file。省略時は stdout |
| `--pretty` | JSON を整形して出力 |
| `filter options` | `filter` と同じ item filter |

JSON / JSONL record には `source`、`line`、`type`、`status`、`title`、
`field`、`index`、`raw`、`html`、`text` が含まれます。Markdown source 内の
raw HTML は escape され、`javascript:` のような unsafe link は link として描画しません。

### 4.9 export filter option

`to-json`、`to-jsonl`、`to-csv`、`markdown` は出力前に item を絞り込めます。

| Option | 意味 |
|---|---|
| `--open` | 未完了 workflow item のみ。対象は `[ ]`、`[/]`、`[>]`、`[?]` |
| `--status VALUE` | status または alias で絞り込み。複数回指定または comma-separated |
| `--type VALUE` | type または alias で絞り込み。複数回指定または comma-separated |
| `--project VALUE` | `project:` で絞り込み。複数回指定または comma-separated |
| `--tag VALUE` | `tag:` で絞り込み。複数回指定または comma-separated |
| `--tag-all VALUE` | 指定した `tag:` をすべて持つ item のみ |
| `--exclude-tag VALUE` | 指定した `tag:` を持つ item を除外 |
| `--user VALUE` | `user/person/owner/assignee/attendee/sender/recipient` を横断して絞り込み |
| `--team VALUE` | `team:` / `group:` または config の team membership で絞り込み |
| `--person VALUE` | `person:` で絞り込み。`S` で `person:` がない場合は `self` |
| `--owner VALUE` | `owner:` で絞り込み。複数回指定または comma-separated |
| `--assignee VALUE` | `assignee:` で絞り込み。複数回指定または comma-separated |
| `--attendee VALUE` | `attendee:` で絞り込み。複数回指定または comma-separated |
| `--detail FILTER` | detail key または `key=value` で絞り込み。複数指定は AND |
| `--text TEXT` | title、元行、detail 値に対する大文字小文字を区別しない部分一致 |
| `--after VALUE` | この時刻以降に関連する item のみ |
| `--before VALUE` | この時刻以前に関連する item のみ |
| `--occurrences` | `to-json`、`to-jsonl`、`to-csv` で、保存済み item ではなく bounded agenda occurrence を出力 |

`--after` と `--before` は `now`、`YYYY-MM-DD`、`YYYY-MM-DDTHH:MM`、
`YYYY-MM-DDTHH:MM:SS`、`YYYY-MM-DDTHH:MM:SS.5`、
`YYYY-MM-DDTHH:MM+09:00`、`YYYY-MM-DDTHH:MM:SS.25+09:00` などを受け付けます。
時刻判定は `agenda` と同じルールを使います。
`on:` のない `at:HH:MM` は日付アンカーを持たないため、片側条件の `--after` /
`--before` では一致対象にしません。

例:

```sh
python -m lifetxt to-json life.txt --open --type task --pretty
python -m lifetxt to-jsonl work.life.txt home.life.txt --project research
python -m lifetxt to-json life.txt --assignee alice --pretty
python -m lifetxt to-json "projects/**/*.life.txt" --team research --tag-all urgent,review
python -m lifetxt to-json life.txt --after now --type event -o future_events.json
python -m lifetxt to-json life.txt --occurrences --after 2026-06-01 --before 2026-06-30 --pretty
python -m lifetxt to-csv life.txt --occurrences --after 2026-06-01 --before 2026-06-30 -o occurrences.csv
```

## 5. iCalendar import / sync

### 5.1 `import-ics`

Google Calendar の export などで得られる iCalendar `.ics` ファイルを、
life.txt の event item に変換します。

```sh
python -m lifetxt import-ics [path ...] [-o life.txt] [--append] [--project PROJECT] [--tag TAG]
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 `.ics` ファイル。`-` なら標準入力 |
| `-o`, `--output` | 出力ファイル。省略時は標準出力 |
| `--append` | `--output` を上書きせず追記 |
| `--project PROJECT` | すべての取り込み予定に `project:PROJECT` を追加 |
| `--tag TAG` | すべての取り込み予定に `tag:TAG` を追加。複数回指定可能 |

変換対応:

| iCalendar field | life.txt output |
|---|---|
| `VEVENT` | `E` item |
| `SUMMARY` | title |
| `UID` | `id:` |
| `DTSTART` / `DTEND` | 時刻付き予定では `from:` / `to:` |
| `DTSTART;VALUE=DATE` | 終日予定では `on:` |
| `LOCATION` | `loc:` |
| `DESCRIPTION` | `note:` |
| `URL` | `url:` |
| `ORGANIZER` | `owner:` |
| `ATTENDEE` | 複数の `attendee:` |
| `CATEGORIES` | 複数の `tag:` |
| `RRULE` | `repeat:RRULE:...` |
| `STATUS:CANCELLED` | `[-]` と `reason:canceled` |
| `STATUS:TENTATIVE` | `[?]` |

注意:

- `VEVENT` component のみを取り込みます。
- Google Calendar の終日 `DTEND` は排他的です。複数日の終日予定は複数の
  `on:` に変換します。
- `TZID` 付きのローカル時刻は書かれている壁時計時刻をそのまま使います。
  UTC の `Z` 付き日時は、実行環境のローカルタイムゾーンへ変換して
  `YYYY-MM-DDTHH:MM` で出力します。
- `RRULE` は `repeat:RRULE:...` として保持します。対応している subset は
  import 時ではなく、`agenda` と time filter で後から展開します。

例:

```sh
python -m lifetxt import-ics google_calendar.ics
python -m lifetxt import-ics google_calendar.ics -o imported_events.life.txt
python -m lifetxt import-ics google_calendar.ics -o life.txt --append --tag google
python -m lifetxt import-ics work.ics personal.ics --project calendar
```

出力例:

```txt
[ ] E "Research Meeting" id:event-1@example.com source:ics uid:event-1@example.com from:2026-06-08T13:00 to:2026-06-08T14:30 loc:"Meeting Room A" owner:"Prof. Smith" attendee:Alice tag:google
```

### 5.2 `sync-ics`

1 つ以上の iCalendar URL を取得し、生成用 life.txt ファイルを再生成します。
定期同期ではこの方式を推奨します。出力ファイルを上書きするため、実行するたびに
同じ予定が重複追記されません。

```sh
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
```

| Option | 意味 |
|---|---|
| `--url URL` | 取得する iCalendar URL。複数回指定可能 |
| `--url-env ENVVAR` | iCalendar URL を入れた環境変数。複数回指定可能 |
| `-o`, `--output` | 生成する life.txt 出力。省略時は標準出力 |
| `--cache-dir DIR` | 取得した生の `.ics` snapshot を保存する directory |
| `--dry-run` | 取得して生成結果を表示するが、出力ファイルと cache は書かない |
| `--project PROJECT` | すべての同期予定に `project:PROJECT` を追加 |
| `--tag TAG` | すべての同期予定に `tag:TAG` を追加。複数回指定可能 |
| `--timeout SECONDS` | 取得 timeout。既定値は 30 |
| `--user-agent VALUE` | HTTP User-Agent header |

秘密 iCalendar URL は、shell history、script、document に残さないために
`--url-env` で渡すことを推奨します。

PowerShell 例:

```powershell
$env:LIFETXT_GOOGLE_CAL_ICS = "https://calendar.google.com/calendar/ical/..."
New-Item -ItemType Directory -Force .generated, .cache/lifetxt
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
python -m lifetxt check life.txt .generated/google_calendar.life.txt
python -m lifetxt agenda life.txt .generated/google_calendar.life.txt --around now --window 1d
```

定期同期する場合は、同じ内容を `.ps1` にして Windows Task Scheduler で実行します。
手書きの item はメインの `life.txt` に残し、ICS 由来の item は
`.generated/*.life.txt` に分離してください。`agenda`、`filter`、`to-json`、
`check` などは両方のファイルを同時に渡せます。

Current additions:

- `import-ics --preset markdown|todoist|github` can import Markdown task lists,
  Todoist CSV exports, and GitHub Issues JSON exports as `T` items.
- ICS-derived records now include `source:ics` and `uid:` metadata.
- `sync-ics --merge-existing --soft-delete-missing` preserves comments in the
  generated output, updates matching UID-backed records, and marks missing
  `source:ics` events as `[-] reason:missing_from_feed`.

## 6. `filter`

解析済みの life.txt item を絞り込み、結果を life.txt、JSON、JSONL で出力します。
条件に合う部分集合を別の `life.txt` として保存したい場合に使います。

```sh
python -m lifetxt filter [path ...] [filter options] [--format life|json|jsonl] [-o output]
```

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt。`-` なら標準入力 |
| `--format life` | 一致した life.txt 行を出力。既定値 |
| `--format json` | JSON 配列で出力 |
| `--format jsonl` | JSONL で出力 |
| `--format table` | STATUS/TYPE/TITLE/PROJECT の table を出力 (`--width` 80 未満では compact な1行形式) |
| `--width N` | `--format table` の列幅 (文字数)。既定値 `0` は terminal width を自動検出 |
| `--limit N` | 出力する item を最大 N 件に制限 (`0` は無制限) |
| `-o`, `--output` | 出力ファイル。省略時は標準出力 |
| `--pretty` | JSON を整形して出力 |
| `--canonical` | 元行ではなく、明示的な `parent:` を使う unindented life.txt 行を再生成 |

filter option は 4.8 の export filter option と同じです。
`--format life` では、一致した item の元行を既定で保持します。
引用や空白を正規化したい場合は `--canonical` を使います。
階層も正規化したい場合は `--canonical` を使います。出力では indentation を使わず、推論済みまたは明示済みの `parent:` を detail として書きます。
terminal で素早く確認したい場合は `--format table` が便利です。`agenda` や
`stats` の table と同様、狭い terminal (または `--width 80` 未満) では
自動的に compact な1行形式に切り替わります。

例:

```sh
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --open --type task --canonical -o canonical_tasks.life.txt
python -m lifetxt filter life.txt --assignee alice -o alice_items.life.txt
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
python -m lifetxt filter work.life.txt home.life.txt --project research --format json --pretty
```

## 7. `status`

`person:` ごとの最新 `S` status / presence record を表示します。

```sh
python -m lifetxt status [path ...] [--format text|json|jsonl] [--person PERSON] [--active] [--pretty]
```

選択ルール:

- type `S` の item だけを対象にします。
- `person:` ごとに group 化します。
- `person:` がない場合は `self` として扱います。
- `from:` が最も新しい item を最新として選びます。
- `--active` を指定すると、`to:` を持つ終了済み log は除外します。

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt。`-` なら標準入力 |
| `--format text` | 表で表示 |
| `--format json` | JSON 配列で表示 |
| `--format jsonl` | JSONL で表示 |
| `--person PERSON` | 特定 person のみ表示 |
| `--active` | `to:` のない現在有効な status item のみ対象 |
| `--pretty` | JSON を整形して出力 |

例:

```sh
python -m lifetxt status life.txt
python -m lifetxt status life.txt --active
python -m lifetxt status life.txt --person self
python -m lifetxt status life.txt --format json --pretty
```

## 8. `notify`

type `M` の通知対象を 1 回表示するか、`--watch` で常駐 polling します。

```sh
python -m lifetxt notify [path ...] [--recipient PERSON] [--watch]
python -m lifetxt notify life.txt --recipient self --email --email-to me@example.com --dry-run
python -m lifetxt notify life.txt --watch --once --state-file .generated/notifications.json
python -m lifetxt notify life.txt --watch --email --email-to me@example.com --interval 60
```

選択ルール:

- type `M` の item だけを対象にします。
- open workflow status (`[ ]`、`[/]`、`[>]`、`[?]`) だけを対象にします。
- `recipient:` が選択 recipient と一致する必要があります。
- `notify_at:` は単一通知時刻として扱います。
- `notify_from:` / `notify_to:` は通知期間として扱います。
- `ack:` がある item は通知済みとして除外します。
- 未来の `snooze_until:` がある item は、その時刻まで抑止します。

| Option | 意味 |
|---|---|
| `path ...` | 入力 life.txt。`-` なら標準入力 |
| `--recipient PERSON` | 通知対象者。省略時は config の `notifications.recipient` または `user.name` |
| `--lookahead VALUE` | 未来方向の通知検出幅。例: `0m`、`5m`、`1h` |
| `--grace VALUE` | 過去方向の取りこぼし許容幅 |
| `--watch` | 終了せず繰り返し polling |
| `--once` | `--watch` と併用し、1 回だけ poll して seen-state を更新して終了 |
| `--interval SECONDS` | `--watch` の polling 秒数 |
| `--desktop` | 対応環境では簡易 desktop 通知も表示 |
| `--email` | 通知対象を plain text email としてまとめて送信 |
| `--email-to ADDRESS[,ADDRESS...]` | email 宛先。省略時は `notifications.email.to` |
| `--email-subject TEXT` | email subject のベース。省略時は `notifications.email.subject` |
| `--smtp-host-env ENVVAR` | SMTP host を格納する環境変数。省略時は `notifications.email.smtp_host_env` または `LIFETXT_SMTP_HOST` |
| `--smtp-user-env ENVVAR` | SMTP username を格納する環境変数。省略時は `notifications.email.smtp_user_env` または `LIFETXT_SMTP_USER` |
| `--smtp-pass-env ENVVAR` | SMTP password を格納する環境変数。省略時は `notifications.email.smtp_pass_env` または `LIFETXT_SMTP_PASS` |
| `--dry-run` | `--email` 時に SMTP 接続せず、送信予定本文を表示 |
| `--state-file PATH` | `--watch` の通知済み ID を保存する JSON file |
| `--no-state` | `--watch` で通知済み状態を保存しない |
| `--format text|json|jsonl` | one-shot mode の出力形式 |
| `--pretty` | JSON を整形して出力 |

例:

```sh
python -m lifetxt notify life.txt --recipient self
python -m lifetxt notify life.txt --recipient self --format json --pretty
python -m lifetxt notify life.txt --watch --interval 30
python -m lifetxt notify life.txt --watch --once --state-file .generated/notifications.json
python -m lifetxt notify life.txt --email --email-to me@example.com --dry-run
```

email 通知は SMTP 認証情報を環境変数から読みます。life.txt 本文や config には
秘密情報を保存せず、必要に応じて `notifications.email.*` で環境変数名だけを
変更してください。

## 9. `agenda`

日時範囲に関連する item を表示します。

```sh
python -m lifetxt agenda [path ...] [range options] [filter options] [output options]
```

範囲判定ルール:

- `from/to` は期間として扱います。
- `on` は終日範囲として扱います。
- `due`、`do`、`at`、`moved_to` は時点または終日範囲として扱います。
- type `S` で `to:` がない item は、`from:` 以降継続中として扱います。
- `at:HH:MM` は `on:` があればその日付と組み合わせ、なければ指定範囲内の各日付と組み合わせます。
- simple `repeat:` の `daily`、`weekly`、`monthly`、`yearly`、`weekdays` は展開します。
- `interval:`、`until:`、`count:` は simple repeat の展開を制限します。
- `repeat:RRULE:...` は dependency-free subset として
  `FREQ=DAILY|WEEKLY|MONTHLY|YEARLY`、`INTERVAL`、`COUNT`、`UNTIL`、
  daily/weekly の `BYDAY` を展開します。
- `on:` のない floating `at:` repeat は、両端がある bounded agenda range の中だけで展開します。

### 9.1 範囲オプション

| Option | 意味 |
|---|---|
| `--from VALUE` | 範囲開始。`now`、`YYYY-MM-DD`、`YYYY-MM-DDTHH:MM` |
| `--to VALUE` | 範囲終了。`now`、`YYYY-MM-DD`、`YYYY-MM-DDTHH:MM` |
| `--after VALUE` | `agenda` では `--from` の alias。filter preset と共有するときに便利 |
| `--before VALUE` | `agenda` では `--to` の alias。filter preset と共有するときに便利 |
| `--around VALUE` | 範囲中心。省略時は `now` |
| `--window VALUE` | `--around` の半幅。省略時は `1h` |

`--from/--to`、`--after/--before`、または `--around` のいずれかを使います。
同じ command で `--from` と `--after`、または `--to` と `--before` は混在できません。
範囲指定がない場合は `--around now --window 1h` と同じ扱いです。

`--window` の duration:

| Form | 意味 |
|---|---|
| `15s` | 15 秒 |
| `30m` | 30 分 |
| `2h` | 2 時間 |
| `1d` | 1 日 |
| `1w` | 1 週間 |
| `1mo` | 1 か月。30 日として近似 |
| `1y` | 1 年。365 日として近似 |
| `30` | 30 分 |

例:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06
python -m lifetxt agenda life.txt --after 2026-06-06 --before 2026-06-06
python -m lifetxt agenda life.txt --from 2026-06-06T13:00 --to 2026-06-06T18:00
python -m lifetxt agenda life.txt --from 2026-06-06T13:00:30.25+09:00 --to 2026-06-06T18:00:00.5+09:00
python -m lifetxt agenda life.txt --around now --window 2h
python -m lifetxt agenda life.txt --around now --window 1w
python -m lifetxt agenda life.txt --from 2026-06-01 --to 2026-06-30 --type habit
```

### 9.2 フィルタオプション

| Option | 意味 |
|---|---|
| `--open` | 未完了 workflow item のみ表示。対象は `[ ]`、`[/]`、`[>]`、`[?]` |
| `--status VALUE` | status または alias で絞り込み。複数回指定または comma-separated |
| `--type VALUE` | type または alias で絞り込み。複数回指定または comma-separated |
| `--project VALUE` | `project:` で絞り込み。複数回指定または comma-separated |
| `--tag VALUE` | `tag:` で絞り込み。複数回指定または comma-separated |
| `--tag-all VALUE` | 指定した `tag:` をすべて持つ item のみ |
| `--exclude-tag VALUE` | 指定した `tag:` を持つ item を除外 |
| `--user VALUE` | user 関連 detail を横断して絞り込み |
| `--team VALUE` | `team:` / `group:` または config の team membership で絞り込み |
| `--person VALUE` | `person:` で絞り込み。複数回指定または comma-separated |
| `--owner VALUE` | `owner:` で絞り込み。複数回指定または comma-separated |
| `--assignee VALUE` | `assignee:` で絞り込み。複数回指定または comma-separated |
| `--attendee VALUE` | `attendee:` で絞り込み。複数回指定または comma-separated |
| `--detail FILTER` | detail key または `key=value` で絞り込み。複数指定は AND |
| `--text TEXT` | title、元行、detail 値に対する大文字小文字を区別しない部分一致 |
| `--blocked [only|hide|all]` | dependency-blocked record を絞り込み。単独の `--blocked` は `--blocked only` と同じ |
| `--unblocked` | `--blocked hide` の後方互換 alias |

例:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --status todo --type task
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --project research --tag urgent
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --assignee alice
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --detail priority=A --text report
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --person alice
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --blocked
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --blocked hide
```

`--detail key` は key の存在を確認します。`--detail key=value` は detail value の完全一致です。
複数の `--detail` は AND 条件です。

### 9.3 出力オプション

| Option | 意味 |
|---|---|
| `--format text` | 表で表示 |
| `--format life` | 一致した元の life.txt item 行を表示 |
| `--format json` | JSON 配列で表示 |
| `--format jsonl` | JSONL で表示 |
| `-o`, `--output` | 出力ファイル。省略時は標準出力 |
| `--pretty` | JSON を整形して出力 |
| `--width N` | text 出力を指定した terminal width 向けに整形 |

agenda の JSON / JSONL record は、open item が open な `depends_on:` または
`blocks:` 関係で block されている場合に `blocked: true` と `blocked_by` 配列を
含めます。repeat から生成された occurrence には、可能な場合 `source_id`、
`occurrence_start`、`occurrence_end`、`occurrence_index`、`repeat_rule` も含めます。
text 出力では短い `blocked` 列で同じ状態を表示します。`--format life` は保存されている元の item 行をそのまま出力します。

例:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --format life
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --format json --pretty
python -m lifetxt agenda life.txt --around now --window 1w --format life -o agenda.life.txt
python -m lifetxt agenda life.txt --around now --window 1d --width 70
```

## 10. `assist`

フラグまたは対話入力で life.txt item を作成・更新します。

```sh
python -m lifetxt assist [options]
```

### 10.1 非対話で作成

```sh
python -m lifetxt assist --type task --title "Write Report" --due 2026-06-12 --project university
python -m lifetxt assist --type status --title "Working" --from 2026-06-06T14:00 --state busy --person self
python -m lifetxt assist --type message --title "Review Slides" --sender self --recipient alice --notify-at 2026-06-06T09:00
python -m lifetxt assist --type journal --title "Research day" --on 2026-06-23 --body-file notes.md
python -m lifetxt assist --type habit --title "Review" --rrule "FREQ=WEEKLY;BYDAY=MO;COUNT=4"
```

基本オプション:

| Option | 意味 |
|---|---|
| `-s`, `--status` | status または alias。例: `[ ]`、`done`、`note` |
| `-t`, `--type` | type または alias。例: `T`、`task`、`status` |
| `--title` | item title |
| `-d`, `--detail` | `key=value` または `key:value`。複数回指定可能 |
| `-o`, `--output` | 生成行をファイルに追記 |
| `--append` | 生成行をファイルに追記 |
| `--no-check` | 生成行の validation を省略 |
| `--body-file FILE` | UTF-8 text file から複数行 `body:` を読み込む |
| `--body-stdin` | 標準入力から複数行 `body:` を読み込む |
| `--rrule VALUE` | `repeat:RRULE:...` を設定する。`RRULE:` prefix は省略可能 |

known detail key には直接フラグもあります。各フラグは複数回指定できます。

```txt
--id --parent --ref --depends_on --blocks --related --created --updated --done --due --do --from --to
--state --user --person --owner --assignee --attendee --sender --recipient --team --group --service --channel
--visibility --notify_at --notify_from --notify_to --ack --snooze_until --on --at --repeat
--interval --until --count
--project --context --loc --priority --est --elapsed --tag --note --body --mood --weather --url
--reason --moved_to
```

underscore を含む detail key には hyphen alias も使えます。例:
`--notify-at`、`--notify-from`、`--snooze-until`。

### 10.2 対話で作成

```sh
python -m lifetxt assist --interactive
python -m lifetxt assist --interactive --append life.txt
```

対話ヘルプ:

| Input | 意味 |
|---|---|
| `?` | 現在の prompt に応じた help |
| `?type` | type help |
| `?status` | status help |
| `?detail` | 推奨 detail key |
| `?all` | known detail key 全体 |
| `?due` | detail key 個別 help |
| `body<<` | 複数行 `body:` 入力を開始。`.` だけの行で終了 |

対応 terminal では、Tab で type、status、detail-key 候補を補完できます。
Up/Down で入力履歴を呼び出せます。`--no-completion` で補完と line editing を無効化できます。

### 10.3 既存 item の更新

行番号または完全一致の `id:` で item を選択して更新します。

```sh
python -m lifetxt assist --update life.txt --line 3 --title "New Title"
python -m lifetxt assist --update life.txt --match-id task_001 --status done --done 2026-06-06
python -m lifetxt assist --update life.txt --match-id task_001 --add-detail tag=important
python -m lifetxt assist --update life.txt --match-id task_001 --remove-detail tag
python -m lifetxt assist --update life.txt --match-id task_001 --output updated_life.txt
```

更新オプション:

| Option | 意味 |
|---|---|
| `--update FILE` | 既存 life.txt を読み込んで更新 |
| `--line N` | `N` 行目の item を選択 |
| `--match-id ID` | `id:` が `ID` と完全一致する item を選択 |
| `--add-detail key=value` | detail value を追加 |
| `--remove-detail key` | 指定 key の value をすべて削除 |
| `--output FILE` | 更新後のファイル全体を別ファイルに書き出し |

`--output` がない場合、update mode は入力ファイルへ書き戻します。

## 11. `serve`

任意機能の FastAPI REST API とブラウザGUIを起動します。

先にWeb依存を入れます。

```sh
pip install -r requirements-web.txt
```

server を起動します。

```sh
python -m lifetxt serve life.txt --host 127.0.0.1 --port 8000
LIFETXT_API_TOKEN=change-me python -m lifetxt serve life.txt --host 0.0.0.0 --token-env LIFETXT_API_TOKEN
```

ブラウザで `http://127.0.0.1:8000/` を開きます。

| Option | 意味 |
|---|---|
| `path ...` | 読み込む life.txt ファイル。省略時は `life.txt` |
| `--write-file FILE` | 作成、更新、削除に使うファイル |
| `--host HOST` | bind host。既定値は `127.0.0.1` |
| `--port PORT` | bind port。既定値は `8000` |
| `--read-only` | `/api/check-line` 以外の write endpoint を無効化。公開用・常時表示用に便利 |
| `--token-env ENVVAR` | API bearer token を環境変数から読み込む |
| `--insecure-public` | token なしの非 loopback writable server を明示的に許可する |
| `--mcp` | FastAPI HTTP server の代わりに stdio MCP server を起動 |

`--host 0.0.0.0` など非 loopback に bind する writable server は、
`--token-env ENVVAR`、`--read-only`、または明示的な `--insecure-public`
のいずれかが必要です。

REST API は `/api/items`、`/api/agenda`、`/api/status`、`/api/health` を提供します。
詳細は [web.md](./web.md) を参照してください。

Browser GUI には header Workspace、中央の record modal、URL/config 由来の
view preset、Review filter と Markdown copy、設定可能な Dashboard card と
theme token、`Ctrl+K` fuzzy Command Palette、recently opened records、
undo history、browser notifications、Graph、display mode、kiosk mode があります。
複数 file を読み込む場合は `path ...` と `--write-file FILE` を併用すると、
generated/read-only file を表示しつつ、編集は hand-maintained file だけに限定できます。

### 11.1 `mcp`

MCP-compatible AI client から life.txt を操作するための JSON-RPC stdio server を起動します。
core package だけで動作し、FastAPI / uvicorn は不要です。

```sh
python -m lifetxt mcp life.txt
python -m lifetxt mcp life.txt .generated/google_calendar.life.txt --write-file life.txt
python -m lifetxt serve life.txt --mcp
python -m lifetxt mcp "projects/**/*.life.txt" --write-file life.txt --read-only
```

主な tool は `list_items`、`get_item`、`check_line`、`parse_item`、
`create_item`、`update_item`、`mark_done`、`complete_item`、`delete_item`、`get_agenda`、
`get_review`(`review --format json` / `GET /api/review` と同形の週次・月次
review report)、`get_graph`、`get_blockers`、`list_links`、`list_status`、
`list_notifications`、および type `M` message 操作です。`complete_item` は
repeat 付き task のインスタンスを完了し次回インスタンスを生成します（repeat
が無ければ `mark_done` と同じ動作）。複数 file を読み込んだ場合、read tool は全 file を走査し、
write tool は `--write-file` のみを変更します。`--read-only` を付けると write tool を無効化します。

## 12. `config`

外部 JSON config を作成または表示します。

```sh
python -m lifetxt config init -o .lifetxt.json
python -m lifetxt --config .lifetxt.json config show
```

| Option | 意味 |
|---|---|
| `config init -o FILE` | starter config を FILE に作成。省略時は `.lifetxt.json` |
| `config init --force` | 既存 config file を上書き |
| `config show` | 読み込まれた config を JSON として表示 |

主な config key:

| Key | 意味 |
|---|---|
| `paths` | life.txt 読み込み系 command の default input files |
| `write_file` | `serve` の default writable file |
| `user.name` | 自身の標準ユーザ名 |
| `users`, `teams`, `tags` | user alias、team membership、tag alias/group |
| `message.default_sender` | type `M` 作成時の default `sender:` |
| `timer.state_file` | `timer` の常駐状態を保存する JSON ファイル |
| `attachments.*` | `file:` / `dir:` の設定。`ignore`、`max_files`、`max_bytes` |
| `tui.*` | TUI の既定値。`theme`、`keymap`、`glyphs`、`limit`、`agenda_window`、`session`、`session_file` |
| `notifications.*` | `notify` と Web 通知の既定値 |
| `ids.auto`, `ids.key`, `ids.prefixes` | 自動IDと ID key の設定 |
| `api.id_key` | Web API / id-based operation が使う ID key |
| `web.*` | `serve` と Web UI の既定値。`web.theme.*` と `web.dashboard.*` で見た目と Dashboard を調整 |
| `sync_ics.*` | `sync-ics` の default source / output / cache |

top-level `generated_paths` または `sync_ics.generated_paths` に含まれる file は、
通常の変更系 command (`assist`, `done`, `archive`, `assign`, `tag`, `batch`,
`migrate`, `encrypt`, `decrypt`) では generated/read-only として扱われ、
変更を拒否します。`sync-ics` は generated file を出力するための例外ですが、
OS 上で read-only の file は拒否します。

### 12.1 設定値の解決順序

同じ設定項目(例: `self` として使う名前や、`quick` で新規項目に付与する
project)は、最大4つのレベルで指定できます。複数レベルで値が指定された場合、
lifetxt は優先度の高い順に次のように解決します。

1. **CLI フラグ** — 実行するコマンドに直接渡すフラグ。
   例: `lifetxt quick "牛乳を買う" --project errands`、
   `lifetxt agenda --person alice`
2. **Config JSON の defaults** — 読み込んだ `.lifetxt.json` の `defaults`
   (および `user`、`message` など関連セクション)の値。
   例: `"defaults": {"person": "self", "timezone": "Asia/Tokyo"}`
3. **`#!` file-level directive** — life.txt file 先頭の directive 行。
   例: `#! self: alice`、`#! project: research`、`#! timezone: UTC`。
   その file 内でのみ有効です。
4. **組み込みの既定値** — 他のどのレベルにも値がない場合に使われる
   ハードコードされた fallback。例: person `"self"`、timezone `"UTC"`。

例: life.txt file 先頭が `#! project: research` でも、
`lifetxt quick "アウトライン作成" --project writing` を実行すると、
CLI フラグが優先されるため item は `writing` に分類されます。
`--project` を省略し、config file に `"defaults": {"project": "misc"}` が
あり file 側に `#! project:` directive が無い場合は `misc` に分類されます。
上位3レベルのいずれにも project の指定が無ければ、その item に project は
付きません。

`lifetxt config init` は config file 書き込み後にこの解決順序を
リマインダーとして表示します。`lifetxt init` は starter life.txt
(`#! self:` / `#! timezone:` / `#! project:` directive 付き)と対応する
`.lifetxt.json` (`defaults.person` / `defaults.timezone` 付き)を同時に
作成するため、新規ユーザーは3つの設定レベルを並べて確認できます。

## 13. CUI 拡張

### 13.1 `tui`

`tui` は未完了 task、現在時刻付近の agenda、active な `S` status を扱う対話的な端末 workspace です。

```sh
python -m lifetxt tui [path ...]
python -m lifetxt tui life.txt --theme dark --limit 15
python -m lifetxt tui life.txt --keymap vim --agenda-window 1d
python -m lifetxt tui life.txt --glyphs ascii
python -m lifetxt tui life.txt --plain > snapshot.txt
```

端末上では `tui` は対話的な workspace を起動します。画面下部に常駐する input bar、
fuzzy 補完付きの slash command palette、入力に追従する live filter、section header 付きの
単一 scroll list、選択行の inspector panel で構成されます。
stdout が TTY でない場合 (pipe や redirect) や `--plain` 指定時は、代わりに plain text の
dashboard snapshot を 1 回出力するため、`python -m lifetxt tui > snapshot.txt` も従来どおり動作します。

#### input bar

既定の `prompt` keymap では input bar が常に focus されています。plain text を入力すると
入力に追従して全 row を fuzzy filter します。substring 一致を scattered subsequence 一致より
高く評価し、一致文字を highlight します。field には重み付けがあり、
title の一致が id の一致より、id の一致が detail 値の一致より上位になります。`Enter` で filter を確定して bar を消去し、
`Esc` で bar を消去した後、さらに押すと有効な filter を解除します。

`/` を入力すると command palette が開きます。row と同じ fuzzy matcher で command を順位付けし、
usage と summary を表示し、`Tab` で選択中の候補を補完します。`Enter` は入力した command を実行し、
名前が完全一致でない場合は選択中の候補を実行するため、`/do` + `Enter` で `/done` が動きます。
未知の command は最も近い名前を提示して明示的に失敗します。

command 名の後に空白を入れると、palette はその command の**引数の値**の一覧に
切り替わり、`Tab` はそちらを補完します:

```txt
/state <TAB>     available busy focus meeting away commuting …
/timer <TAB>     start stop status cancel
/due tomo<TAB>   tomorrow
/project re<TAB> （ファイル内の "re" で始まる project）
/goto <TAB>      （ファイル内のレコード id）
```

選択肢が固定の command（`/view`、`/sort`、`/status`、`/mark`、`/timer`、
`/export`、`/theme`）は自身の語を提示します。その他は開いているファイルを読むため、
`/project`、`/context`、`/tag`、`/goto`、`/assign`、`/now`、`/state` は
ファイルに実在する project・context・tag・id・人名を提示します。文書化された
一覧にない独自の presence state も含まれます。`/due` は shorthand が受け付ける
日付語を提示します。`/search` や `/add` のように自由記述を取る command では
何も提示しません。

上下キーで候補を移動し、`Tab` で選択中のものを確定します。ここで得られる候補は
shell completion script・Web UI・MCP の `complete` tool と同一です。

#### command 一覧

**view と filter**

| command | 用途 |
| --- | --- |
| `/help [QUERY]` | 一覧の表示切り替え、または検索 (`/help timer`) |
| `/view all\|tasks\|agenda\|status\|next` | 表示する section を切り替え |
| `/next` | 未完了・blocked でない・someday でない次の行動を priority 順に表示 |
| `/search TEXT` | 全 row を fuzzy filter |
| `/project NAME` | `project:` で filter (値なしで解除) |
| `/context NAME` | `context:` で filter (値なしで解除) |
| `/tag NAME` | `tag:` で filter (先頭の `#` は省略可) |
| `/sort natural\|due\|priority\|title\|status` | 並び順を変更 |
| `/clear` | filter と mark をすべて解除 |
| `/goto ID` | 指定 id の行へ選択を移動 |
| `/mark toggle\|all\|none` | 一括操作用に row を mark |

**編集** — 以下は mark 済み row、mark がなければ選択行に適用されます。

| command | 用途 |
| --- | --- |
| `/done [now]` | task 系の row を完了して `done:` を記録。`now` で時刻も記録 |
| `/state STATE [TITLE]` | 直前の status を閉じて presence を記録。`/state end` で閉じる |
| `/now` | 現在 open な presence status を表示 |
| `/status open\|active\|done\|dropped` | CLI と同じ alias で status を設定 |
| `/set KEY VALUE` | detail を設定。値を省略すると key を削除 |
| `/due DATE` | `today`、`tomorrow`、曜日、`+3d`、`-1w` で `due:` を設定 |
| `/assign USER` | `assignee:` を設定 |
| `/add TITLE` | write file に未完了 task を追記。記号 (`@ # ! ^`) を展開 |
| `/delete yes` | row を削除。`yes` がないと拒否 |
| `/edit` | 選択行を `$EDITOR` で開く |
| `/timer start\|stop\|status\|cancel` | 経過時間を計測し、stop 時に `elapsed:` を書き込む |
| `/undo` | このセッションの直前の書き込みを取り消す |

**出力と表示**

| command | 用途 |
| --- | --- |
| `/export md\|csv\|json [PATH]` | 現在表示中の row を file に書き出す |
| `/stats` | status / type / project 別の内訳を表示切り替え |
| `/detail` | inspector panel の表示切り替え |
| `/reload` | 全 file を即時読み直す |
| `/theme auto\|dark\|light\|mono` | 配色を即時変更 |
| `/limit N` | section ごとの保持 row 数 |
| `/window 12h` | 現在時刻を中心とした agenda window |
| `/quit` | TUI を終了 |

#### editor の指定

`/edit` (および `fzf --action edit`) は `EDITOR`、`VISUAL`、config の `editor` key の
順で editor を解決します。config key は、どちらの環境変数も通常設定されていない
Windows のために用意されています。

```powershell
$env:EDITOR = "code"                                               # 現在のセッションのみ
[Environment]::SetEnvironmentVariable("EDITOR", "code", "User")    # 永続化
```

```sh
export EDITOR=vim        # 永続化するには shell の profile に追記
```

```json
{ "editor": "code" }
```

config file は**カレントディレクトリ**の `.lifetxt.json` または `lifetxt.config.json`、
あるいは `$LIFETXT_CONFIG` が指す path です。global な config 置き場はないため、
`editor` key はそのディレクトリで `lifetxt` を実行したときだけ有効です。
どこからでも有効にしたい場合は `EDITOR` を使ってください。

`code -n` のように flag を含めて指定できます。実行 file は `PATH` から解決されます。
Windows では `code` が `.CMD` であり、名前だけでは起動できないためこれが必要です。
window を開く editor には wait flag を渡すため、`/edit` は file を閉じてから戻ります。

行番号は `vim`、`nvim`、`vi`、`nano`、`emacs`、`micro`、`gedit` には `+42` 形式で、
`helix`、VS Code とその派生、Sublime Text には `path:42` 形式で渡されます。
それ以外の editor には file path のみを渡します。
editor が未設定の場合は、実行すべき command を platform ごとに明示した error になります。

端末内 editor にも対応しています。TUI は editor を起動する前に端末を解放し、
終了時に画面を復元します。

command の短縮名: `/d` done、`/s` state、`/a` add、`/f` search、`/t` timer、
`/e` edit、`/u` undo、`/n` next、`/q` quit。完全一致の別名は fuzzy 順位より優先されます。

#### 編集の安全性

編集系 command はすべて 1 つの内部 mutation path を通ります。
書き込み前に対象 row をすべて検証するため、`id:` を持たない row を含む一括編集は
明示的に失敗し、一部だけが適用されることはありません。
対象 file は 1 つの undo entry として snapshot されるため、
`/delete` を含む一括操作も `/undo` 1 回で元に戻せます。

`id:` を持たない row は TUI から編集できません。先に `lifetxt ids --assign` を実行してください。

#### timer

`/timer start` は選択行の計測を開始し、`[ ]` の task を `[/]` に変更します。
`/timer status` は実行中の timer を表示し、`/timer stop` は経過分を既存の `elapsed:` に
加算して timer を終了、`/timer cancel` は `elapsed:` を書かずに破棄します。
state file は `lifetxt timer` と共有されるため、両者を通じて同時に動く timer は 1 つだけです。

#### export

`/export` は画面上の filter と並び順をそのまま反映して書き出します。
`/project work` → `/sort due` → `/export md report.md` でその view の報告書が作れます。
Markdown は section ごとの checkbox list、CSV は header 1 行 + record 1 行ずつ、
JSON は detail を含む row object を出力します。

#### row の上限

`tui.limit` (または `/limit N`) は section ごとの表示 row 数を制限します。
省略は必ず表示されます。section header に `TASKS 10/30` と表示され、
section 末尾に `... 20 more hidden by limit:10` の行が追加されます。

#### session 状態

view、sort、project / context / tag filter、inspector の表示状態、command 履歴は
終了時に `.cache/lifetxt/tui_session.json` に保存され、次回起動時に復元されます。
無効になった値は失敗せずに無視されます。
`tui.session_file` で保存先を変更でき、`tui.session` を `off` にすると無効化されます。

#### key 操作

既定の `prompt` keymap では、Up/Down で選択移動 (palette が開いている場合は候補移動)、
PageUp/PageDown で半ページ移動、Home/End で先頭・末尾へ移動、`Ctrl-T` で選択行の mark 切り替え、
`Ctrl-P` / `Ctrl-N` で入力履歴の呼び出し、`Ctrl-A` / `Ctrl-E` で入力の先頭・末尾へ移動、
`Ctrl-U` / `Ctrl-K` で cursor 前後の削除、`Ctrl-C` で traceback を出さずに終了します。

`--keymap vim` では navigation mode から開始します。`j` / `k` で移動、`g` / `G` で先頭・末尾、
`Space` で mark、`Enter` で inspector 切り替え、`Tab` で view 循環、
`d` / `e` / `u` / `r` で done / edit / undo / reload、`/` で filter 入力、`:` で command 入力、
`?` で help、`q` で終了します。
`/` と `:` は一度きりの入力で、`Enter` または `Esc` の後は navigation mode に戻るため、
すぐに `j` / `k` で移動できます。

help 表示中は `j` / `k` と PageUp/PageDown で 1 画面に収まらない一覧を scroll できます。

#### 表示

端末幅が 118 列以上ある場合、inspector は下部ではなく右側の pane として list の横に表示され、
狭い pane でも値が切れないよう 1 項目 1 行で表示されます。

`--theme auto|dark|light|mono` で配色、`--glyphs auto|unicode|ascii` で罫線文字を指定します。
`auto` は出力 encoding を判定し、端末が丸角罫線を表現できない場合は ASCII に fallback するため、
Windows の code page でも例外にならず安全に劣化します。
列幅は East Asian Width を考慮するため日本語 title でも整列が崩れず、
meta 列 (project、due、priority) は端末幅が狭くなると折り返さずに 1 列ずつ省略されます。

既定値は config の `tui.theme`、`tui.keymap`、`tui.glyphs`、`tui.limit`、`tui.agenda_window`
で設定できます。

filter と並び替えは cache された parse 結果に対して行われるため、
input bar への入力で file を読み直すことはありません。
再 parse は file が変更されたとき、書き込みの後、`/reload` のときだけ発生します。

入力 file が変更されると自動 reload します。`watchdog` が利用可能な場合は file event を使い、
未導入の場合は mtime を定期確認する fallback で動作します。
parse に失敗した file は終了せずに diagnostic 付きの error panel を表示するため、
file を修正すればそのまま復帰します。

### 13.2 `fzf`

`fzf` は通常の item filter を適用した後、`fzf` または `peco` で item を選択し、action を実行します。

```sh
python -m lifetxt fzf life.txt --open --type task --action done
python -m lifetxt fzf life.txt --project research --action show
python -m lifetxt fzf "projects/**/*.life.txt" --tool peco --action edit
```

| Option | 意味 |
|---|---|
| `--action done|edit|delete|show` | 選択 item に実行する action。省略時は prompt |
| `--tool fzf|peco` | 選択 tool。既定では `fzf`、次に `peco` を探索 |
| `--preview` / `--no-preview` | `fzf` preview の有効/無効 |
| `--print-query` | `fzf` の query 行だけを出力 |

`done` と `delete` は item ID を必要とします。必要なら先に `ids --assign` で ID を付与してください。
`delete` は source file、line、title を表示したうえで `DELETE` の入力を要求します。
`fzf` preview では source location、複数行 `body:`、生成された life.txt 行を表示します。

### 13.3 `timer`

`timer` は 1 つの running timer を JSON state file に保存し、停止時に合計時間を `elapsed:` として item に書き戻します。

```sh
python -m lifetxt timer start life.txt --id task_report
python -m lifetxt timer status life.txt
python -m lifetxt timer pause
python -m lifetxt timer resume
python -m lifetxt timer stop
python -m lifetxt timer summary life.txt --project research
```

| Subcommand | 意味 |
|---|---|
| `start path --id ID` | `id:ID` の item の計測を開始。`[ ]` は `[/]` に変更 |
| `pause` | item は変更せず、単一の running timer を一時停止 |
| `resume` | 一時停止中の timer を再開 |
| `stop [path] [--id ID]` | running timer を停止し `elapsed:` を更新 |
| `status [path ...]` | running timer と経過時間を表示 |
| `summary path ...` | `elapsed:` を item / project ごとに集計 |
| `cancel` | item を変更せず state file だけ削除 |

同時に動かせる timer は 1 つだけです。`pause` は累積分数を state file に保存し、
`stop` は timer が一時停止中でも累積合計を item に書き戻します。`elapsed:` は
`25m`、`1h`、`1h30m` のように記録されます。state file の既定値は
`~/.lifetxt_timer.json` で、config の `timer.state_file` で変更できます。

### 13.4 `stats`

`stats` は task 完了率、期限超過、habit streak、mood、project 別進捗を表示します。

```sh
python -m lifetxt stats life.txt
python -m lifetxt stats life.txt --from 2026-06-01 --to 2026-06-30
python -m lifetxt stats life.txt --project research --format json
python -m lifetxt stats life.txt --tag focus --assignee alice --format json
python -m lifetxt stats "projects/**/*.life.txt" --group weekly
python -m lifetxt stats life.txt --width 60
```

| Option | 意味 |
|---|---|
| `--from DATE` | 開始日。省略時は `--to` の 29 日前 |
| `--to DATE` | 終了日。省略時は今日 |
| `filter options` | `filter` と同じ item filter。status、type、project、tag、user、team、people、detail、text、time filter を含む |
| `--group daily|weekly|monthly` | mood trend の集計単位 |
| `--format text|json` | 出力形式 |
| `--width N` | 狭い terminal 向けの compact text 出力 |

`weekly` / `monthly` では task bucket ごとの done / total / overdue と、
bucket ごとの habit sparkline も表示します。

### 13.5 report / chart / batch / encryption

`review` は JSON、JSONL、Markdown、単体 HTML report を出力できます。

```sh
python -m lifetxt review life.txt --week --format html > weekly_review.html
```

`plot` は既定では terminal bar chart を表示します。`--format svg` は追加依存なし、
`--format png` は `matplotlib` がある場合に利用できます。

```sh
python -m lifetxt plot life.txt --chart deadlines --from 2026-06-01 --to 2026-06-30
python -m lifetxt plot life.txt --chart tasks --format svg -o tasks.svg
python -m lifetxt plot life.txt --chart habits --format png -o habits.png
```

`export-heatmap` は task / habit activity を SVG heatmap として出力します。

```sh
python -m lifetxt export-heatmap life.txt --from 2026-01-01 --to 2026-12-31 -o activity.svg
python -m lifetxt export-heatmap "projects/**/*.life.txt" --type habit --project research -o habits.svg
```

`batch` は複数ファイルに対して既存の `done` / `assign` 処理を反復実行します。

```sh
python -m lifetxt batch done "projects/**/*.life.txt" --id task_report
python -m lifetxt batch assign life.txt team_life.txt --text Review --to alice --dry-run
```

`encrypt` / `decrypt` は環境変数または UTF-8 text file から passphrase を読み取れます。

```sh
python -m lifetxt encrypt life.txt --field body --type journal --key-file .secrets/lifetxt.key
python -m lifetxt decrypt life.txt --field body --key-file .secrets/lifetxt.key
```

`inbox --fzf` は未分類 inbox item を `fzf` または `peco` に渡し、選択された行を出力します。

### 13.6 `git-hook`

`git-hook` は現在の repository に local Git hook を導入します。生成される `pre-commit`
hook は `lifetxt check` を実行し、`commit-msg` hook は利用可能な場合に完了 task の要約を commit message に追記します。

```sh
python -m lifetxt git-hook status
python -m lifetxt git-hook install --files life.txt examples/*.txt
python -m lifetxt git-hook uninstall
```

既存の非 lifetxt hook は `--force` なしでは上書きしません。検証だけが必要なら `--no-commit-msg` を指定します。

### 13.7 `completion`

`completion` は shell completion script を生成します。

```sh
python -m lifetxt completion bash
python -m lifetxt completion zsh -o ~/.zfunc/_lifetxt
python -m lifetxt completion fish -o ~/.config/fish/completions/lifetxt.fish
python -m lifetxt completion powershell -o $HOME\Documents\PowerShell\lifetxt-completion.ps1
python -m lifetxt completion install --shell bash
```

`completion install` は導入手順を表示するだけで、shell startup file は自動変更しません。

候補はすべて CLI 自身の argument parser から生成されるため、コマンドや flag を
追加すればその時点で補完に現れます。

**option は入力中のコマンドに限定されます。** `lifetxt check --<TAB>` は
プログラム全体の flag ではなく `check` が受け付ける 10 個だけを提示します:

```txt
lifetxt check --<TAB>
  --help --verify-files --no-files --format --warnings-as-errors
  --ignore --severity --code --category --config
```

**値も補完されます。** `--type`、`--format`、`--theme`、`--state` などの固定集合は
フォーマット定義に由来します。subcommand も補完され、`lifetxt timer <TAB>` は
`start stop status cancel` を提示します。

presence の state は flag の値としてだけでなく、`state`・`s`・`start` が取る
positional としても補完されます。実際に入力するのはこの形です:

```txt
lifetxt state <TAB>
  available busy focus meeting away commuting working offline sleeping
```

#### 自分のファイルからの候補

`state:` は自由記述であり、project・tag・id・人名は利用者固有のものなので、
組み込みの一覧では表現できません。生成された script は補助コマンドを呼び出して
現在のファイルを読みます:

```bash
python -m lifetxt completion values --kind state
python -m lifetxt completion values --kind project life.txt
```

| `--kind` | 候補 |
|---|---|
| `state` | 文書化された state に続けて、ファイル内の独自 state |
| `project`、`tag`、`id` | ファイル内に存在する値 |
| `person` | `person:`、`owner:`、`assignee:`、`attendee:`、`sender:`、`recipient:`、`user:` |
| `type`、`status` | フォーマット自身の集合。ファイル不要 |

path 省略時は config の `paths` を使います。shell は入力中にこれを実行するため、
決して fail-loud にはなりません。読めないファイルや存在しないファイルの場合は、
prompt を壊すエラーではなく組み込みの候補を返します。

そのため `state:hyperfocus` を使っているファイルでは次のようになります:

```txt
lifetxt state <TAB>
  available busy focus meeting away commuting working offline sleeping hyperfocus
```

PowerShell の注意点: `lifetxt check --<TAB>` は動作しません。PowerShell は単独の
`--` を「パラメータ終端」として扱い、completer を呼び出さないためです。
`lifetxt check --v<TAB>` のように 1 文字以上入力してください。

### 13.8 `deps`

`deps` は宣言済みまたは未解決の dependency chain を indented tree として表示します。
`agenda` や `health` と同じ blocker semantics を使い、`depends_on:` target は現在の
item を block し、`blocks:ID` を持つ item は target `ID` を block します。

```sh
python -m lifetxt deps life.txt
python -m lifetxt deps life.txt --blocked
python -m lifetxt deps life.txt --root task_report
python -m lifetxt deps life.txt --root task_report --format json --pretty
python -m lifetxt deps life.txt --root task_report --format mermaid --depth 2
python -m lifetxt deps life.txt --blocked --format dot
```

| Option | 意味 |
|---|---|
| `--blocked` | open blocker を持つ open item のみ表示 |
| `--root ID` | 1つの item ID から blocker chain を辿る |
| `--format text|json|mermaid|dot` | 出力形式 |
| `--depth N` | 表示する dependency depth の上限。`0` は root のみ |
| `--pretty` | JSON を整形して出力 |

### 13.9 `complete` と habit `done` ログ

`[x]` と `done:` だけで task を完了にすると、`repeat:` の周期情報が失われます。
次回の due instance は誰も記録せず、file 自体が唯一の完了履歴になってしまいます。
`complete` と、habit item 向けに拡張された `done` はこの問題を、新しい記法を
発明せずに既存の `repeat:`、`due:`/`do:`、`until:`、`done:` の上に構築して解決します。

**`complete`** は repeat 付き task（type は任意、多くは `T`）を対象にします。
現在の instance を `done:DATE` 付きで `[x]` にし、その直後に次回 due を持つ新しい
`[ ]` instance を追記します（Taskwarrior 方式）。

```sh
python -m lifetxt complete life.txt task_water_plants
python -m lifetxt complete life.txt --text "Water plants" --date 2026-07-08
python -m lifetxt complete life.txt task_water_plants --dry-run
```

次回 due は `repeat:` の周期をちょうど1つ分、anchor 日付から進めます。anchor は
item の detail key `repeat_base:due|done`（または config の
`defaults.repeat_base`、デフォルトは `due`）で選べます。

- `repeat_base:due` は item の現在の `due:`/`do:` から進めます。`due:` /
  `do:` が無い場合は開始日を推測せず fail-loud でエラーになります。
- `repeat_base:done` は完了日（today、または `--date`）から進めます。「実際に
  やった日から3か月後」のように、固定スケジュールより実施日基準が重要な task
  に向いています。

`until:` の上限を超える場合は、現在の instance を完了にした上で新しい
instance を作らず、series が終了したことを表示します。`BYDAY` の RRULE
（例: `RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR`）はまだ instance 生成に対応しておらず
fail-loud エラーになります。該当する場合は due を手動で編集してください。
`repeat:` を持たない item は `done` と全く同じ動作になります。新しい instance
には必ず新規生成した ID が割り当てられ（完了済み instance は元の ID を保持）、
`ids` が重複を報告することはありません。繰り返し完了によるファイル増加は
想定内の挙動なので、定期的に `archive` を実行して完了済み instance を作業
file から退避してください。

**habit `done` ログ**（`H` type item）は異なるアプローチを取ります。habit の
定義は常に開いた状態の1行のまま保ち、履歴だけが積み上がっていくべきだから
です。`H` item に対する `lifetxt done PATH ID [--date DATE] [--force]` は
`status:` を変更せず、既存の `done:` 値のリストに `done:DATE` を追記し
（他の繰り返し可能な detail key と同様の複数値リスト）、結果の streak を
表示します。

```sh
python -m lifetxt done life.txt habit_exercise
python -m lifetxt done life.txt habit_exercise --date 2026-06-01
```

同じ日付を2回記録しようとすると fail-loud エラーになります（`--force` で
意図的に上書き可能）。誤って2回実行しても streak が静かに水増しされることは
ありません。streak は蓄積された `done:` の日付から `stats.streak_days` で
計算されます。これは Web UI の heatmap や `stats --habits` と同じ関数なので、
すべての画面で一致します。habit 以外の `done` の動作は変わりません:
`done PATH ID [--date DATE]` は引き続き item を `[x]` にし `done:DATE`
（省略時は今日）を設定します。

### 13.10 `rrule`: 繰り返しルールの展開

`repeat:` は単純な cadence（`daily`、`weekly`）と iCalendar の RRULE
（`RRULE:FREQ=MONTHLY;BYDAY=1MO`）の両方を受け付けます。ルールの文字列だけでは
実際の日付が分かりにくいため、`rrule` は `agenda` や `complete` が使うのと同じ
具体的な日付に展開します。

ルールを直接展開する:

```bash
python -m lifetxt rrule "RRULE:FREQ=MONTHLY;BYDAY=1MO" --from 2026-07-01 --count 3
```

```txt
Every month on 1st Monday
  1  2026-07-06  Mon
  2  2026-08-03  Mon
  3  2026-09-07  Mon
```

item に設定済みのルールを展開する:

```bash
python -m lifetxt rrule --path life.txt --id standup --count 4
```

option:

| option | 意味 |
|---|---|
| `--path PATH`、`--id ID` | ルールを直接渡す代わりに既存 item の `repeat:` を読む |
| `--from DATE` | 起点。省略時は今日、または item の `due:`/`do:`/`from:` |
| `--after DATE`、`--before DATE` | 出力する期間を限定 |
| `--count N` | 出力する最大件数（既定 10） |
| `--format text\|json\|life` | 表形式、JSON、貼り付け可能な life.txt 行 |
| `--type KIND`、`--title TEXT` | `--format life` で使う type と title |

`--format life` はそのまま追記できるレコードを出力します。`complete` に頼らず
決まった件数だけ実体化したい場合に便利です:

```bash
python -m lifetxt rrule weekly --from 2026-07-06 --count 2 --format life \
  --type T --title Standup
```

```txt
[ ] T Standup due:2026-07-06
[ ] T Standup due:2026-07-13
```

対応している部分は `FREQ`、`INTERVAL`、`COUNT`、`UNTIL`、`BYDAY`（`1MO` や
`-1FR` のような序数付きも含む）、`BYMONTHDAY`（月末を表す `-1` などの負値も
含む）、`BYMONTH` です。対象外の部分は黙って無視せず stderr に報告します:

```txt
Ignoring unsupported RRULE part(s): BYSETPOS
```

日付のみの `UNTIL` はその日全体を含みます。`UNTIL=20260703` は 2026-07-03 を
含み、その日の 0 時で打ち切られることはありません。

## 14. alias

status alias:

| Alias | Status |
|---|---|
| `todo`, `open`, `not_completed`, `queued`, `scheduled` | `[ ]` |
| `progress`, `doing`, `in_progress`, `active`, `sending` | `[/]` |
| `done`, `complete`, `completed`, `sent`, `delivered` | `[x]` |
| `cancel`, `canceled`, `cancelled` | `[-]` |
| `defer`, `deferred`, `moved` | `[>]` |
| `pending`, `unknown` | `[?]` |
| `note`, `n` | `[N]` |
| `x`, `/`, `-`, `>`, `?` | 対応する記号 status |

type alias:

| Alias | Type |
|---|---|
| `task`, `todo` | `T` |
| `event`, `calendar` | `E` |
| `deadline`, `due` | `D` |
| `reminder`, `remind` | `R` |
| `habit`, `recurring` | `H` |
| `note`, `memo` | `N` |
| `status`, `presence`, `presence_status`, `state` | `S` |
| `message`, `msg`, `mail`, `notification` | `M` |
| `journal`, `diary`, `log`, `entry` | `J` |

## 15. 実用例

検査と変換:

```sh
python -m lifetxt check life.txt
python -m lifetxt to-json life.txt --pretty -o life.json
python -m lifetxt to-jsonl life.txt --open --type task -o open_tasks.jsonl
```

絞り込んだ life.txt ファイルを作成:

```sh
python -m lifetxt filter life.txt --open --type task -o open_tasks.life.txt
python -m lifetxt filter life.txt --after now --type event -o future_schedule.life.txt
python -m lifetxt filter life.txt --type status --person self -o my_status.life.txt
```

カレンダー予定を取り込む:

```sh
python -m lifetxt import-ics google_calendar.ics -o life.txt --append --tag google
```

秘密 iCalendar URL からカレンダー予定を同期する:

```sh
python -m lifetxt sync-ics --url-env LIFETXT_GOOGLE_CAL_ICS -o .generated/google_calendar.life.txt --cache-dir .cache/lifetxt --tag google
```

現在時刻付近の未完了 item を表示:

```sh
python -m lifetxt agenda life.txt --around now --window 2h --open
```

今日の未完了 task を表示:

```sh
python -m lifetxt agenda life.txt --from 2026-06-06 --to 2026-06-06 --open --type task
```

チームの現在状態を表示:

```sh
python -m lifetxt status life.txt --active
```

ブラウザGUIを起動:

```sh
pip install -r requirements-web.txt
python -m lifetxt serve life.txt
```

## 16. `init` と `doctor`

この2つの command は新規ユーザー向けの推奨エントリーポイントです。

```sh
python -m lifetxt init
python -m lifetxt init --yes
python -m lifetxt doctor
```

`init` は starter life.txt と対応する `.lifetxt.json` を作成します。

| Option | 意味 |
|---|---|
| `--file PATH` | 作成する life.txt file。省略時は `life.txt` |
| `--config-output PATH` | 作成する config file。省略時は `.lifetxt.json` |
| `--force` | 確認なしで既存 file を上書き |
| `--name NAME` | 自分の名前。`#! self:` と `defaults.person` に書き込まれる |
| `--timezone TZ` | timezone。`#! timezone:` と `defaults.timezone` に書き込まれる |
| `--project NAME` | default project。`#! project:` と `defaults.project` に書き込まれる |
| `--yes` | すべて既定値 (`self`、`UTC`、project なし) で非対話実行。`--force` と併用した場合の上書き確認プロンプトも省略される。script や CI 向け |

`--yes` を付けない場合、`init` は名前・timezone・default project を尋ね、
既存の `life.txt` や config file を上書きする前に確認します
(`--force` 指定時を除く)。`--yes` を付けると3つのプロンプトはすべて
スキップされ、`--name`/`--timezone`/`--project` で指定されなかった値は
組み込みの既定値になります。

`doctor` は pass/warn/fail の check を表示し、file は一切変更しません。

| Check | 検査内容 |
|---|---|
| `python` | Python 3.10+ (未満は FAIL) |
| `life.txt` | 設定または既定の life.txt file が存在し読み取り可能か |
| `config` | `.lifetxt.json` (または `--config` の path) が存在するか (無ければ WARN) |
| `fzf`, `peco` | optional selector tool が `PATH` にあるか (無ければ WARN) |
| `textual`, `watchdog`, `matplotlib`, `cryptography` | optional Python package が導入済みか (無ければ WARN) |
| `check` | life.txt file を解析し error/warning 件数を報告 |
| `ids` | `id:` が無い item を報告 |

`doctor` は `FAIL` レベルの check がある場合のみ非ゼロで終了します
(Python version が古い、または file が存在しない/読み取れない場合)。
optional dependency の不足は `WARN` であり、終了コードには影響しません。
機械可読な出力には `--format json` を使用してください。

## 17. `encrypt` と `decrypt`

標準ライブラリのみを使った field 単位の暗号化 (journal の body、message の
本文など機密性の高い値向け)。追加 dependency は不要です。

```sh
LIFETXT_KEY="correct horse battery staple" python -m lifetxt encrypt life.txt --field body --type J
LIFETXT_KEY="correct horse battery staple" python -m lifetxt decrypt life.txt --field body
```

**アルゴリズム。** 値は in-place で `enc:XSK:BASE64` の形式にタグ付けされます
(例: `body:"enc:XSK:AbCd..."`)。XSK ("XOR stream cipher, keyed") は
PBKDF2-HMAC-SHA256 (100,000 iteration) と値ごとにランダムな 16 byte の
salt から 32 byte の key を導出し、SHA-256 の繰り返し
(`SHA256(key ‖ counter)`) で keystream を生成して UTF-8 平文と XOR します。
`salt ‖ ciphertext` に対する HMAC-SHA256 (同じ導出 key を使用) を先頭に
付与して整合性を保証しており、MAC が一致しない値は `decrypt` が復号を
拒否します ("wrong passphrase or tampered data")。そのため passphrase の
typo は文字化けではなく明確なエラーになります。これは `hashlib`/`hmac`/
`secrets` のみで組んだ独自実装であり、リポジトリを信頼している前提での
私的な journal など「カジュアルにローカルの秘密を隠す」用途には十分ですが、
監査は受けておらず、レビュー済みの暗号 library の代替にはなりません。

**Passphrase の強度。** key は passphrase のみから導出されるため、
passphrase の強度がデータを守る唯一の要素です。辞書に載っている単語では
なく、長く一意な passphrase (複数単語のフレーズや password manager の
出力) を使ってください。passphrase 自体を repository に commit しては
いけません。

**Key の管理方法。**

| 方法 | Flag | 備考 |
|---|---|---|
| 環境変数 | `--key-env NAME` (既定 `LIFETXT_KEY`) | ローカル shell や CI の secret に便利。shell の history に残さないよう注意 |
| Key file | `--key-file PATH` | `--key-env` より優先。file は repository の外に置くか `.gitignore` に追加する |

**Rotation workflow。** passphrase を rotate するには、影響するすべての
file を古い passphrase で `decrypt` し、新しい passphrase で再度
`encrypt` してから古い passphrase を破棄します。in-place の re-key
操作は無いため、rotation 中は両方の passphrase が必要です。

**部分的に暗号化された file の check。** `check` と `filter` は
`enc:XSK:...` の値を不透明な文字列として扱い、復号を試みません。
そのため暗号化済みの値と平文の値が混在する file でも、構文検証や他 field
による filter は通常どおり動作します。暗号化された field の平文内容で
filter するには、事前に復号する必要があります。

**Upgrade path。** optional package の `cryptography` が導入されていれば
(`pip install cryptography`)、組み込みの XSK 方式の代わりに標準的で
レビュー済みの AES-GCM 実装を検討してください。`doctor` は
`cryptography` の有無を報告します。ただし `encrypt`/`decrypt` は現時点で
自動検出して使用することはありません — これは今後の方向性であり、
現在の挙動ではありません。

Current encryption and watch additions:

```sh
python -m lifetxt batch tag-rename "projects/**/*.life.txt" --old inbox --new triage --dry-run
python -m lifetxt batch tag-merge team.life.txt archive.life.txt --old urgent_old --new urgent
python -m lifetxt batch migrate "projects/**/*.life.txt" --migration normalize-status --backup
python -m lifetxt watch life.txt --run agenda --timestamp
python -m lifetxt watch life.txt --run "agenda --around now --window 2h" --notify
python -m lifetxt encrypt life.txt --field body --algorithm aesgcm --key-file .secrets/lifetxt.key
```

`batch` now supports `done`, `assign`, `tag-rename`, `tag-merge`, and
`migrate`. `watch --timestamp` prints run headers, and `watch --notify`
notifies when the child command exit status changes. `encrypt --algorithm
aesgcm` uses the optional `cryptography` package and writes `enc:GCM:` values;
`decrypt` auto-detects both `enc:XSK:` and `enc:GCM:`.

## 18. `share`、`digest`、`template`

### `share`

server を起動せずに、filter した item・bar chart・table をまとめた
自己完結型の HTML または Markdown report を出力します。

```sh
python -m lifetxt share life.txt --open --type task -o open_tasks.html
python -m lifetxt share life.txt --week --format markdown -o weekly.md
python -m lifetxt share life.txt --project research --title "Research report"
```

`share` は `filter`/`agenda` と同じ filter option (2章参照) に加え、
以下を受け付けます。

| Option | 意味 |
|---|---|
| `--week` | report の見出しに現在の ISO week (月曜日〜今日) を表示 |
| `--month YYYY-MM` | report の見出しに特定の calendar month を表示 |
| `--format html\|markdown` | 出力形式。省略時は `html` |
| `-o, --output PATH` | 出力先 file。省略時は `share.html` または `share.md` |
| `--title TEXT` | report title。省略時は "lifetxt share report" |

`--week`/`--month` は report 見出しの表示のみを変更します。日付で
含める item を絞り込みたい場合は `--after`/`--before` を併用してください。
HTML 出力は外部依存が無く (inline CSS、inline SVG chart)、ブラウザで
直接開いたり email に添付したりできます。

### `digest`

`review` 相当の期間サマリーを Slack、email、または local file へ配信します。

```sh
python -m lifetxt digest life.txt --week --format slack-webhook --url-env SLACK_WEBHOOK_URL
python -m lifetxt digest life.txt --month 2026-06 --format email --to team@example.com
python -m lifetxt digest life.txt --week --format file --path digest-log.md
```

| Option | 意味 |
|---|---|
| `--week` / `--month YYYY-MM` | `review` と同じ期間選択 |
| `--project NAME` | 特定 project に限定 |
| `--format slack-webhook\|email\|file` | 配信 channel (必須) |
| `--url-env ENVVAR` | Slack incoming webhook URL を格納した環境変数 (`slack-webhook`) |
| `--to ADDRESS` | 送信先 email address (`email`) |
| `--smtp-host-env`, `--smtp-user-env`, `--smtp-pass-env` | SMTP host/username/password を格納した環境変数 (`email`)。既定は `LIFETXT_SMTP_HOST`/`_USER`/`_PASS` |
| `--path PATH` | Markdown を追記する local file (`file`) |
| `--dry-run` | message を組み立てて表示するのみで、network request も書き込みも行わない |

各 channel は、network request や書き込みを行う **前に** 必要な環境変数
(または `--to`/`--path`) を検証します。そのため secret が不足している
場合は配信途中でなく即座に明確なエラーで失敗します。

### `template`

config `templates` に定義した再利用可能な named item template を
list / apply します。

```sh
python -m lifetxt template list
python -m lifetxt template apply weekly_review --append life.txt
python -m lifetxt template apply weekly_review --append life.txt --dry-run
```

`.lifetxt.json` で template を定義します。

```json
{
  "templates": {
    "weekly_review": {
      "lines": [
        "[ ] T Weekly_Review due:{next_monday} project:reflection",
        "[ ] T Plan_Next_Week due:{next_monday} project:reflection"
      ]
    }
  }
}
```

日付 placeholder は template 定義時ではなく apply 実行時に解決されます:
`{today}`、`{next_monday}` (直近の未来の月曜日)、`{next_week}`
(今日 + 7日)。`H` habit と異なり、template の内容は自動で
再スケジュールされません — `apply` を再実行すると、新しく解決された
日付で同じ行がもう一度追記されます。
