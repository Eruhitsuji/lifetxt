
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
