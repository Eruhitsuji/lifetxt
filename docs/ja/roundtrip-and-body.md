# ラウンドトリップと複数行 body の規則

この文書は、参照パーサーとシリアライザーが守るロスレスな規則を説明します。実行可能な例は `tests/golden/roundtrip_cases.json` にあり、`tests/test_roundtrip_golden.py` で検証されます。

## parse-serialize-parse 契約

有効な life.txt 文書では、参照実装は次の流れを満たします。

1. 入力をエラー診断なしで parse する。
2. parse した各 item を正規化された life.txt テキストへ serialize する。
3. 正規化後のテキストをもう一度エラー診断なしで parse する。
4. status、type、title、indent、detail key、繰り返し値の順序、detail value を同じ内容として復元する。

正規 serializer は LF 改行を書き出します。読み取り側は LF、CRLF、CR を受け付けます。UTF-8 テキスト、Unicode の title/value、引用符のエスケープ、繰り返し detail、階層、明示的な timezone offset 文字列は golden corpus で検証されています。

JSON と JSONL はすべての detail を配列として保持します。CSV は繰り返し値を JSON 配列形式のセルとして保持します。`+09:00` のような明示的 offset は、JSON、JSONL、CSV への往復中も detail 文字列の一部として残ります。日時比較のコードは parse 後の値を別途正規化できますが、交換形式は書かれた値を書き換えてはいけません。

## 1 つの continuation block は 1 つの body 値

`|` で始まる連続行は、正確に 1 つの複数行 `body:` 値を表します。

```txt
[N] J "Research log" on:2026-07-22
| First paragraph.
|
| Third line after a blank line.
```

parse 後の body 値は次の内容です。

```text
First paragraph.\n\nThird line after a blank line.
```

item に改行を含む `body:` 値が 1 つだけある場合、serializer はこの continuation 形式を使います。indentation は item 単位で保持されます。child item が複数行 body を持つ場合、各 `|` continuation line の前にも同じ item indentation が出力されるため、body は sibling item ではなくその child に結び付いたままです。

後方互換性のため、inline の `body:` 値が 1 つだけなら、その後ろに continuation 行を続けられます。

```txt
[N] N Note body:First_line
| Second line
```

追記先が 1 つに決まるため、これは `First_line\nSecond line` として parse されます。正規形式へ serialize すると inline detail は外され、continuation 行だけになります。

```txt
[N] N Note
| First_line
| Second line
```

## 意図的に拒否する形

繰り返された inline `body:` detail の後ろに continuation block を置くことはできません。

```txt
[N] N Note body:first body:second
| ambiguous continuation
```

continuation が `first`、`second`、または新しい値のどれに属するかを示す境界記号がないためです。parser は continuation 行の位置で error `E022` を報告し、繰り返し inline 値は変更しません。

continuation block がなければ、1 行だけの `body:` 値を繰り返す形は有効でロスレスです。

```txt
[N] N Note body:first body:second
```

ただし、繰り返された `body:` 値のどれかが複数行の場合は serialize できません。`|` 構文には、どの continuation 行がどの繰り返し値に属するかを保持する境界 marker がないため、serializer は値を平坦化したり結合したりせず `ValueError` を送出します。

## 記述時の指針

次のいずれかを使ってください。

- 短い値を 1 つだけ inline で書く: `body:short_text`
- すべての値が 1 行で、後ろに `|` block を置かない場合だけ inline の `body:` を繰り返す
- 複数行値を 1 つの continuation block として書く

単一の inline 値と continuation 行の組み合わせは後方互換性のため受け付けられ、continuation-only の正規形へ変換されます。繰り返し `body:` 値の後ろには continuation block を追加しないでください。この fail-loud な境界により、formatter、converter、editor integration、将来の LSP 操作が data model を黙って変えることを防ぎます。

## integration 向け検証 checklist

life.txt の editor formatter、importer、exporter、AI tool を作る場合、user data を書く前に次を検証してください。

- `tests/golden/roundtrip_cases.json` を parse し、再 serialize する。
- key が 1 回しか出ていない場合でも JSON/JSONL の detail values を array として保つ。
- interchange 中に明示的 timezone-offset strings を保つ。
- `body:first body:second` の後ろに `| continuation` が来た場合は `E022` で拒否する。
- 複数行値を含む繰り返し `body:` set は serialize せず raise する。

重要なのは、すべての surface が同一 whitespace を出力することではありません。どの surface も、書かれた値を黙って merge、drop、retarget しないことです。
