# Editor Support

## Latest Format Coverage

現在の VS Code extension は、最新の format profile に含まれる item type を
highlight 対象にします。

```txt
T E D R H N S M J
```

title は detail value とは別 scope で capture されるため、theme 側で title、
detail key、quoted string を別色にできます。snippet は `status`、`message`、
`journal`、`repeat-limited`、`dtz` などを含み、`S`、`M`、`J`、複数行 `body:`、
秒・小数秒・timezone 付き datetime、simple repeat の制限 key に対応します。

このプロジェクトには、VS Code 向けの基本的な editor support を
[`editors/vscode/lifetxt`](../../editors/vscode/lifetxt) に含めています。これとは別に、
CLI・TUI・`fzf`/`peco` の選択結果を任意の外部 editor で安全に開くための
code-level な仕組みもあります。この文書の後半、「CLI からの編集: `lifetxt edit`」
以降で説明する内容で、VS Code extension には依存しません。

## 現在の範囲

現時点では軽量な static extension として実装しています。

- コメント、item 開始、status、type、title、detail key、quoted string、日時、
  body 継続行、ID 参照の TextMate syntax highlight
- よく使う item type と detail key の VS Code snippet
- `life.txt`、`*.life.txt`、`*_life.txt`、`.life.txt`、`.lifetxt` の file association

background process を起動しないため、ローカル環境へコピーするだけで使えます。

## ローカルインストール

Windows 例:

```powershell
$target = "$env:USERPROFILE\.vscode\extensions\lifetxt"
New-Item -ItemType Directory -Force $target
Copy-Item -Recurse -Force .\editors\vscode\lifetxt\* $target
```

コピー後に VS Code を reload してください。この workspace には
`.vscode/settings.json` も含め、`*_life.txt` を `lifetxt` 言語へ関連付けます。
`editors/vscode/lifetxt` を VS Code で開き、`F5` で Extension Development Host
を起動して試すこともできます。

## 補完方針

static snippet では以下を提供します。

- `task`、`event`、`status`、`message`、`journal`、`habit`
- `subtask`、`body`、`ibody`
- `id`、`parent`、`depends_on`、`blocks`
- `due`、`fromto`、`dtz`、`project`、`tag`

snippet は現在の format profile に合わせています。

- `status` は type `S` と `from:`、`state:`、`person:` を挿入します。
- `message` は type `M` と `sender:`、`recipient:`、`notify_at:`、`body:` を挿入します。
- `journal` は type `J` と `|` body continuation line を挿入します。
- `repeat-limited` は `repeat:`、`interval:`、`until:`、`count:` を挿入します。
- `dtz` は秒、小数秒、timezone 付き datetime を挿入します。

より高度な補完は、Python parser / validator を再利用する optional language
server として実装する方針が適しています。

## CLI からの編集: `lifetxt edit`

TUI の `/edit` コマンドや `fzf --action edit`
（[`cli.md`](./cli.md) の 13.1 `tui` と 13.2 `fzf` を参照）とは別に、
lifetxt には 1 item の source file を外部 editor で開くための独立した
command があります。

```sh
python -m lifetxt edit t1 life.txt --show-diff
```

```txt
python -m lifetxt edit ID [paths ...]
  --editor CMD    この実行だけ EDITOR/VISUAL/config を上書きする
  --dry-run       解決した editor command を表示するだけで起動しない
  --review-only   一時コピーを開き、適用せずに diff を表示する
  --reconcile     editor を開いている間の外部変更のうち重なりのないものを保守的にマージする
  --keep-temp     編集済みの一時コピーを手動復旧用に残す
  --show-diff     編集適用後に diff を表示する
```

`ID` は `lifetxt show` や `lifetxt next` と同じ方法で解決されます。見つから
ない場合は editor を起動せずに error で終了します。`--dry-run` は一時ファイル
を使わず、lifetxt が実行する実際の argv をそのまま表示します。見慣れない
`EDITOR` 値がどう解決されるか確認するのに便利です。

```console
$ EDITOR=code python -m lifetxt edit t1 life.txt --dry-run
code -g 'C:\path\to\life.txt:1'
```

`--review-only` と `--show-diff` はどちらも `difflib.unified_diff` が生成する
unified diff を表示します。書き込み前後それぞれのタイミングで、
`--review-only` は書き込まずに diff だけを示し、`--show-diff` は書き込んでから
何が変わったかを示します。scripted な代替 editor で検証済みです。
`--review-only` は source file を 1 byte も変えずに、一時コピー内で editor が
行った変更を正しく報告しました。同じ編集を `--review-only` なしで再実行すると、
適用したうえで同じ diff を表示しました。

## editor 安全性契約

`lifetxt edit`、`fzf --action edit`、TUI の `/edit` はいずれも
`lifetxt.editor_safety.safe_edit` という 1 つの関数を経由し、`life.txt` を
直接開くことはありません。この関数がこの文書の言う「delegated-mutation-proposal
contract」です。editor は信頼できない長時間動作の外部プロセスとして扱われ、
その出力は次の 3 つの検査を通過して初めて信頼されます。

1. **source ではなくコピーを編集する。** `safe_edit` は source file を新しい
   一時ディレクトリ（`lifetxt-edit-*`）へコピーし、editor にはそのコピーを
   渡します。editor process がクラッシュしたり、応答しなくなったり、未保存の
   まま閉じられたりしても、`life.txt` には一切触れません。
2. **書き込み前に検証する。** editor が終了すると、一時コピーは
   `lifetxt.parser.parse_text` で解析されます。editor session の結果が構文的
   に不正な場合、書き込み処理には到達せず、parse error が報告されます。
3. **revision を検査したうえで書き込む。** 元の読み込みと最終的な書き込みは、
   どちらも他の lifetxt の書き込みと同じ revision 検査付き mutation 経路
   （`lifetxt.mutation`）を通ります。editor を開いている間に `life.txt` が
   外部で変わっていた場合、`--reconcile` なしの通常経路は `MutationConflict`
   で即座に失敗し、期待した revision と実際の revision を報告して何も
   書き込みません。source file を "外部から" 同時に変更する scripted editor
   で実際に確認済みです。

### 競合解消（`--reconcile`）

`--reconcile`（`lifetxt edit` のみが対応。`fzf --action edit` と TUI は常に
変更があれば失敗する通常経路を使います）は拒否する代わりに保守的な
three-way merge を試みます。元の text と、editor の結果・file の現在の
on-disk 内容の両方を diff し（`difflib.SequenceMatcher`）、2 つの変更行範囲
が重ならない場合のみ merge を受け入れます。重なる場合は、どちらを優先するか
推測せず、重なった範囲を明示して `EditorReconcileConflict` を送出します。

```text
The editor and source changed the same line range (1:2).
```

この検査は実際に触れた field ではなく `difflib` の diff hunk 単位で行われます。
実際に検証したところ、文字通り同じ行ではなく隣接する行を編集しただけでも
重なりとして報告されました。`SequenceMatcher` が近接した変更を 1 つの hunk
にまとめてしまうためです。`--reconcile` は「file 内で明らかに離れた編集を
マージする」機能であり、行単位の精密な merge ではないと考えてください。

### `--keep-temp` と復旧

`--keep-temp` は command 終了後も一時ディレクトリを削除せず、そのパスを
表示します。`--review-only` と組み合わせると、`life.txt` に一切書き込む
ことなく editor session を確認・手動で復旧する手段になります。何も適用され
ず、編集済みコピーは手動で diff したりコピーしたりできる状態でディスクに
残ります。

### 呼び出し元によって default editor の解決が異なる

どちらの呼び出し元も `EDITOR`、次に `VISUAL`、次に config file の `editor`
key を順に探します（正確な解決順序、`PATH` 経由の実行ファイル解決、editor
ごとの行番号引数の書式は [`cli.md`](./cli.md) の「Choosing an editor」
節を参照してください）。**どれも設定されていない場合** の挙動は異なります。

- `fzf --action edit` と TUI の `/edit`（`lifetxt.fzf_helper.resolve_editor`）
  は `None` を返し、`cli.md` に記載されている "No editor configured" と
  同じ message で失敗します。
- `lifetxt edit`（`lifetxt.extra_core.command_edit` の `_resolve_editor`
  helper）は代わりに固定の default にフォールバックします。Windows では
  `notepad`、それ以外では `vi` です。`EDITOR`/`VISUAL` を未設定にした状態で
  `lifetxt edit --dry-run` を実行し、error にならず実行可能な command が
  表示されることを確認済みです。

特定の editor を使いたい場合は、`lifetxt edit` の fallback に依存せず、
`EDITOR`/`VISUAL`（または config の `editor` key）を明示的に設定してください。
この fallback は `fzf`/TUI の編集とは異なり、`--editor` 以外では実行ごとに
変更できません。

## 今後の language server 候補

将来的な LSP では以下を提供できます。

- `python -m lifetxt check` 相当の diagnostics
- type / status に応じた detail-key completion
- `parent:`、`ref:`、`depends_on:`、`blocks:`、`related:` の ID completion
- 仕様書由来の hover help
- type、project、tag、hierarchy ごとの document symbols
- `links`、`agenda`、`status`、ID 付与の command / code action

static extension は dependency-free に保ち、動的機能は optional language-server
package に分離すると、CLI ユーザや単なる plain text ユーザに editor 依存を強制せずに済みます。
