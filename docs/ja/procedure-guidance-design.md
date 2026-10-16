# 人間向け手順案内：v1契約草案

状態：**2026-10-16、PR #1345のmerge後にEruhitsujiがD1〜D4を承認**。
第1段階（#1334〜#1337）の閲覧・検証・図出力は提供済み。第2段階（#1338〜#1341）でローカルrun/証跡/CAS/CLIを実装し、Webは後続計画。Format 1.0の文法変更ではない。
Phase 0 / #1333、親Epic #1332。
対応する[英語版](../en/procedure-guidance-design.md)と同じ契約を記載する。

## Decision Request

D1〜D4の一括承認を推奨する。

- D1：`[N] N`と専用`proc_*`によるopt-in、v1は同一ファイル内に限定。
- D2：明示操作による遷移、終了とno-opを区別し、ループを有限に制限。
- D3：定義と別のNativeドメインイベントを実施状態の正本にし、定義と実施ログの完全revisionを照合。
- D4：初期リリースは#1337までの閲覧・検証・図出力とし、run実行とWebは後続リリース。

承認結果は#1332/#1333へ記録済み。後続の正確なデータ/API対応と、merge・release・deployの承認は別である。
判断根拠、代替案、リスクと次の作業を以下に示す。
適用規則：CTX-HUMAN-001、CTX-ASSURE-001、TASK_DECOMPOSITIONの作業単位、
AI_HUMAN_INTERACTIONの公開API・データモデル変更の人間承認。

## D1：定義・互換性・代替案

| 案 | 利点 | 制約・推奨 |
| --- | --- | --- |
| `[N] N`と`proc_*` | 既存parser・body・ID・parentを再利用しTaskには混ざらない | 推奨。一般Note一覧には表示される |
| `[ ] T`でテンプレート | チェックリストとして親しみやすい | 定義と実施完了を混同するため採らない |
| 別ファイルに通常Noteを保存 | 一般Note一覧への混在を減らせる | 配置方法として対応。別フォーマットではない |
| 専用type・別DSL | 専用記法を強制しやすい | 旧クライアント互換や別parserが必要となるため延期 |

KNOWN_KEYSや一般`check`への登録・意味変更は提案しない。独自属性のW106は想定内である。
通常のcheckは警告付き成功、`--warnings-as-errors`は失敗となる。
一般checkの成功は手順意味論の検証を意味しない。既存のtext/JSON/JSONL変換ではキーを
保持できるが、旧クライアントは手順誘導・実行できない。未知属性を捨てる外部ツールを
編集に使わず、バックアップと差分を確認する。空白・コメントのバイト一致は保証せず、
ID・body・繰返し属性の意味的一致を要求する。

`proc_role:root|step`の明示指定だけで対象にする。通常Task/Note、無関係な独自属性、
VMの`next:`等を誤認しない。厳格検証はprocedureコマンドだけで行う。
対象レコードは`[N] N`、canonicalな`id`を一つ持つ。代替id-key設定はv1では拒否し、
別の識別子規則を黙って混用しない。`proc_case`以外の各profile属性は単一値。

| 草案キー | 所有レコード・値・個数 |
| --- | --- |
| `proc_role` | rootまたはstep、一つ |
| `proc_version` | rootのみ、値は`1`。未知versionは拒否 |
| `proc_start` | rootのみ、開始step IDを一つ |
| `proc_kind` | stepのみ、action / decision / endを一つ |
| `proc_next` | actionのみ、次step IDを必ず一つ |
| `proc_case` | decisionのみ、`label=STEP_ID`を2〜16個 |

選択ラベルは`[a-z][a-z0-9_-]{0,31}`のASCIIトークン。大文字小文字を区別し、空白や
条件式を許さない。最初の`=`で分割し、空・不正な対象IDを拒否する。対象は既存ID規則に
従う。ラベルの翻訳説明はbodyに置き、識別トークンは変えない。
opt-in対象の未知`proc_*`は誤記として拒否し、それ以外の独自属性は通常のデータとして保持する。

各stepは単一の明示`parent`チェーンで一つのrootに属する。祖先はstepまたはrootのNote。
複数parent、循環、rootの入れ子、単なる行隣接による所属推測は禁止。stepの入れ子は
表示階層であり、暗黙の呼出し・復帰ではない。表示は入力順、実行順は明示遷移で決める。
既存parser通り明示parentがインデントより優先し、解決結果のparentは一意でなければならない。
rootはparentを持たない。

v1の入力は明示的に選んだ単一ファイル。workspace globは扱わない。ファイル内の全IDを
索引化し、選択を曖昧にする重複は拒否する。遷移先は同じファイル・rootのopt-in stepに
限定し、別ファイル/root、URL、パスを解決しない。別ファイルでは同一IDを使えても、
source handle込みで識別する。CLIは複数入力を拒否、Webは認可済みsource resolverを使い、
クライアントから任意パスを受け取らない。同じファイルに複数rootは許可するが、
`--id`等で一つを指定し、既定入口を推測しない。

## 承認済み記法の例（show/graph対応、run実行は後続）

```text
[N] N "サーバー更新" id:p_update proc_role:root proc_version:1 proc_start:s_check
[N] N "状態を点検" id:s_check parent:p_update proc_role:step proc_kind:action proc_next:s_backup
| 稼働と空き容量を人間が確認してから続行する。
[N] N "バックアップ取得" id:s_backup parent:p_update proc_role:step proc_kind:action proc_next:s_update
[N] N "手動更新" id:s_update parent:p_update proc_role:step proc_kind:action proc_next:s_verify
[N] N "検証結果" id:s_verify parent:p_update proc_role:step proc_kind:decision proc_case:ok=s_done proc_case:ng=s_rollback
| ok/ngは人間が選ぶ。コマンド実行や条件式評価は行わない。
[N] N "完了" id:s_done parent:p_update proc_role:step proc_kind:end
[N] N "手動切り戻し" id:s_rollback parent:p_update proc_role:step proc_kind:action proc_next:s_verify
```

## D2：遷移・拒否・上限

actionは明示`next`、decisionは明示`choose LABEL`で一辺だけ進む。
endは出辺を持たず、明示`finish`で初めてrunがcompletedになる。書かれた作業自体は実行しない。
閲覧・図出力・end到達だけではrun作成や完了を行わない。
no-opは未操作・拒否による状態/イベント不変であり終了ではない。nextのないactionは不正。
pause/resumeは辺を進まず、resumeはpaused状態から同じstepへ戻る。abandonは終端。
completed/abandoned後はshowだけ可能で変更不可。取り消し・後戻りは設けず、再実施は別runにする。

| 反例 | 提案する結果 |
| --- | --- |
| missing target、ID重複、別root/ファイルへの遷移 | 拒否し、推測や外部読込を行わない |
| 複数start、単一値属性の重複、複数parent | 拒否し、最初/最後を勝手に採らない |
| 分岐なし、ラベル重複、`ok`に対する`OK`入力 | 拒否し、既定選択を設けない |
| `proc_case:"disk_free>10=s_done"` | 不正ラベル。式を評価しない |
| actionにcase、endにnext、未知version/kind | profileエラー |
| 到達不能step | エラー。行付き診断を示し、利用可能な図は出さない |
| endへの経路がない閉じた循環 | エラー。全到達stepから何らかのendへ到達可能であること |
| 脱出口のある循環、自己ループと脱出口のあるdecision | 閲覧では警告、run開始時に明示確認 |
| actionのnext省略 | エラー。no-opやendにしない |
| depends_on / follows / VM next | 従来通り。手順遷移の辺にしない |
| 実施中の定義編集（コメントだけでも） | revision不一致で変更を拒否し証跡を保持 |

runは成功した辺遷移が最大1,000回、同じstepへの訪問は開始時を含め最大20回。
超える操作はイベントを残さず拒否し、pause/abandonは可能とする。
循環がある定義は`start --allow-loops`（Webは同等の明示チェック）が必要で、上限は緩和しない。
上限到達時は確認・abandon・別run作成を案内し、自動再開しない。endでのfinishは辺を数えない。

投影/検証上限：入力10 MiB・10,000レコード、選択定義500 step・2,000辺・parent深度32、
stepのbody 64 KiB、図出力2 MiB。途中切捨てで正常な図に見せず、利用可能な出力前に拒否。
索引・到達性・逆向きend到達性をO(V+E)、走査は非再帰で行う。入力順・case順を保持し、
診断はsource行→安定code順。図のnode IDにはローカル連番を使い、サニタイズ衝突を避ける。
既存quote関数もラベル・改行・衝突を試験して再利用する。リンク・script・HTMLは埋め込まない。

## D3：revision・証跡・保存正本

定義の識別は（認可済みsource handle、root ID、profile version）。
`template_revision`は`mutation.read_text_snapshot`による**正確なUTF-8入力バイト列**のSHA-256。
シリアライズ後のitem、mtime、Web ETag、item hashと混同しない。exportには絶対/秘密パスを
入れず安定したsource handleを使う。開始時にファイル全体のrevisionへ拘束し、編集後の
next/choose/resume/finishは拒否する。pause/abandonだけは元revisionを保ち、変わったstep本文を
参照せずに実施を中断・放棄できる。古いrunはID/イベントで閲覧できるが、新定義では継続しない。
bodyの凍結コピーや自動移行はしない。運用者のバックアップから正確な元ファイルを復元して
再開するか、放棄して新規runを作る。

Native Historyの`item_event`は閉じた語彙であり、手順イベントを追加・偽装しない。
新しいNativeの**ドメイン**`record:procedure_event`（`[N] N`）を、定義とは異なる明示指定の
実施ログlife.txtに保存する案を採る。実施状態の正本はこれだけであり、既存のドメイン履歴との
分離方針に合わせる。将来timelineへ投影しても、同じ操作をitem_eventに二重記録しない。
更新可能なrun状態レコード、DB、必須sidecarキャッシュは作らない。

`procedure-event-v1`の閉じたenvelope候補：schema version、一意event ID、run ID、sequence、
transaction/request ID、UTC日時、actor ID、source handle、root ID、template revision、
event kind、直前event digest、型付きpayload。startはsequence 1・直前digest nullで、
version・guard・loop確認・開始stepを固定する。後続はnext / choose / pause / resume /
finish / abandonのみ。payloadは必要時の前後step IDと選択トークンに限定し、タイトル・body・
秘密・URL・コマンド出力・自由メモを複製しない。actor IDは個人情報でログ/バックアップの
保護対象。hash chainは偶発破損検出であり、認証付き改竄防止監査を保証しない。
正確な実装済みenvelopeと意味検証はpackageのprocedure-event-v1.schema.json（#1339）で定義する。

純粋なreducerでactive / paused / completed / abandonedを導出する。
重複・欠番・逆順sequence、未知schema/属性、他runやrevisionの混入、直前digest不一致、
不正step/choice、guard矛盾、終端後イベントは拒否。日時で並べ替えずsequenceを正本とする。
意図的な再実施は別run ID。replayは現実の操作を再実行せず、欠けた操作を推測して復旧しない。

既存mutation/CAS/atomic writer・backup・権限を再利用する。templateとrun-logの完全revisionを
個別照合し、commit直前にtemplateを再確認する。commit後に定義変更を観測した場合もrunを
blockedとして扱う。人間のエディタはOSロックを共有しないため、二ファイル間のportableな
原子性を称さない。後続操作でも双方を再検査する。一イベントを追記した完全ファイルを
原子的置換し、生のappendはしない。共有ログは別runでも同じfile revisionで競合する。
request IDとexpected step/sequenceを必須とし、重複要求で二重記録しない。
応答不明時は明示的に再読込し、一致する既存イベントまたは競合を示す。自動retryは禁止。
新規ログの作成は既存のmissing-state前提を使い、空ファイルhashで代用しない。

上限は一run 5,000イベント、一ログ50,000イベント/32 MiBで書込前に拒否。
replayは展開前に境界を検査しO(events)。自動圧縮・保存期限・rotationは延期。
運用者は新しいrunを新しいログへ保存できるが、古いrun用のログは保持し、進行中chainを分割しない。
破損ログは読取専用とし、破損バイト列を保持した上で、既存の運用者復旧手順で検証済みの完全backupを
戻す。中断commitは既存writer契約の完全な旧版/新版へ収束させ、journal不明時は書込停止。
softwareのrevertで定義/ログを削除しない。旧clientはNoteを読めてもrunを書けない。
本書はデータ移行・rollback実行・削除を承認しない。

Webは全read/writeで定義/stepの可視性とログ権限をserver側で照合する。変更はwrite権限と
actor本人のrun所有権が必要。actorはJSON申告ではなく認証済みserver contextから得る。
CLIはlocal operator identityを明示する。信頼できるWeb identityがなければrun書込は無効。
source書込権限だけで本人性を推定せず、新しい認証ポリシーは本Epic外とする。
既存If-Match middlewareに加えtemplate/run-log revisionを別前提として渡し、最新ETagで
古いform snapshotを格上げしない。読取画面はGETのみ。CSRF/origin、path制限、機密errorの
抑制は既存server境界を再利用し、非公開/存在しない/未認可resourceから本文や秘密パスを漏らさない。

## 脅威モデル・残存リスク

非信頼の定義・図ラベル・URL入力・同時編集を想定。data-only escape、選択allowlist、
図の連番ID、eval/process/HTTP/MCP呼出し禁止、外部Mermaidサービス禁止、入出力上限で対処する。
秘密は定義/ログに書かない。hashは元ファイルの秘密を消さず、定義閲覧権限を持つ人はbodyを読める。
exportも元データと同じprivacy判断が必要。DoS、symlink/path脱出、古いform、二tab/二click、
応答不明時を否定試験に含める。clipboard/downloadは明示操作に限る。background実行・通知・
外部共有はしない。上限とCASは手順の正しさや現実の作業完了を保証せず、実作業は人間が担う。

## UX・リリース（show/graph・ローカルrun実装、Webは計画）

テキストだけ：Noteの定義は変更せず、作業ごとに別work fileへ一意IDの`[ ] T`を作り、
`ref:`で定義を参照する。選択・中断理由はwork fileへ手書きする。機械検証可能なrun証跡とは
称さない。#1334は既存キーだけの基本例を日英で作り、proc_*付き例を示すなら別のopt-in例にする。

CLI案：`procedure show FILE --id ROOT`（text既定）、
`procedure graph FILE --id ROOT --format text|mermaid|dot`、
`procedure run start|show|next|choose|pause|resume|finish|abandon`。
readではログを作らない。writeはsource/log、run ID（start時は新規返却）、request ID、
expected template/log revision、expected step/sequenceを明示する。非TTYで既定選択せず不足は拒否。
公開JSON/schemaはHigh契約承認まで延期。内部投影`projection-v1`、将来Web adapter
`procedure-v1`、遷移結果`transition-v1`は異なる契約境界であり同一schemaとして扱わない。

Web：既存deep link/graph表示を再利用し、text階層、keyboard、accessible status、390 px幅で
確認する。閲覧画面はrun操作を持たず、明示実行モードでrun/source revisionと現在stepを表示。
reload/timeoutは再取得し、競合時に選択内容を確認用に残しても再送しない。
read-only/未認証状態では変更UIを出さない。

Phase 1（#1334/#1335）だけの出荷も有用だが分岐検証/図がなく、出すなら「定義閲覧」と表示する。
初期の利用者向け出荷は#1337までを推奨し、runとWebは別リリースとする。
version/tag/deploy先はここでは決めない。

## 子Issue契約・受入マトリクス

追加の人間承認により、#1334〜#1337（閲覧）、#1338〜#1341（run/CLI）、#1342/#1343（Web）の3 PRに再編。
同じ段階内の依存は一PR内で順に実装し、次段階は前段のmerge後、最新origin/mainから開始する。
最終baseはmain。中間sub-PR・integration branchは作らない。requirements/merge ownerはEruhitsuji、executorはCodex、
最新headの独立人間reviewは未実施。各実装のReady前にCAPABILITIES/TRACEABILITY/package更新を
作業契約に追加する。本Phase 0はglobal registry・製品コード・規範Format・実行fixtureを変更しない。

| Issue | #1333承認/merge後の依存 | 書込境界 | assurance・証明 |
| --- | --- | --- | --- |
| #1334 | なし | 日英guideとexamples | Quick：独立した2回の実施、一般check |
| #1335 | なし | procedure_definition.py、対象test、最小show dispatch | Standard：階層/source/順序/上限、parser/links回帰、公開JSONなし |
| #1336 | #1335 | procedure_validation.pyとtest、一般validatorは不変 | High：選択/終了可能性/循環/上限/反例 |
| #1337 | #1336 | procedure_graph.py、最小dispatch、test、日英CLI | Standard：text/Mermaid/DOT同義、注入/ID衝突、subprocess |
| #1338 | #1336 | procedure_transition.pyとtestだけ | High：純粋遷移表、guard/revision、副作用なし |
| #1339 | #1335 | procedure_run_model.py、schema、test、設計記録 | High：ドメインevent属性、roundtrip/replay/privacy/破損 |
| #1340 | #1338/#1339 | procedure_run_store.py、薄いtransaction adapter、fault test | High/M：CAS/復旧は単一event commit契約として一体で検証 |
| #1341 | #1340 | procedure_cli.py、最小dispatch、test、日英guide | High：非TTYの開始/分岐/中断/再起動/再開/終了、重複要求 |
| #1342 | #1337 | 専用Web adapter/assets、最小登録、test | 新endpointならHigh：GET認可/XSS/390 px/keyboard/browser |
| #1343 | #1341/#1342 | 専用write adapter/UI、対象test | High/M：本人認可、二run/tab、stale form、障害/browser復旧 |

実施順は#1333→#1334→#1335→#1336→#1337→#1338→#1339→#1340→#1341→#1342→#1343。
依存上の並行可能性があっても今回は逐次対応とする。共有cli.py/Web登録はdispatch/resource hookの
最小変更に限定しPlanner/Topの再設計を行わない。各着手前に既存ファイルの正確なpathとschema対応を
Issueで具体化し、size/High承認、依存mergeを確認してReadyにする。
Phase 0承認は後続試験の成功を意味せず、独立review・CI・freeze方針・merge承認を省略しない。

## 最新mainの調査・重複整理

調査commit：`204fc69e0796a29e8ecf98fa822e64fd866ac028`。

| 既存要素・Issue | 再利用 | 意味境界・根拠 |
| --- | --- | --- |
| Format spec、parser.py、serializer.py、validator.py、tests/test_roundtrip_golden.py | Note/body/custom key/ID/parentと変換 | W106は警告。手順の意味を検証しない |
| cap-graph-link-foundation、links.py、tests/test_links.py | ID索引と図の書式処理 | 関係辺は関係のまま。既存sanitize IDは衝突しうる |
| #1140、docs/ja/text-editor-only-workflow.mdと英語版 | 制限環境の運用説明 | 週次guideを重複させず手順定義/実施例を追加 |
| #562、vm.py、tests/test_vm.py、tests/test_vm_cli.py | 図構築・escapeの知見 | VM CFG/opcode/実行意味は転用しない |
| #563、webapp.py、mcp.py、tests/test_mcp_expansion.py | filter付きgraph表示 | 手順MCP公開・temporal辺混合はしない |
| #564、links.pyのtopological_order/critical_path/shortest_path | 索引/走査手法 | 手順の有限人間loopとTask DAGを区別 |
| #565、integrity.py、tests/test_integrity.py | read-only診断の様式 | 一般integrity修復を増やさない |
| #835、docs/ja/web.md、Web item route | canonical ID deep link | host URLを定義identityに保存しない |
| #1296、work_session.py、web_assets_js_22.js、tests/test_work_session_v4.py | frozen revision/二重送信/transaction UI | timer/work-sessionをrunにしない |
| cap-native-semantic-history、native_history.py、docs/ja/native-semantic-history.md、tests/test_native_history.py | ドメイン履歴の正本と出典 | 閉じたitem_event語彙へ手順遷移を入れない |
| mutation.py、tests/test_safety_foundation.py、docs/ja/web.md | 完全byte snapshot、CAS、validated atomic write | file/source/run/HTTP revisionを区別 |

関連7 Issueはいずれもfetchしてclosedを確認した。trackerの未更新checkboxだけで実装を判断せず、
上記source/testを根拠にする。現行check/roundtripの実測はpackageのverification記録を参照。
提案した意味診断・保存・browser動作は未実装の受入計画であり、検証済みとはしない。

第1段階の実装と使い方は[人間向け手順書](procedure-guidance.md)を参照。
Phase 0調査の根拠commitと実装検証のcommitを区別し、実測結果は更新済みpackageへ記録する。
上限付きreaderはread_text_snapshotと同じ完全byte hashのmutation.hash_bytesを使い、
全snapshotを割り当てる前にサイズを制限する。

第2段階の正確なローカルrun契約は[guide](procedure-guidance.md#ローカルでの実行案内と証跡)を参照。閉じた一行event_data、ID/種類/辺だけの固定control、明示request receipt、既存の単一log journal復旧を実装する。CLI actorは記録用で認証ではなく、Webは第3段階である。
