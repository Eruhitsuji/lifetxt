# 往復変換と複数行bodyの規則

この文書は、参照パーサーとシリアライザーが保証するロスレスな規則を説明します。実行可能な例は `tests/golden/roundtrip_cases.json` にあり、`tests/test_roundtrip_golden.py` が検証します。

## parse→serialize→parse契約

有効なlife.txt文書について、参照実装は次を満たす必要があります。

1. エラー診断なしで入力を解析する。
2. 解析した各項目を正規化されたlife.txtへシリアライズする。
3. 正規化後のテキストを再びエラー診断なしで解析する。
4. status、type、title、indent、detail key、繰り返し値の順序、detail valueを同一に復元する。

正規シリアライザーはLF改行を書き出します。読み込み時はLF、CRLF、CRを受け付けます。UTF-8、Unicodeのtitle/value、引用符のエスケープ、繰り返しdetail、階層、明示的なタイムゾーンオフセット文字列をゴールデンコーパスで検証します。

JSONとJSONLでは、すべてのdetailを配列として保持します。CSVでは、繰り返し値をJSON配列形式のセルとして保持します。`+09:00` のような明示的オフセットは、JSON・JSONL・CSVの往復中にdetail文字列の一部として保持されます。日時比較処理は解析後の値を別途正規化できますが、交換形式が記述された値を書き換えてはいけません。

## 1つの継続ブロックは1つのbody値を表す

`|` で始まる一連の行は、1つの複数行 `body:` 値を表します。

```txt
[N] J "Research log" on:2026-07-22
| First paragraph.
|
| Third line after a blank line.
```

解析後のbody値は次の内容です。

```text
First paragraph.\n\nThird line after a blank line.
```

項目に改行を含む `body:` 値が1つだけある場合、シリアライザーはこの継続形式を使用します。

後方互換性のため、インラインの `body:` 値が1つだけの場合は、その後に継続行を記述できます。

```txt
[N] N Note body:First_line
| Second line
```

追記対象が1つに定まるため、これは `First_line\nSecond line` として解析されます。正規化してシリアライズすると、インラインdetailを除き、継続行だけの形式になります。

```txt
[N] N Note
| First_line
| Second line
```

## 明示的に拒否する形式

繰り返されたインライン `body:` detailの後に継続ブロックを記述してはいけません。

```txt
[N] N Note body:first body:second
| ambiguous continuation
```

この継続行が `first`、`second`、新しい値のどれに属するかを示す境界記号がないため、パーサーは継続行の位置にエラー `E022` を報告し、繰り返しインライン値は変更しません。

継続ブロックを伴わず、すべてが1行である繰り返しbody値は有効です。

```txt
[N] N Note body:first body:second
```

一方、複数の `body:` 値のいずれかが複数行である場合はシリアライズできません。`|` 構文には繰り返し値どうしの境界を表す記号がないため、シリアライザーは値を平坦化・結合せず `ValueError` を発生させます。

## 記述時の指針

次のいずれかを使用してください。

- 短い値を1つだけインラインで記述する: `body:short_text`
- すべてが1行であり、その後に `|` ブロックを置かない場合に限り、インラインの `body:` を繰り返す
- 複数行値を1つの継続ブロックで記述する

単一のインライン値と継続行の組み合わせは後方互換性のため受け付け、継続行だけの正規形へ変換します。繰り返し `body:` 値の後には継続ブロックを追加しないでください。このfail-loud境界により、フォーマッター、コンバーター、エディター連携、将来のLSP操作がデータモデルを暗黙に変更することを防ぎます。
