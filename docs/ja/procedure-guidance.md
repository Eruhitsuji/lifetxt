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
エラーです。脱出口のあるloopは閲覧時に警告し、runの開始では明示確認と有限guardを要求します。

一般の`check`ではproc_*は従来通り独自属性のW106警告となり、手順の意味は検証しません。
そのため`--warnings-as-errors`ではopt-in例は失敗します。一般の変換は属性を保持します。
`links`・`flow`・`vm`・`depends_on`・`follows`・通常の`next`の意味は従来通りです。

上限は入力10 MiB/10,000レコード、選択500 step/2,000辺、parent深度32、各レコードbody 64 KiB、
出力2 MiB。制御文字はデータとしてescapeし、図のnodeは独立した連番IDで衝突を避けます。
入力バイト列の完全なSHA-256を内部に保持します。公開JSON投影/APIは追加せず、ローカルrunコマンドは以下で説明します。

[承認済み設計](procedure-guidance-design.md)に沿ったrun/event/CASは以下で説明し、Webは後続計画です。

## ローカルでの実行案内と証跡

`procedure run`は人間の明示操作に従って手順を案内します。記載した保守作業・コマンド/URL起動・
HTTP/MCP送信・Note定義や通常Taskの変更は行いません。開始ごとに新しいrun IDを作り、状態は独立します。
別の実施ログ内のNative `record:procedure_event`だけを正本とし、順序付きイベントから状態を復元します。
更新可能な状態ファイルは作りません。既存のtransaction journalは復旧資料であり、別の実行状態正本ではありません。

まず定義とログの完全revisionを確認します。run IDを省略した`show`は当該source/rootの実行一覧と開始stepを
表示します。存在しないログは作成しません。ログの親directoryは事前に用意してください。

```sh
python -m lifetxt procedure run show examples/procedure-flow-ja.txt --id r --log runs.txt
python -m lifetxt procedure run start examples/procedure-flow-ja.txt --id r --log runs.txt --actor local --request-id start-001 --template-revision TEMPLATE_SHA --log-revision "<missing>" --step a --sequence 0 --allow-loops
```

`TEMPLATE_SHA`は表示されたTemplate revisionに置き換えます。例には脱出口のある再試行loopがあるため、
`--allow-loops`で明示確認します。確認しても1,000遷移/同じstepへの20回訪問の上限は緩和しません。
既存ログへ追加するときは`<missing>`の代わりに完全なLog revisionを渡します。
開始すると新しいRun ID、Sequence 1、現在の作業説明を表示します。
`--actor`はローカルの記録用トークンであり、**認証ではありません**。アクセス境界はローカルのファイル権限です。

以後も操作前に読み直し、作業説明と前提を確認します。

```sh
python -m lifetxt procedure run show examples/procedure-flow-ja.txt --id r --log runs.txt --run-id RUN_ID
python -m lifetxt procedure run next examples/procedure-flow-ja.txt --id r --log runs.txt --run-id RUN_ID --actor local --request-id next-001 --template-revision BOUND_SHA --log-revision LOG_SHA --step a --sequence 1
python -m lifetxt procedure run choose examples/procedure-flow-ja.txt --id r --log runs.txt --run-id RUN_ID --actor local --request-id choice-001 --template-revision BOUND_SHA --log-revision NEW_LOG_SHA --step q --sequence 2 --choice yes
```

`RUN_ID`、`BOUND_SHA`、`LOG_SHA`、`NEW_LOG_SHA`、stepとsequenceは最新の確認済み出力で置き換えます。
Bound template revisionは開始時の値を保ち、Log revision/Sequenceはイベント確定ごとに変わります。
これらの前提を自動更新・自動retryしません。選択は大小文字を区別した完全一致で、stdin入力や既定選択はありません。
actor/request IDは先頭が英数字、以後が英数字・underscore・dot・hyphenの1〜64文字です。
request IDはログ全体で一意にしてください。

| 操作 | 許可される状態・結果 |
| --- | --- |
| `next` | activeのactionから一辺進む |
| `choose --choice TOKEN` | activeのdecisionから明示した辺だけ進む |
| `pause` | active→paused。同じstep・訪問回数を維持 |
| `resume` | paused→active。同じstepへ再開し、元の定義revision一致が必要 |
| `finish` | activeのend→completed。endへ到達しただけでは完了しない |
| `abandon` | active/paused→abandoned。履歴は保持 |

すべての書込みで同じactor/request/revision/step/sequence指定が必要です。
戻る/undoは設けず、やり直すなら別runにします。completed/abandoned後は閲覧だけ可能です。
不正操作・古いform・未知choiceはstderr診断と非0終了で拒否し、成功出力やイベントを追加しません。
遷移guardの上限に達しても、イベント数上限まで余裕があればpause/abandonできます。

### 定義変更・応答不明・復旧

コメントやBOM/改行を含め、定義のバイト列が変わるとnext/choose/resume/finishを拒否します。
`show --run-id`は固定した制御plan（step ID・種類・辺のみ）から過去の状態を復元し、変更後の本文を
元の手順として見せません。pause/abandonは元のBound template revisionで可能です。
続行するなら運用者が信頼できるbackupから元のバイト列を正確に復元するか、放棄して新規runにします。
自動移行・本文snapshot・外部作業の凍結実行はしません。sourceはcanonical pathのSHA-256 handleへ拘束し、
移動・コピーで黙って再接続しません。hashはパスの匿名性を保証するものではありません。

応答が失われたときは、**同じ操作を自動再送せず**、元のrequest IDを確認します。

```sh
python -m lifetxt procedure run show examples/procedure-flow-ja.txt --id r --log runs.txt --request-id next-001
```

一致するreceiptは元のevent/sequenceとrunの現在状態を表示します。未発見なら再実行せず拒否します。
transaction復旧状態を確認してから、新しい明示要求の要否を判断してください。
確定済みrequest IDは別runでも再使用できず、二重イベントを追加しません。
同じログの2 writerはfile revisionを明示的に更新する必要があります。run状態は独立していてもCAS境界は共有します。

各操作は既存のlock/CAS/durable transaction journalで完全ログを置き換えます。
保護されたjournalにはログの前後バイト列を残し、定義本文はjournalの書込対象にしません。
プロセス停止・未解決/破損journalがあれば新しい書込みを止めます。
既存の[transaction復旧ツール](transaction-recovery-and-strict-timers.md)で前後revisionを確認し、
運用者が復旧を明示判断してください。新たな自動repair/rollback/archiveはありません。
検証済みbackupを戻す際も破損ログは調査用に保持し、softwareのdowngrade/revertで実施ログを削除しません。
旧clientはNoteを読めてもrunを安全に更新することはできません。

commit直前に定義を再検査しますが、外部エディタは同じlockを共有しないため、定義とログの2 file間の
portableな原子性は保証しません。commit後の定義変更を観測した場合は確定済みeventを保持しblockedと表示し、
後続操作でも再検査します。復旧journalとactor IDも実施ログと同じprivacy/access保護が必要です。

上限は一run 5,000イベント、一ログ50,000イベント/32 MiB（UTF-8 BOM込み）、event JSON 2 MiB、
永続化するIDは256文字までです。ログは定義と別の通常ファイルに限り、同一path・hardlink・symlinkのログ・
generated/read-only・不正record・未知schema・sequence/digest/request IDの重複や欠測・actor/source不一致は拒否します。
ログは閉じた一行procedure_eventだけとし、コメントは許可します。自動rotationはなく、進行中chainを分割しないでください。
journalが20,000件を超えたら、追加書込前に運用者によるarchiveが必要です。

正確な[event契約](../../.ai/project/changes/procedure-guidance/procedure-event-v1.schema.json)はchange packageに
保存し、一般Format/schema catalogへは追加しません。event_dataは閉じたprocedure-event-v1 JSON envelopeと
canonical digest chainを持ち、title/body/秘密/URL/コマンド出力/自由メモを複製しません。
hash chainは偶発破損を検出しますが、**認証付き改竄防止監査や現実の作業完了の証明ではありません**。
有効なprefixだけでは末尾eventの削除がなかったことも証明できないため、完全性の判断には信頼できるbackup/journal証拠を使い、欠けたeventを推測して追加しません。
runtimeはgraph意味論、実在するUTC日時、guard、イベント順も検証します。
replayの入力はログ/event/control planの上限で制限し、遷移は上限付きgraphで判定します。

Web実行画面・server認証済みactorの本人性・Remote/MCPは本段階に含みません。
Webは最後のPR、任意の外部自動実行は引き続きEpic外です。

## Webで手順の定義を閲覧する（第3段階・読取り専用）

通常のWebサーバーの入力に手順定義ファイルを指定します。

```sh
python -m lifetxt serve examples/procedure-flow-ja.txt
```

**More → Procedures / 手順書**、または `/procedures` を開き、手順を選びます。
階層・説明・前後の遷移・警告を確認できます。フローチャートのノードを選ぶと、
対応するステップの説明へ移動します。80ステップ・160辺までをSVGで描画し、
それより大きい有効な定義は全ステップ・遷移のテキスト一覧で表示します（最大500ステップ）。
形式の選択でCLIと同じテキスト・Mermaid・DOTを確認できます。
外部レンダラー・CDN・Markdown・URL操作や指示内容の実行は行いません。

URLには `source`（設定済みファイルの識別トークン）、`id`（root ID）、任意の
`lang=en|ja` が残ります。再読み込みで最新の定義・改訂を取得します。
sourceトークンは設定済み入力の識別子であり、認可や匿名化の保証ではありません。
レコードを開くリンクは既存の `/?id=...` を使います。複数ファイルの同名IDは
既存レコード画面の重複検査に従います。手順URL自体はsource/rootで区別します。

| GETルート | 内容 |
| --- | --- |
| `/procedures` | PC・スマホ・キーボードに対応する専用閲覧画面 |
| `/api/procedures` | `procedure-catalog-v1`：root一覧・妥当性・警告・source識別子・読めないsource |
| `/api/procedures/{source}/{root_id}` | `procedure-v1`：定義のroot・step・辺・改訂・診断・CLIと同じ出力 |

既存WebのBearer認証設定がある場合、定義の2つのAPIには同じ認証を適用します。
`/procedures` の枠は `/` と同様に公開し、W1の入力欄でトークンをメモリだけに保持して
保護されたAPIへBearerヘッダーを送ります。詳細は次のWeb runの節を参照してください。
読取り専用サーバーでも閲覧できます。不正定義は422、未知のsourceは404、
書込みメソッドは405です（既存の読取り専用・認証ガードが先に403/401を返す場合があります）。
定義・通常Task・procedure-eventログは更新しません。既存サーバー起動時のmetricsとは別です。

上限：設定済みsource 64、一覧のroot 100、一覧JSON 1 MiB、詳細JSON 2 MiB。
既存の入力10 MiB・10,000レコード・500ステップ・2,000辺・階層32の制限も適用します。
上限エラー時は入力を減らすか定義を分割してください。構文が不正なsourceは読取不可、
プロファイルが不正なrootは診断付きで一覧に表示します。
API未対応のサーバーでは案内を表示し、既存Items・Plannerへの導線を維持します。

Web run契約W1は承認されました。認証付き操作の使い方は次の節を参照してください。

## Webで手順を実施する（W1承認済み・共有実施者）

life.txtの外で環境変数にAPIトークンを設定し、定義ファイルを書込み先に選んで起動します。

```sh
python -m lifetxt serve examples/procedure-flow-ja.txt --write-file examples/procedure-flow-ja.txt --token-env LIFETXT_API_TOKEN
```

More → 手順書（`/procedures`）でトークンを入力してサインインし、手順を選びます。
定義の閲覧とは別の「手順の実施」欄を使います。「新しいrunを準備」は状態の取得のみで、
「runを開始」を押して初めて記録します。ループを含む定義は確認が必要です。
説明を読み、「次へ」または分岐の選択肢を押し、必要に応じて中断・再開・終端での完了記録・
打切りを明示します。指示・スクリプト・URL・外部作業は自動実行しません。

既存runは一覧から選べます。URLのrun IDを保って再読み込みし、再度サインインすると、
同じrunの最新状態を取得します。トークンはメモリだけに保持し、ブラウザの保存領域・URL・
イベントログには残しません。サインアウトでトークンと操作欄を消去します。
同じトークンの利用者は共有の `web-shared` 実施者となり、同じrunを操作できます。
個人別の識別ではありません。別actorのCLI runをWebで引き継ぐことはできません。

runの読み書きには既存Bearerトークンが必須です。トークン未設定・Remote有効・
別の読取りファイル・生成物・読取り専用の定義やサーバーではrunを書き込めません。
読取り専用サーバーでは、認証後に共有実施者のrunを閲覧できます。
ページの枠は既存の `/` と同様に公開し、定義API・run APIの認証は維持します。
ログはサーバーが選ぶ `<writable_path>.procedure-runs.txt` のみです。再起動時の入力展開に
含まれても、通常のItems/Notesには混ぜません。CLIと共用する場合は、このログと
`--actor web-shared` を明示します。境界はローカルのファイル権限で、署名付き監査ではありません。

操作は画面に表示したsource/logの完全な改訂・root/run・step・記録番号・一意な要求IDに
固定します。従来のobserveモードでもsourceの `If-Match` を必須とし、ログ自身のCASを適用します。
異なるOrigin・未知のJSON項目・8 KiBを超える要求は拒否します。既存の時計検査設定も保持し、
画面は設定済みのclient-timeヘッダーを送ります。別タブとの競合や不正操作時は操作欄を消し、
明示的な再読み込みを求めます。書込みの自動再送はしません。

応答が失われた場合は「元の要求を確認」で、その要求の確定済みイベント・記録番号を
読取り専用で確認します。記録が見つからなくても再送の許可にはなりません。
状態を再読み込みして判断してください。未解決・破損journalは既存の運用者向け復旧を使います。
定義が変更・削除・不正になったrunは継続できませんが、run URLから元の状態を確認し、
中断・打切りを記録できます。変更後の説明を元のrunの指示として表示しません。
runの完了を通常Taskの完了に自動反映しません。

| API | 契約 |
| --- | --- |
| `GET /api/procedure-runs?source=TOKEN&root_id=ID[&run_id=RUN][&request_id=REQUEST]` | `procedure-run-web-v1`：所有run・改訂・説明・可能な操作、または元の要求の確認 |
| `POST /api/procedure-runs` | Bearer・同一OriginのJSON・完全な`If-Match`で、専用ログへ明示操作を1件記録 |

POSTの共通項目は `source`・`root_id`・`operation`・`request_id`・`template_revision`・
`log_revision`・`step`・`sequence` のみです。start以外は `run_id`、chooseは `choice` も必須。
startにはbooleanの `allow_loops` を追加できます。actorやpathの指定は拒否します。
GETの `source_revision` を引用符付きの `If-Match` に使い、本文の `template_revision` には
run開始時の改訂を保ちます。操作はstart/next/choose/pause/resume/finish/abandonです。
エラーはprivate pathを含めず、401/403（認証・権限）、404（所有runなし）、409（競合・不確定）、
413（上限）、415（JSON以外）、422（項目不正）、428（source改訂なし）を返します。
