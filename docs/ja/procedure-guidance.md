# 人間向け手順書の運用

繰り返し使う手順の定義と、毎回の実施記録を分けます。実施記録のチェックを完了しても、
共通テンプレートの状態は変更しません。許可されたテキストエディタだけでも読める運用です。
基本的な日次・週次管理は[テキストエディタのみの運用](text-editor-only-workflow.md)を参照してください。

## テキストエディタだけで使う

[procedure-template-ja.txt](../../examples/procedure-template-ja.txt)と
[procedure-work-ja.txt](../../examples/procedure-work-ja.txt)を別のファイルとして開きます。
前者は通常の`[N] N`、ID、parent、bodyだけで、点検→バックアップ→更新→確認、失敗時の手動復旧を
説明します。後者は実施ごとに一意のTask IDを持ち、1回目は完了、2回目はバックアップ中断中です。
テンプレートのIDや状態は変更しません。

1. bodyの説明を順に読み、`id:`で手順を検索します。
2. 実施のたびに作業記録を新しいTask IDで作ります。`ref:`はテンプレートのstepを指し、前回の結果と共有しません。
3. 着手で`[ ]`→`[/]`、自分で確認して完了したら`[x]`にします。
4. 中断時は`[/]`と残作業のbodyを残します。未確定の前提・判断は`[?]`にします。
   再開前にメモを読み、現在の状況を自分で確認します。自動再開やtimerはありません。
5. yes/noの判断結果を手書きします。確認に失敗したら復旧手順を読み、人間が実施して再確認します。

機械的な条件判定・自動作業・通知・構造化されたrun証跡はありません。開発用ツールが使える環境なら、
`python -m lifetxt check examples/procedure-template-ja.txt examples/procedure-work-ja.txt`
で通常のFormat 1.0構文とファイル間の参照を確認できます。作業記録だけをcheckすると、テンプレートへの
参照が未解決の警告になることがあります。秘密情報や職場で保存が許可されない情報は書かないでください。

## CLIの定義閲覧・フローチャート

機械的な手順表示には、別のopt-in例
[procedure-flow-ja.txt](../../examples/procedure-flow-ja.txt)を使います。

```sh
python -m lifetxt procedure show examples/procedure-flow-ja.txt --id r
python -m lifetxt procedure graph examples/procedure-flow-ja.txt --id r --format text
python -m lifetxt procedure graph examples/procedure-flow-ja.txt --id r --format mermaid
python -m lifetxt procedure graph examples/procedure-flow-ja.txt --id r --format dot
```

`show`は本文・階層・選択肢を表示します。`graph`は同じ遷移をtextまたは図のソースとして出力し、
外部描画サービスは呼びません。例には脱出口のある再試行loopがあり、stderrにPG201警告、stdoutには
図だけを出します。不正な定義では非0終了し、stderrへcodeと元の行番号を出して、途中の図は出しません。
ログの作成・実作業・URL起動・Task状態変更・run完了は行いません。

明示した単一の通常UTF-8ファイルとroot IDが必要です。空白を含むpathは引用符で囲みます。
stdin・glob・directory・workspaceの展開はせず、代替id-key設定も拒否します。定義は`[N] N`です。

| 属性 | 意味 |
| --- | --- |
| `proc_role:root proc_version:1 proc_start:STEP` | rootと単一の入口 |
| `proc_role:step parent:ROOT proc_kind:action proc_next:STEP` | 次のstepを一つ持つ作業説明 |
| `proc_kind:decision proc_case:yes=A proc_case:no=B` | 人間の明示選択を2〜16個。式は評価しない |
| `proc_kind:end` | 出辺のない明示終端 |

各レコードは安全な`id:`を一つ持ち、同じroot内でparent階層を作れます。表示順はファイル順で、
実施順とは区別します。選択ラベルは小文字ASCIIトークンで大文字小文字を区別します。
欠損遷移先・ID/ラベル重複・未知proc_*・到達不能step・parent循環・endに到達する経路のないstepは
エラーです。脱出口のあるloopは閲覧時に警告し、将来のrunでは明示確認と有限guardを要求します。

一般の`check`ではproc_*は従来通り独自属性のW106警告となり、手順の意味は検証しません。
そのため`--warnings-as-errors`ではopt-in例は失敗します。一般の変換は属性を保持します。
`links`・`flow`・`vm`・`depends_on`・`follows`・通常の`next`の意味は従来通りです。

上限は入力10 MiB/10,000レコード、選択500 step/2,000辺、parent深度32、各レコードbody 64 KiB、
出力2 MiB。制御文字はデータとしてescapeし、図のnodeは独立した連番IDで衝突を避けます。
入力バイト列の完全なSHA-256を内部に保持します。この段階に公開JSON投影/schemaやrunコマンドはありません。

[承認済み設計](procedure-guidance-design.md)にあるrun/event/CAS・Webは後続段階の計画です。
