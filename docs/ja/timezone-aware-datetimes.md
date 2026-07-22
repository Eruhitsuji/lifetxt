# タイムゾーン付き日時の保持

この文書は、共通日時ユーティリティが保証する明示的オフセットの保持規則を説明します。対象は完全な日時値です。naive値、ファイルディレクティブ、設定、CLIオーバーライドの優先順位は、別のロードマップ項目として定義します。

## 解析

明示的なオフセットを持つ日時は、解析後もtimezone-awareのままです。

```python
from lifetxt.timeutil import parse_datetime

value = parse_datetime("2026-07-22T09:30:15.25+09:00")
assert value.utcoffset().total_seconds() == 9 * 60 * 60
```

`Z` はUTCとして解析します。`+0900` のようなコロンなしのオフセットも受け付け、出力時には `+09:00` へ正規化します。オフセットがない日時はnaiveのままです。

## フォーマット

`format_datetime` はオフセット、秒、小数秒を保持します。

```python
from lifetxt.timeutil import format_datetime, parse_datetime

value = parse_datetime("2026-07-22T09:30:15.25+09:00")
assert format_datetime(value) == "2026-07-22T09:30:15.25+09:00"
```

`Z` を解析した値をフォーマットすると、同じUTCを表す正規形 `+00:00` を出力します。life.txt内の元のdetail文字列は、読み込みや交換形式への変換だけでは書き換えません。

## JSON・JSONL・CSV

日時detailは、Itemモデルと交換形式では文字列として保持します。そのため、次の値はJSON・JSONL・CSVを往復しても変化しません。

```text
from:2026-07-22T09:30:15.25+09:00
```

フィルタリング、validation、agenda計算、timer計算、recurrence処理のために日時を解析しても、オフセットを破棄する必要がなくなりました。

## 比較時の互換性

以前のlifetxtは、aware日時を解析直後に実行環境のローカル時刻へ変換し、`tzinfo` を削除していました。この実装ではaware値を保持し、比較または減算するときだけ従来と同じローカルnaive表現へ変換します。

`comparison_datetime(value)` を使用すると、比較専用の値を明示的に取得できます。表示やシリアライズでは元のaware値を使用してください。

```python
from lifetxt.timeutil import comparison_datetime, parse_datetime

aware = parse_datetime("2026-07-22T09:30+09:00")
local_comparison_value = comparison_datetime(aware)
assert aware.utcoffset() is not None
assert local_comparison_value.tzinfo is None
```

agenda、validation、timerなどの既存処理では、awareとnaiveが混在する比較・減算を引き続き行えます。ただし、この互換処理はnaive値の意味を決定するものではありません。naive値の扱いは `#! timezone:`、`defaults.timezone`、CLIオーバーライド、表示変換、フィルタ、完了日の境界規則とまとめて定義します。

## 時刻だけの値

今回の実装範囲は完全な日時値です。`at:09:30+09:00` のような時刻だけの値は、タイムゾーン優先順位を定義するまで従来のローカル比較動作を維持します。
