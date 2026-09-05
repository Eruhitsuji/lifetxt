# lifetxt 1.0.2 Release Notes

`1.0.2` は `1.0.1` 後の小さな usability patch release です。
[#664-#668](https://github.com/Eruhitsuji/lifetxt/issues/669) で実装され
[PR #670](https://github.com/Eruhitsuji/lifetxt/pull/670) で merge された、
5つの daily single-item CLI convenience の batch を完成させます。Format
1.0 の記法、public API、schema、storage の behavior は変更されていません。

## Highlights

- **`lifetxt reopen PATH [ID]`**（[#664](https://github.com/Eruhitsuji/lifetxt/issues/664)）--
  item の completion を取り消します: `done:` を削除し、`clone` が新しい
  item に与えるのと同じ kind-aware な open/default status に戻します。
  既に open な item は確定的な no-op です。Habit records は completion を
  単一の completed state ではなく複数の `done:` 日付として記録するため、
  代替手段を示して拒否されます。
- **`lifetxt progress PATH ID --set VALUE`**（[#665](https://github.com/Eruhitsuji/lifetxt/issues/665)）--
  `progress:`（percentage または fraction）を直接設定します。既存の
  `--delta` 増減とは互いに排他的です。`--delta` と異なり、`--set` は
  既存の `progress:` 値が無くても動作します。加減算の起点を必要としない
  ためです。
- **`lifetxt due PATH ID DATE`** / **`--clear`**（[#666](https://github.com/Eruhitsuji/lifetxt/issues/666)）--
  `done`/`progress`/`clone` と同じ guarded mutation path を通じて、item
  の `due:` 値を設定・置換・削除します。
- **範囲を限定した相対日付 shorthand**（[#667](https://github.com/Eruhitsuji/lifetxt/issues/667)）--
  `due` の `DATE` 引数（および `quick`/`add` の既存 `--due`/`--do`/
  `--until` flag）は、`today`、`tomorrow`、`yesterday`、曜日名、
  `next_week`、`+3d`/`-1w`/`+2m`/`+1y` のような signed offset を、単一の
  確定的な resolver を通じて解決します。**これは CLI 入力の convenience
  のみです**: 解決は command-line の境界で行われ、`life.txt` に実際に
  書き込まれる値は常に解決済みの canonical な絶対日付です（例:
  `due:tomorrow` ではなく `due:2026-09-09`）。Format 1.0 自体には新しい
  記法が一切追加されず、Web API・MCP・その他の machine-readable な
  surface にも相対日付の semantics は一切追加されていません。
- **`lifetxt recent PATH`**（[#668](https://github.com/Eruhitsuji/lifetxt/issues/668)）--
  最近作成・更新された item の read-only、newest-first な view です。
  既存の parsing、short ID、relative-time 表示を組み合わせたもので、
  default では `updated:` を基準とし、`created:` に fallback します。
  `--updated`/`--created` はどちらか一方の基準を fallback なしで
  明示的に選択します。

完全な command reference と例は [cli.md](cli.md#1313-reopen)（および
続く `due`/`recent` の節）と
[new-cli-workflows.md](new-cli-workflows.md) を参照してください。

## Compatibility

破壊的変更はありません。5つのコマンドはすべて、既存の guarded
mutation・target-resolution・read primitive を再利用する新規の
additive surface です。既存コマンドの default behavior、output shape、
machine-readable contract はいずれも変更されていません。

## Upgrading

migration は不要です。`1.0.1` に対して動作していた既存の `life.txt`、
config、script は `1.0.2` でも変更なく動作します。

## Release status

- **`v1.0.2`**: この release-preparation commit で準備されました
  （完全な準備・公開チェックリストは
  [#669](https://github.com/Eruhitsuji/lifetxt/issues/669) 参照）。
  version metadata は `pyproject.toml`/`lifetxt/__init__.py` で
  `1.0.1` -> `1.0.2` に bump され、MCP server と Web API の version
  surface はどちらも `lifetxt.__version__` から derive されており、
  tag 作成前に `1.0.2` を報告することを確認済みです。

## Installation smoke

```text
python -m lifetxt --help
lifetxt --help
python -m lifetxt check examples/minimal_life.txt
```

[#454](https://github.com/Eruhitsuji/lifetxt/issues/454) で確立された
reduced Stable-release gate をこの patch release でも再利用します:
release-critical な最小要件は、`1.0.0`/`1.0.1` について
[Stable Release Artifact Verification](stable-release-artifact-verification.md)
に記録されているのと同じ、clean な wheel/sdist の build、fresh
environment への install、representative な core smoke です。
