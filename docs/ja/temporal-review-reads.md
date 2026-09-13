# Temporal review の read surface

read-only の Personal Context CLI には、期間と上限を持つ3つの投影があります。

- `decision-review --format json`：明示的な `realizes:` リンクだけを追跡します。
- `change-feed --since OFFSET --until OFFSET --format json`：型付きの意味ある履歴変更だけを返します。
- `future-intent --cutoff OFFSET --until OFFSET --format json`：明示された未来時刻だけを返します。

Text と JSON は同じドメイン結果から生成されます。根拠がない状態を現在値から
推測することはありません。
