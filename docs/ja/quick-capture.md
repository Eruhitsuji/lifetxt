# Quick capture と省略記法

Quick capture は短い入力を通常の `life.txt` task に変換します。CLI の
`add`、`quick`、`q`、TUI の `/add`、Web Quick add、MCP/Web の capture 操作は、
同じ4種類のtoken parserを共有します。省略記法は入力時だけの便宜機能です。
fileには `@home` ではなく `project:home` のような正規fieldが保存されます。

task titleと少数の共通fieldで十分ならQuick captureを使います。他のrecord type、
status、body、link、repeated/custom keyなどを明示する場合は、完全な
[Format line](./life_txt_format_spec.md)またはstructured create/editを使います。

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

## 完全lineはsurface固有

`/capture`を含むWeb Quick-add controlは、trim後に`[`で始まる入力をraw-line
endpointへ送ります。たとえば`[ ] N "Read later" tag:reading`を入力できます。
それ以外はshorthand capture endpointへ送ります。

CLI `add`/`quick`/`q`、TUI `/add`、MCP `capture_item`、Web
`POST /api/items/capture`にはこの完全line判定がありません。それぞれのraw/structured
authoring経路を使ってください。Web APIでは`POST /api/items/raw`が別endpointです。

## 利用可能なsurface

| Surface | Shorthand入口 | 主な差異 |
| --- | --- | --- |
| CLI | `add`, `quick`, `q` | option、preset、default、stdin、`--no-shorthand` |
| TUI | `/add TITLE` | shorthand。CLI option/presetなし。context prefillより明示sigil優先 |
| Web UI | Quick add、`/capture` | shorthandとUI専用の完全line routing |
| Web API | `POST /api/items/capture` | shorthand task capture。`type`指定可。raw lineは別endpoint |
| MCP | `capture_item`, `parse_shorthand` | task captureまたは非書込preview。structured `create_item`は別 |

すべてのshorthand capture経路は、空になったtitleと不正な`^DATE`を拒否します。
validation失敗時は対象recordを書きません。完全なfile grammarと推奨field値は
[Format specification](./life_txt_format_spec.md)、CLI optionは
[CLI reference](./cli.md)を参照してください。
