# Quick capture と省略記法

Quickは、**省略記法または完全なlife.txt 1行**を受け付ける共通入力基盤です。
CLI `add` / `quick` / `q`、ローカル／Remote TUI `/add`、Web Quick Add、
`/capture`、Planner Quick Capture、MCP `capture_item`が同じresolverを利用します。
完全なrecordは既存Format parser、省略記法は既存の4種類のtoken parserで解析します。
保存されるfileでは `@home` は `project:home` のような正規fieldになります。

共通fieldを素早く入力するなら省略記法を、type・status・body・引用値・繰り返し／
custom keyを明示するなら完全な[Format line](./life_txt_format_spec.md)を、同じ入口で使えます。

## Quick start

`--append`で書込先を指定するか、`write_file`を設定します。

```sh
lifetxt add "Buy milk" --append life.txt
lifetxt quick "Buy milk @home #errand" --append life.txt
lifetxt q "Submit report @work !high ^tomorrow" --append life.txt
```

`add`は初心者向けaliasで、3つのCLI表記は同じhandlerを使います。`quick -`なら
stdinの1行をtitleとして読めます。

## 対応するcapture token

tokenは「1つのsigil＋空白を含まない1文字以上の値」からなる、空白区切りの
完全な単語でなければなりません。

| 入力 | 正規field | 例 | 繰返し |
| --- | --- | --- | --- |
| `@NAME` | `project:NAME` | `@home` | 全値をparse。projectは1つを推奨 |
| `#NAME` | `tag:NAME` | `#errand` | 累積。CLIはmergeして重複排除 |
| `!VALUE` | `priority:VALUE` | `!high` | 全値をparse。priorityは1つを推奨 |
| `^DATE` | `due:DATE` | `^tomorrow` | 全値をparseし、保存前に日付解決 |

parserはproject、tag、priorityの値を語彙に制限せず、sigil後の非空白文字列を
値にします。生成lineには通常のFormat validationが適用されます。`^`のような
sigilだけのtokenはtitle textのままです。

## 入力と保存結果

明示的な日付なら対応は決定的です。

```text
Buy milk @home #errand !high ^2026-10-02
    -> title: Buy milk
       project: home; tag: errand; priority: high; due: 2026-10-02
    -> [ ] T "Buy milk" project:home tag:errand priority:high due:2026-10-02 id:task_...
```

quoteやfield順はserializerが決め、ID生成は設定とsurfaceに依存します。例示IDを
そのまま使わないでください。

## 日付の便宜入力

`^DATE`はISO dateまたは次の共有tokenを受け付けます。

| 入力 | 解決結果 |
| --- | --- |
| `today`, `tomorrow`, `yesterday` | 対応する暦日 |
| `monday` ... `sunday` | 次の該当曜日（今日なら7日後） |
| `next_monday` ... `next_sunday` | 次の該当曜日からさらに7日後 |
| `next_week` | 次の月曜日 |
| `+3d`, `-1w`, `+2m`, `+1y` | 日・週・月・年の符号付きoffset |

workspace-awareな現在日を基準にし、月・年shiftは有効な日に丸めます。
`^tomorrow`は先に解決され、`due:YYYY-MM-DD`として保存されます。
`due:tomorrow`が正規Formatになるわけではありません。CLIの`--due`/`--do`/
`--until`とTUI `/due`も同じdate tokenを使います。不明または不可能な`^DATE`は
書込み前に拒否されます。

## CLIの優先順位、default、重複

scalar fieldの優先順位は次の通りです。

```text
明示CLI option > capture sigil > named capture preset > config/file default
```

したがって`lifetxt add "Buy milk @home" --project errands`は
`project:errands`を書きます。presetの`type`、`status`、`project`、`tags`、
`priority`は明示入力がない場合だけ使われます。CLIでは`--tag`、shorthand、
presetのtagをmergeし、完全一致の重複を除きます。詳細は
[named capture preset](./config.md#名前付き-capture-preset)を参照してください。

共有parser自体はrepeated valueを保持します。parser結果を直接使うTUI、Web capture
endpoint、MCPでは、複数project/priority/dueや重複tagが残り得ます。CLIのtag重複
排除をsurface共通仕様として頼らず、scalar tokenは1つ、tagは一意にしてください。

`--no-shorthand`はCLI専用で、すべてのsigil tokenをtitleに残します。明示optionと
設定defaultは引き続き適用されます。

## 空白、quote、literal sigil

- CLIの`"Buy milk @home"`はshellがtitle引数をまとめます。parser自身にquoted-token
  grammarはありません。
- shorthand parse時に連続spaceは正規化されます。sigil値にspaceは使えず、
  `@"deep work"`を複数語projectの規約としては使えません。
- 単語内部のsigilはliteralです。`a@b.com`はtitleに残ります。
- token先頭にbackslashを1つ付けるとliteralになります。`Write about \@home`は
  title `Write about @home`になります。
- shorthand値内のspace専用escapeはありません。
- parserに届いたquote文字は通常のtitle/value文字です。unclosed quoteをshorthand
  errorにはしません。shell自身のquote規則に従ってください。

認識されたsigilだけでtitleが空になる入力は拒否されます。認識tokenのないplain
textは通常のtitle serialization以外は変更されません。

## 完全なrecordも同じQuick入口で入力

```sh
lifetxt quick '[N] N "Idea" body:"共通Quick入力を試す"' --append life.txt
lifetxt add '[N] J "Journal" on:2026-10-01 body:"今日の記録"' --append life.txt
```

Web Quick Add、`/capture`、Plannerにも同じ1行を貼り付けられます。
TUIでは `/add [N] N "Idea" body:"text"`、MCPでは `capture_item` の `text` に
完全な1行を渡します。Webの共通APIは `POST /api/items/capture`、bodyは
`{"text":"..."}`です。応答の `mode` は `shorthand` または `full_line`です。
`POST /api/quick/resolve` は同じ契約の非書込previewで、IDを生成しません。
明示的な `POST /api/items/raw` とstructured create/importも引き続き利用できます。

trim後に `[` で始まる入力は完全recordの意図として扱います。不正なstatus/type、
閉じていない引用符、構文エラーは省略記法のtaskに変換せず、何も書き込まずエラーを返します。
例：`[ ] T "unterminated`。Quickは1行入力専用で、複数行／一括importは対象外です。
Formatのwarningはwarningのまま、custom keyは有効のままです。
完全recordのtitle/body内のsigilは文字として保持し、展開しません。

完全record自体が優先されます。CLIのtype/status/detail flag、preset、設定由来の
入力defaultは省略記法にだけ適用します。完全recordのfieldはその1行内で指定してください。
`--no-shorthand`はtitleのsigil展開を止めますが、`--no-check`と併用しても
不正な完全recordの検証を回避できません。関連recordのcontextは未指定fieldだけを補います。
既存のrevision・認証・read-only・書込先の制約も適用されます。明示IDは保持し、
workspace内の重複IDは拒否します。CLIは `ids.auto` に従い、TUI/Web/MCPは従来どおり
操作用IDを保証します。設定されたID key/prefixを利用します。
MCPの設定に応じた出所metadataとdry-run proposalも維持します。

## 利用可能なsurface

| Surface | 共通Quick入口 | 固有の動作 |
| --- | --- | --- |
| CLI | `add`, `quick`, `q`, stdin | 既存の省略記法flag/preset/default |
| ローカルTUI | `/add`, `/a`, `/related` | 共通resolver。関連contextは未指定fieldを補完 |
| Remote TUI | `/add`, `/a`, `/related` | revision付きでtextをサーバーへ送り、サーバー側で解決 |
| Web UI | Quick Add、`/capture`、Planner、command `/add`、Focus Quick Add | 共通capture API。Focusはdue未指定時だけ今日を補完 |
| Web API | `POST /api/items/capture` | 省略記法または完全record。省略記法には`type`指定可 |
| MCP | `capture_item` | 省略記法または完全record。proposalと出所metadataを維持 |

`parse_shorthand` / `POST /api/shorthand/parse`は明示的な省略記法専用previewです。
structured/guided editorやpresence/message commandは専用契約を維持します。

すべてのshorthand capture経路は、空になったtitleと不正な`^DATE`を拒否します。
validation失敗時は対象recordを書きません。完全なfile grammarと推奨field値は
[Format specification](./life_txt_format_spec.md)、CLI optionは
[CLI reference](./cli.md)を参照してください。
