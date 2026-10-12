
## 添付のreload・browser restart・journal回復（#1290）

#1288と同じ実browser環境で `python -m unittest tests.test_web_revision_recovery_browser -v`
を実行します。required modeの実upload drawerで有限サイズの合成fileを送信し、
test-only fault `after_journal_publish` で中断します。prepared journalを残し、source/blob
byte不変、503のuncertain UI、成功receiptなしを確認します。Page reloadと、browser終了後の
新process/一時profile起動を別々に検証し、未確定transactionの成功表示・自動再送を防ぎます。

既存journal `resume` を明示呼出しするtest-only operator endpointを使い、同じjournalを
1回だけcommitします。本番browser recovery機能を追加するものではありません。refresh後の
参照と重複/replayなし、別HTTP writerによる409時のsource/blob不変、明示refreshによる
最新revision再取得後の成功を確認します。precondition欠落/不正も既存UIで停止し、
source/blob/journalを変更しません。`LIFETXT_REVISION_EVIDENCE_DIR` の
`attachment-recovery.json` に実engine・commit・fault点・status・process/profile変更・
再送/重複検証を記録します。offline resumeやautofixは実装しません。

**元の添付suite単独はwork-sessionの画面証拠ではありません。** 別途承認された
#1296がTask drawerに実UIを提供します。`tests.test_web_revision_work_session_browser`
はobserve/requiredのstart/stop/edit、item/timer/HTTP snapshot、stale/missing/invalid、
重複/replay抑止、read-only/他record保護、固定clock、中断journal/operator resume、
Page reloadと新process/profileを検証します。#1288と同じ環境で
`python -m unittest tests.test_web_revision_work_session_browser -v` を実行します。
`work-session-observe.json` / `work-session-required.json` に実engine/commit/modeを
記録します。既存`/api/timer`やTestClientを画面証拠と同一視しません。#1290/#1294の
close-outはfeature merge後の証拠記録まで保留します。

## 実ブラウザによるrevision smoke（#1288）

Web extras、Node 22以上（native WebSocket）、Chrome/Chromiumを用意し、
`python -m unittest tests.test_web_revision_browser -v` を実行します。
PATHにないブラウザは `LIFETXT_BROWSER_BIN` に実行ファイルを指定します。
ローカルの依存欠落は明示skipであり、ブラウザ検証成功の証拠にはなりません。
`LIFETXT_REQUIRE_REVISION_BROWSER=1` は欠落を失敗にします。
CIの `Real Chromium revision contract` jobもこの設定を使用します。
`LIFETXT_REVISION_EVIDENCE_DIR=.cache/revision-browser` でJSON証跡を保存できます。

loopbackの一時Uvicorn serverと合成life.txtを使い、server clockを固定します。
実Plannerのcaptureフォームがobserve/required両モードでrevisionを取得・送信し、
正常更新のlegacy fallbackが0であることを確認します。フォームを開いた後に別HTTP
writerが更新すると、409拒否時にsourceの全byteが不変で、入力と再読込エラーが
残ることを確認します。test-only fetch transportで両preconditionとrevision discovery
cookieを外した場合、requiredは428で更新せず、observeは既存のlegacy互換更新を
許容してfallbackを正確に1回計上します。server側でも受信preconditionを記録します。
file/source/workspace revisionは同一視せず、このsmokeでは単一writable sourceを
使用しcaptureのsource snapshotを明示照合します。

証跡には実engine/version、OS、Node、source commit、mode、status、metric、
byte不変の検証結果を記録します。意図したcaptureの409/428応答と対応するbrowser
logだけを許容し、それ以外のconsole/例外/HTTP/network失敗はtestを失敗にします。
起動、CDP command、subprocess、browser/server/profile cleanupに有限timeoutを設けます。
CI artifactは合成JSONのみで、本番URL・ユーザデータ・認証情報は使用しません。
proxy fault（#1289）、process/profile restart・transaction recovery（#1290）、
実deployment observe（#288–292）、layout/accessibility（#318）の完了証拠ではありません。
#1289/#1290は#1288のmergeまでblockedを維持します。最新headへの独立reviewとCIが
merge条件として残ります。

## Proxy fault・metricsのプロセス再起動（#1289）

#1288と同じ実browser環境で `python -m unittest tests.test_web_revision_proxy_browser -v`
を実行します。必須CIは `test_web_revision*browser.py` の全suiteを検出します。
loopback限定proxyでETagのみを除去（X-Lifetxt-Revisionへの既存fallback）、両read
tokenを除去（POSTせずUI errorで停止）、ETag書換え（409と全source byte不変）を
再現します。正常proxyに戻した後の明示reload・retryを確認します。write precondition
欠落はrequiredで428拒否、observeでは互換更新とcounterの追加1回計上を確認します。

旧metrics fixtureには既存legacy利用2回・観測identity・廃止済み未知fieldを含めます。
同じsource/明示metrics pathのUvicorn processを終了し、新processを起動して、全source
byte・counter・route別count・観測identityの保持、現在mode/schema、旧未知fieldを
exportしない既存contractを確認します。telemetry v3のidentity/relocation契約を再利用
しますが、保存JSON schemaはversion 1です。browser reloadのみはserver restart証拠に
しません。`LIFETXT_REVISION_EVIDENCE_DIR` の `proxy-observe.json` /
`proxy-required.json` に実engine/Node/OS/commit、proxy条件、read header、status、
metrics before/afterを記録します。
