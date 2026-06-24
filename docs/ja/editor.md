# Editor Support

このプロジェクトには、VS Code 向けの基本的な editor support を
[`editors/vscode/lifetxt`](../../editors/vscode/lifetxt) に含めています。

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

より高度な補完は、Python parser / validator を再利用する optional language
server として実装する方針が適しています。

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
