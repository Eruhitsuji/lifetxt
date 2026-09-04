# Getting Started: Beginner / Minimal Profile

`life.txt` には広い surface area があります: 9 個の item type、7 個の
status、数十の detail key、hierarchy、link、recurrence、message などです。
最初からそのすべてを覚える必要はありません。

このページでは **Beginner / Minimal Profile** を説明します。これは既存の
[format specification](./life_txt_format_spec.md) の小さな named subset で
あり、第二の format ではありません:

> Beginner Profile のすべての record は、そのまま valid な Full Format
> syntax です。ここで書いたものは、あとで format のより多くを学んだときに
> migration、変換、書き換えを一切必要としません。

```text
life.txt Format 1.0
├── Beginner / Minimal Profile   <- このページの level 1
├── Daily Use                    <- このページの level 2
└── Full Format                  <- life_txt_format_spec.md、level 3
```

読む前に動くところを見たい場合は、`lifetxt tour` が小さな Beginner
Profile のサンプルと、それに対する実際の derive された view を 1 つ
表示します。config も `life.txt` もセットアップも不要です:

```sh
lifetxt tour
```

## Level 1 -- Minimum（5分）

以下の4つを覚えれば、実用的な `life.txt` を書けます:

| Concept | Vocabulary |
| --- | --- |
| Status | `[ ]` open、`[x]` completed、`[N]` note |
| Type | `T` task、`E` event、`N` note |
| Time key | `due`、`on`、`from`、`to` |
| 長い text | item のあとに1行以上の `\|` 行 |

行の形はこうです:

```txt
[status] type "title" key:value
```

学習中は title を常に quote してください。これは通常の Format 1.0
syntax です（space を含まない bare title も valid です。format
specification の
[section 4](./life_txt_format_spec.md#4-title-と-value-の規則) を参照）。
quote することで、始めたばかりのときに考えることを一つ減らせます。

### Task（`T`）

```txt
[ ] T "Buy milk"
[ ] T "Write report" due:2026-09-10
[x] T "Buy milk" done:2026-09-01
```

`due:` は deadline です。`[x]` は task が done であることを表し、
`done:` に完了日を添えます。

### Event（`E`）

```txt
[ ] E "Lab meeting" on:2026-09-10
[ ] E "Lab meeting" from:2026-09-10T13:00 to:2026-09-10T14:00
```

終日の date には `on:`、特定の time range には `from:`/`to:` を使います。

### Note（`N`）

```txt
[N] N "Research idea"
```

`[N]` は note status で、`N`（そして後述の `J`）のように「open」でも
「done」でもなく、単に存在する record に使います。`|` continuation line
で長い text を追加できます:

```txt
[N] N "Research idea"
| Use previous and next frames as temporal context.
| Compare the result with the current frame-only model.
```

### 完全な5分ファイル

```txt
# Tasks
[ ] T "Buy milk"
[ ] T "Write report" due:2026-09-10

# Events
[ ] E "Lab meeting" from:2026-09-10T13:00 to:2026-09-10T14:00

# Notes
[N] N "Research idea"
| Temporal context may reduce false positives.
```

これは
[`examples/getting_started_life.txt`](../../examples/getting_started_life.txt)
です。自分の `life.txt` として保存し、check してください:

```sh
python -m lifetxt check life.txt
```

これが Level 1 の vocabulary のすべてです。`check` は他のすべての
command と同じ parser を使うので、この vocabulary だけで書けるものは
`filter`、`agenda`、`tui`、`serve` など他のすべての surface でもそのまま
動きます。

数行書いたら、`lifetxt today` が日々の入口になります:

```sh
python -m lifetxt today life.txt
```

これは第二の data model や新しい vocabulary ではありません -- 既に書いた
内容（due のもの、actionable なもの、blocked なもの、today の event）を
1 つの view に要約・優先順位付けするだけです。想定する動線は小さいまま
です: life.txt に書く、`today` で何に attention が必要か確認する、より
深く見る必要があるときだけ専門 command（`agenda`、`next`、`project`、...）
を使う。全体像は [life-hub.md](life-hub.md) を参照してください。

## Level 2 -- Daily Use

基本に慣れてきたら、以下の既存機能で ID・link・recurrence の内部仕様に
触れずに日常のほとんどをカバーできます:

| Concept | Vocabulary |
| --- | --- |
| 追加の type | `D` deadline、`R` reminder、`H` habit、`J` journal / diary |
| 追加の status | `[/]` in progress |
| 追加の key | `do`、`at`、`repeat`、`project`、`tag`、`priority` |

```txt
[/] T "Write paper" due:2026-09-30 project:research
[ ] R "Take medicine" at:21:00
[ ] H "English study" repeat:daily at:18:00
[N] J "Today" on:2026-09-10
| Worked on the experiment.
```

`project:` と `tag:` は `filter`、`stats`、Web UI で関連する item を
グルーピングします。`priority:`（`low`/`normal`/`high`、または数値）は
`next` の並び順に影響します。`repeat:`（`daily`、`weekly`、
`monthly`、`yearly`、`weekdays`）は recurring item を自動的に展開します。
type ごとの recommended key は format specification の
[section 9](./life_txt_format_spec.md#9-type-別-recommended-keys) を、
command level の filtering と shorthand capture
（`lifetxt add "Buy milk @home #errand !high ^tomorrow"` -- `add` は
`quick`/`q` の初心者向けの綴りです）は
[`cli.md`](./cli.md) を参照してください。

## Level 3 -- Full Format

`life.txt` の残りの機能はすべて、必要になったときにそこにあります。
Level 1 や Level 2 を正しく使っていたかどうかに関係なく利用できます:

- 残りの type（`S` status/presence、`M` message）と status（`[-]`
  canceled、`[>]` deferred、`[?]` pending）
- ID と link: `id`、`parent`、`ref`、`depends_on`、`blocks`、`related`、
  `duplicate_of`、`replaced_by`
- people/ownership key（`assignee`、`owner`、`attendee`、`person` など）
- recurrence の制限（`interval`、`until`、`count`）と `repeat:RRULE:...`
- indentation による hierarchy
- repeated key と custom key
- workflow / system metadata、development ticket、Personal Context /
  AI 向けの convention

これらが必要になったら
[`life_txt_format_spec.md`](./life_txt_format_spec.md) から始めてください。
Level 1 や Level 2 で書いたものを先に変更する必要はありません --
すでにそのまま full grammar への valid な入力です。

## 次に読むもの

- `lifetxt tour` -- config 不要の 30 秒デモ。何かを書く前にまず試すと
  よいです。
- `lifetxt init` -- 自分用の `life.txt` と config を作成します。
- `lifetxt add "Buy milk ^tomorrow"` -- 最初の実データを capture します。
- `lifetxt web` -- それに対してブラウザ UI を開きます。
- [`life_txt_format_spec.md`](./life_txt_format_spec.md) -- 完全な grammar
- [`cli.md`](./cli.md) -- すべての command、filter、output format
- [`use-cases.md`](./use-cases.md) -- 実践的な setup（task tracking、
  calendar、journaling、team status、AI integration）
- [`philosophy.md`](./philosophy.md) -- なぜ lifetxt がこの設計なのか
