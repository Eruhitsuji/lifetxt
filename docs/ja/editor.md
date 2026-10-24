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

静的支援は次の機能を提供します。

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

## 静的なFormat 1.0対応

9種類すべてに `task`、`event`、`deadline`、`reminder`、`habit`、`note`、`status`、`message`、`journal` のsnippetがあります。`do` は実施予定、`due` は締切です。日付のtabstopは `YYYY-MM-DD` と表示されるため、保存前に明示入力してください。過去の固定日付は挿入しません。titleと本文detailは引用符付き、`|` の本文は通常の文字列です。metadata、全参照key、末尾 `\` の継続記号もhighlightします。highlightは表示支援であり、検証ではありません。

`2026-W42.txt` のような週次ファイルは言語選択で **life.txt** を選ぶか、`files.associations` に `"2026-W*.txt": "lifetxt"` を明示してください。汎用 `*.txt` は関連付けません。静的支援にはPythonもLSPも不要です。

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

## 任意の言語サーバー（ローカル・読み取り専用）

lifetxtを導入した **Python 3.10以上** で `python -m lifetxt.lsp --stdio` を実行できます。
PythonのLSP追加依存は不要です。選択した環境へ明示的に導入してください（checkoutからは
`python -m pip install -e .`、またはこのmoduleを含むリリースを使用）。導入後はofflineで使えます。
serverは自動install、Core設定の読み込み、disk走査、symlink追跡、network送信、command実行、
life.txt書き込みを行いません。IDEの通常保存は直接保存です。上記 `safe_edit` はCLI/TUIの
一時コピー経由の編集を保護する契約です。

lifecycle、全文sync、version付き診断、UTF-16位置の補完、plaintext Hoverを提供します。
Core parser/validatorのcodeとseverityを再利用し、未対応Formatの宣言は既存Core policyの
`F110` で追加表示します。end span不明時は長さ0、論理行の位置は物理行へ変換します。
format-on-save、自動修正、code action、symbol、definitionは未提供です。
入力途中の引用符、title、comment、body、論理行継続の位置では補完を控えます。
custom keyは保持します。Hoverの説明は現時点で既存Coreの英語metadataを再利用します。

### VS Code（1.82以上）

静的支援は拡張directoryのコピーで使用できます。動的支援は任意のNode client依存が必要です。
`editors/vscode/lifetxt` で `npm ci --omit=dev --ignore-scripts` を明示実行してから、
production `node_modules` ごとコピーしてください。拡張自体はinstallを実行しません。
準備済みdirectoryはofflineで使用できます。Marketplace公開は含みません。

VS Codeのユーザー設定例:

```json
{
  "lifetxt.languageServer.enabled": true,
  "lifetxt.languageServer.python": "/absolute/path/to/python"
}
```

Windowsでは `"C:\\Python312\\python.exe"` のように実行ファイルだけを指定し、引数を含めません。
Remote Developmentではdesktop側でなく **extension host側** のPythonです。
対象は `file` と `untitled` bufferで、virtual URI providerは静的支援のみです。
設定変更後はwindowをreloadしてください。起動失敗時は警告とlife.txt outputを確認し、
指定環境へlifetxtを導入してreloadします。Python/client依存がなくても静的機能は使えます。
信頼されていないworkspaceでは有効設定にかかわらず静的支援のみです。

| 拡張設定 | 型・既定値 | scope・正本 | 反映・秘密・互換性 |
| --- | --- | --- | --- |
| `lifetxt.languageServer.enabled` | boolean / `false` | VS Code window設定、trusted workspaceのみ | reloadが必要、秘密情報ではない、0.2.0追加、無効化で静的支援へ戻る |
| `lifetxt.languageServer.python` | string / `python` | VS Code machine/user設定、実行ファイルのみ | reloadが必要、秘密情報ではない、0.2.0追加、対応するlifetxtを導入した環境を指定 |
| `lifetxt.languageServer.idKey` | string / `id` | VS Code window設定、Coreの `ids.key` と明示的に合わせる | reloadが必要、秘密情報ではない、0.2.0追加、旧拡張は無視、既定動作へ戻す場合は `id` |

正本は拡張manifestです。Core設定schemaの項目ではないため `lifetxt config explain` の対象外で、
Core設定migrationもありません。旧拡張は設定を無視します。このmoduleを含まないlifetxtへ
downgradeする前にLSPを無効化してください。解除は設定を無効にし、コピーした拡張directoryを
削除してreloadします。

### Neovim（0.11以上）

信頼する `init.lua` から [`editors/neovim/lifetxt.lua`](../../editors/neovim/lifetxt.lua) を
明示的に読み込み、`python` を導入先interpreterへ変更します。組込の
`vim.lsp.config` / `vim.lsp.enable` を使い、lspconfig pluginは不要です。
週次ファイルは `:setfiletype lifetxt`。停止は `vim.lsp.enable('lifetxt', false)`、
解除は設定の削除です。通常のテキスト運用にPythonは不要で、LSPを使う場合のみ必要です。

### 上限・互換性

最大32文書、文書あたりUTF-8で256KiB、補完・診断200件、frame 2MiB、header 8KiBです。
古いversionの変更通知と差分syncを受理しません（全文syncを宣言します）。
文書が拒否された場合はclient logを確認し、close/openで再同期してください。
最後の有効snapshotを保持しますが、その文書の診断・補完・Hover・他bufferへの候補/参照解決への参加を一時停止します。
拒否されたversionより新しい有効な全文通知でも復帰します。同じか古いversionでは復帰しません。要求は同期実行し、client側debounceで通知頻度を抑えます。
cancelは既に開始したCore解析を中断しません。背景走査、telemetry、自動編集はありません。

## 開いているbufferのworkspace・展開状況

同じserver sessionで明示的に開いたlife.txt bufferは、未保存のID、project、tag、personなどを
Core補完候補として共有します。closeで候補を除外し、残る文書の参照診断を更新します。
rootやfile URIは識別子として扱うため、folderを開くだけではdisk走査しません。
同じclient sessionの複数rootも共有範囲に入ります。候補を共有したくない文書は別window/
server sessionに分けてください。開いていないファイルのIDは参照解決に使えません。

Coreの `ids.key` を変更している場合は、VS Codeで `lifetxt.languageServer.idKey` を明示し、
Neovimでは `cmd` に `--id-key uid` などを追加します。Core設定を暗黙に読み込みません。
未対応Formatの文書は現行文書のID候補へ混ぜません。非常に深い参照graphはadapter診断
`LSP001` を表示します。この場合も構文診断は使えますがgraph検証は未完了です。
参照chainを簡単にするか、無関係なbufferを閉じてください。元の文書は変更しません。

| 対象 | 提供内容 | 検証・残る境界 |
| --- | --- | --- |
| 通常のテキストエディタ | 従来のtemplate・最小文法・手動運用 | Python/LSP/network不要 |
| VS Code静的（1.80以上） | 全Type・snippet・関連付け・TextMate grammar | Core生成確認と実際のTextMate/Oniguruma corpus |
| VS Code動的（1.82以上） | 任意client、診断・補完・Hover | Microsoft protocol・host doubles確認済み、GUI/Windows/macOS受入は#1373 |
| Neovim（0.11以上の設定API） | 組込LSP設定 | Linuxの実際の0.12.6で共通fixtureを確認、0.11/他OS未実施 |
| Zed | 未対応 | metadata・Tree-sitter grammar/queries・拡張adapterを要調査 |
| Sublime Text | 未対応 | syntaxとcommunity LSP clientの設定・受入が必要 |
| JetBrains | 未対応 | 対象IDE/API対応版・plugin設計を決めてから検証 |

## Windows向け正式Editorサポート・リリース配布物（#1389）

**公式のEditor入力補助対象はWindows版VS Code / Neovim（nvim）のみ**です。
VS Codeは静的機能が1.80以上、任意のLSPは1.82以上、Neovimは0.11以上を対象とします。
この範囲はEditorの支援機能のみに適用し、Core/CLI/ServerのOSサポート方針は変更しません。
通常Vim/Vim9、Linux/macOSのEditor実機保証、Marketplace/Open VSXは対象外です。

既存の人間承認付きRelease CIは、同一のlifetxt Release版/source SHA/チェックサムに
対応する次の2ファイルをGitHub Releasesに添付する設計です。

- `lifetxt-vscode-<lifetxt-version>.vsix`
- `lifetxt-neovim-windows-<lifetxt-version>.zip`

**実際に正式Release Authority承認と公開が済むまではダウンロード可能と断定できません。**
preflight生成・PRのmergeは正式公開ではありません。
拡張内の3要素版（現状`0.2.0`）とlifetxt本体の`X.Y.Z[.N]`は独立し、
両ZIP内の`release.json`でsource SHA・候補digest・両版を結び付けています。
導入前に同じReleaseの`SHA256SUMS`とファイルのハッシュを確認してください。

### VS Code VSIX導入（Windows）

1. 対象ReleaseからVSIXと`SHA256SUMS`を取得します。PowerShellの
   `Get-FileHash .\lifetxt-vscode-*.vsix -Algorithm SHA256`で照合します。
2. VS Code → 拡張機能 → `...` →「VSIXからのインストール」、
   または`code --install-extension .\lifetxt-vscode-<version>.vsix`を実行します。
3. 再起動後に`life.txt`を開いて言語モードを確認します。
   静的highlight/snippetはPython無しで使え、LSPは既定で無効です。
4. 診断・補完・Hoverを使う場合のみPython 3.10以上の環境へlifetxtを
   **明示的に導入**し、VS Code設定で
   `lifetxt.languageServer.enabled=true`、
   `lifetxt.languageServer.python`に導入先Python実行ファイルの絶対パス
   （JSON中のバックスラッシュはエスケープ）を設定してウィンドウを再読み込みします。
   Python実行設定に引数を含めません。IDキーを変更している場合は
   `lifetxt.languageServer.idKey`を明示します。
5. 静的機能へ戻す場合は`enabled=false`にして再読み込みします。
   削除する場合は拡張機能から「アンインストール」、または
   `code --uninstall-extension lifetxt.lifetxt`を実行します。
   `lifetxt.lsp`を持たない旧本体へ戻す前にLSPをOFFにしてください。
   Python/LSP不具合時にも静的編集は可能です。

### Neovim設定導入（Windows）

1. 対象Releaseから同版のZIPとSHA256SUMSを取得・照合し、
   `lifetxt.lua`、`release.json`、`INSTALL-WINDOWS.md`を安全に展開します。
2. Luaを確認して`cmd`のPython実行ファイルを変更し、自分の`init.lua`へ
   `dofile([[C:\path\to\lifetxt.lua]])`を**手動で追加**します。
   Neovim built-in LSPを利用するため、追加LSP pluginは不要です。
   LSPを使う場合のみPython環境へlifetxtを別途導入してください。
3. Neovimを再起動して`life.txt`を開きます。週次の`.txt`は
   `:setfiletype lifetxt`を指定します。LSP停止は
   `:lua vim.lsp.enable('lifetxt', false)`です。
   元に戻すときは`init.lua`の追加した`dofile`行だけを削除し、
   展開先を削除して再起動します。他の設定を上書きしません。

[#1373](https://github.com/Eruhitsuji/lifetxt/issues/1373)にはWindows実機の
VS Code/Neovim主要動作の受入結果が記録されていますが、一部のpath・Unicode・
offline・再接続の組合せや追加試験は**未実施**です。CIによるパッケージ検査は
全実機条件のPASSを意味しません。LSPが失敗しても無効化して静的/手動編集を継続できます。

Marketplace/外部registryへの公開は対象外です。symbol/definition/actionや
disk workspace探索は未提供です。

性能の回帰確認は同じPython/OS/machineで
`python -m editors.benchmark_lsp > baseline.json`、続いて
`python -m editors.benchmark_lsp --baseline baseline.json --max-ratio 2` を実行します。
1,000件・2bufferのCore解析、圧縮位置map、参照診断、補完をtracemalloc付きで測定します。
Linux/Python 3.12で初期中央値約137ms、Python割当peak約4.3MBでした。
この環境の観測値であり、他環境で同じ速度を保証するものではありません。
