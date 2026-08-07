# Remote互換性ネゴシエーション

Remoteプロトコルversion 2では、`GET /api/remote/v1/capabilities`から明示的な互換性マニフェストを公開します。このマニフェストは、最小・現行プロトコルヘッダーとcapability revisionを補完するものであり、Remote書き込みを有効化するものではありません。

## 公開されるメタデータ

capabilityレスポンスには次の情報が含まれます。

- `server`: パッケージ名とサーバーパッケージversion。
- `schema_bundle`: 公開スキーマ数と、正規化したスキーマ束のSHA-256 revision。
- `contracts`: 設定、workspace manifest、transaction journal/policy、clock、ticket/custom field/workflow/event/time/planning、attachment、Remote resourceについて、検出した最小・現行スキーマversionと正確なスキーマ名。
- `optional_dependencies`: 実行中プロセスでWeb（`fastapi`、`uvicorn`）およびTUI（`textual`、`watchdog`）の宣言済み依存グループを利用できるか。
- `compatibility`: 未知フィールド、未導入の任意機能、削除済み機能、将来プロトコル、明示的なdowngrade選択に関するクライアント規則。

すべて集約情報のみであり、ローカルパス、認証情報、ソース本文、parser message、record内容は含みません。互換性フィールドは`capability_revision`の計算対象となるため、クライアントは完全なpayloadを比較せずにサーバー契約の変更を検出できます。

## クライアント動作

クライアントは、自身の対応プロトコル範囲とサーバーの最小・現行範囲の共通部分を計算します。要求プロトコルがその共通部分に含まれる場合のみ処理を継続します。未知のcapabilityフィールドは無視します。任意依存が存在しない機能は無効として扱います。削除済み機能は暗黙に代替せず、明示的な非対応エラーにします。未対応の将来プロトコル番号は、従来どおり`REMOTE_VERSION_UNSUPPORTED`で拒否します。

`lifetxt remote test PROFILE`は、クライアントとサーバーの範囲、共通部分、選択プロトコル、マニフェスト有無、旧版・新版サーバーに関する警告を含む決定的な互換性レポートを返します。プロトコルversion 1はヘッダー未指定時の互換デフォルトとして維持され、拡張マニフェストを必須としません。

## ドメイン単位のcontract警告

特定の公開contractドメイン（例: `ticket_workflow`や`attachment`）に依存するクライアントは、`evaluate_compatibility()`に`required_contracts`を渡せます。ドメイン名のリストを渡せば存在確認のみ、ドメイン名から最小要求versionへのマッピングを渡せば存在確認とversion確認の両方を行います。ドメインが未公開・利用不可・要求最小versionを下回っている場合は、そのドメイン名を明示した警告を互換性レポートに1件追加します。`contracts`に公開されていない未知のドメイン名を指定した場合は、無言で警告し続けるのではなく即座にエラーになります。この確認はクライアント側のみで行う助言的なものであり、サーバーがこれを理由にリクエストを拒否することはありません。`required_contracts`を省略した場合、レポートは変化しません。

## capability-revisionヘッダーの整合性

`X-Lifetxt-Remote-Capability-Revision`ヘッダーとcapability本文自身の`capability_revision`フィールドは、サーバー側で計算された同一の値から設定されるため、クライアントは両者を比較することでヘッダーを除去・書き換えるリバースプロキシやキャッシュを検出できます。`lifetxt remote test`は`header_status`フィールドを報告します。両者が一致する場合は`"present-and-consistent"`、レスポンスにヘッダーが存在しない場合は`"missing"`、ヘッダーが本文と一致しない場合は`"mismatch"`となり、後者2つの場合は互換性レポートに警告も追加されます。このフィールドは、クライアントがこの確認を要求した場合にのみ現れ、要求しないレポートには含まれません。
