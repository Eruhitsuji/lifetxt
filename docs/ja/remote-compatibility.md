# Remote互換性ネゴシエーション

Remoteプロトコルversion 2では、`GET /api/remote/v1/capabilities`から明示的な互換性マニフェストを公開します。このマニフェストは、最小・現行プロトコルヘッダーとcapability revisionを補完するものであり、Remote書き込みを有効化するものではありません。

本ドキュメントは、マニフェストと`evaluate_compatibility()`レポートを構築するmodule `lifetxt/remote_compatibility_v21.py`を扱います。同じcapabilityレスポンスが公開するresource catalog（`roles`、`resources`、`authentication`）については[remote.md](remote.md)を、`lifetxt remote test`／`lifetxt remote permissions`がこのdataをCLIでどう表示するかについては[remote-client-writes.md](remote-client-writes.md)を参照してください。

## 公開されるメタデータ

`install_remote_compatibility_v21()`はserverの基本capability builderをwrapします。基本documentが既に公開しているfield（`protocol`、`roles`、`resources`、`authentication`、`mutation_policy`、`features`など -- [remote.md](remote.md)と[remote-ticket-writes.md](remote-ticket-writes.md)参照）はそのまま保持し、その上に次の5つのtop-level fieldを追加してから、統合済みpayload全体に対して`capability_revision`を再計算します。

- `server`: パッケージ名とサーバーパッケージversion。
- `schema_bundle`: 公開スキーマ数と、正規化したスキーマ束のSHA-256 revision。
- `contracts`: 設定、workspace manifest、transaction journal/policy、clock、ticket/custom field/workflow/event/time/planning、attachment、Remote resourceについて、検出した最小・現行スキーマversionと正確なスキーマ名。
- `optional_dependencies`: 実行中プロセスでWeb（`fastapi`、`uvicorn`）およびTUI（`textual`、`watchdog`）の宣言済み依存グループを利用できるか。
- `compatibility`: 未知フィールド、未導入の任意機能、削除済み機能、将来プロトコル、明示的なdowngrade選択に関するクライアント規則。

すべて集約情報のみであり、ローカルパス、認証情報、ソース本文、parser message、record内容は含みません。互換性フィールドは`capability_revision`の計算対象となるため、クライアントは完全なpayloadを比較せずにサーバー契約の変更を検出できます。

`contracts`が認識するドメイン名は正確に12個です（`lifetxt/remote_compatibility_v21.py`の`_CONTRACT_PATTERNS`）。`configuration`、`workspace_manifest`、`transaction_journal_policy`、`clock`、`ticket`、`ticket_custom_field`、`ticket_workflow`、`ticket_event`、`time_entry`、`ticket_planning`、`attachment`、`remote_resource`です。各ドメインの`minimum`／`current`／`schemas`は、公開済みの全スキーマファイル名をsubstring pattern（`ticket_workflow`ドメイン向けの`ticket-workflow`、`attachment`ドメイン向けの`attachment`／`directory-package`／`package-manifest`など）でスキャンして導出されます -- 手作業で維持された、互いに排他的な対応表ではありません。実際に稼働中のserverで確認したとおり、これは1つのスキーマファイルが同時に複数ドメインを満たし得ることを意味します。`ticket-version-v1.schema.json`は、`ticket`ドメインのスキーマリスト（substring `ticket-v`を含む）と`ticket_planning`ドメインのスキーマリスト（`ticket-version`も含む）の両方に現れます。`required_contracts=["ticket_planning"]`で存在確認だけを行うcallerにとっては、`ticket-planning`や`ticket-sprint`という名前のスキーマが個別に必要なわけではなく、この1つのスキーマが公開されていれば十分です。

## クライアント動作

クライアントは、自身の対応プロトコル範囲とサーバーの最小・現行範囲の共通部分を計算します。要求プロトコルがその共通部分に含まれる場合のみ処理を継続します。未知のcapabilityフィールドは無視します。任意依存が存在しない機能は無効として扱います。削除済み機能は暗黙に代替せず、明示的な非対応エラーにします。未対応の将来プロトコル番号は、従来どおり`REMOTE_VERSION_UNSUPPORTED`で拒否します。

`lifetxt remote test PROFILE`は、クライアントとサーバーの範囲、共通部分、選択プロトコル、マニフェスト有無、旧版・新版サーバーに関する警告を含む決定的な互換性レポートを返します。プロトコルversion 1はヘッダー未指定時の互換デフォルトとして維持され、拡張マニフェストを必須としません。実際に稼働中のserver（clientとserver双方がprotocol 2）に対して確認したレポートは次のとおりです。

```json
{
  "ok": true,
  "status": "compatible",
  "requested_protocol": 2,
  "client": {"minimum": 1, "current": 2},
  "server": {"minimum": 1, "current": 2},
  "overlap": [1, 2],
  "selected_protocol": 2,
  "manifest_present": true,
  "warnings": [],
  "header_status": "present-and-consistent"
}
```

## ドメイン単位のcontract警告

特定の公開contractドメイン（例: `ticket_workflow`や`attachment`）に依存するクライアントは、`evaluate_compatibility()`に`required_contracts`を渡せます。ドメイン名のリストを渡せば存在確認のみ、ドメイン名から最小要求versionへのマッピングを渡せば存在確認とversion確認の両方を行います。ドメインが未公開・利用不可・要求最小versionを下回っている場合は、そのドメイン名を明示した警告を互換性レポートに1件追加します。`contracts`に公開されていない未知のドメイン名を指定した場合は、無言で警告し続けるのではなく即座にエラーになります。この確認はクライアント側のみで行う助言的なものであり、サーバーがこれを理由にリクエストを拒否することはありません。`required_contracts`を省略した場合、レポートは変化しません。

実際のcapability documentに対して`evaluate_compatibility()`を直接呼び出すと、callerが期待すべき正確な警告文・エラー文を確認できます。

```pycon
>>> evaluate_compatibility(caps, required_contracts={"ticket_workflow": 99})["warnings"]
["Required contract 'ticket_workflow' is at version 1, below the required minimum 99."]
>>> evaluate_compatibility(caps, required_contracts=["not_a_real_domain"])
ValueError: Unknown required contract domain(s): not_a_real_domain. Valid domains: attachment, clock,
configuration, remote_resource, ticket, ticket_custom_field, ticket_event, ticket_planning,
ticket_workflow, time_entry, transaction_journal_policy, workspace_manifest.
```

`required_contracts`は共有の`evaluate_compatibility()`関数のparameterであり、現時点では専用の`lifetxt remote` CLI flagとして公開されていません -- この確認を利用したいclientは、Python関数を直接呼び出す（`lifetxt/remote_compatibility_v21.py`自身のtest suiteがそうしているように）か、`lifetxt remote test PROFILE`の`capabilities`オブジェクト内に既に含まれる`contracts` fieldに対して同じ存在確認／version確認を自前で実装する必要があります。

## capability-revisionヘッダーの整合性

`X-Lifetxt-Remote-Capability-Revision`ヘッダーとcapability本文自身の`capability_revision`フィールドは、サーバー側で計算された同一の値から設定されるため、クライアントは両者を比較することでヘッダーを除去・書き換えるリバースプロキシやキャッシュを検出できます。`lifetxt remote test`は`header_status`フィールドを報告します。両者が一致する場合は`"present-and-consistent"`、レスポンスにヘッダーが存在しない場合は`"missing"`、ヘッダーが本文と一致しない場合は`"mismatch"`となり、後者2つの場合は互換性レポートに警告も追加されます。

このfieldは、callerが`capability_revision_header`を（何らかの形で）渡した場合にのみ`evaluate_compatibility()`のresultへ現れます（明示的に`None`を渡した場合も`"missing"`として報告されます。parameterを完全に省略した場合はcheck自体が省略され、resultにkeyが含まれません）。`install_remote_client_compatibility_v21()`は`lifetxt remote test`がこのparameterを常に渡す（responseの実際の`X-Lifetxt-Remote-Capability-Revision`ヘッダー値を使う）ようにwireしているため、実運用では`lifetxt remote test`のレポートには常に`header_status`が含まれます -- parameter省略のcaseが問題になるのは、`evaluate_compatibility()`を直接呼び出す独自コード（将来のTUIやMCP互換性checkが独自に追加する場合など）だけです。実際に確認したところ、本文の`capability_revision`と一致しないヘッダー値を渡すと`"mismatch"`と警告`"Capability-revision header does not match the response body; a proxy may be rewriting or caching it."`が、`None`を渡すと`"missing"`と警告`"Capability-revision header is missing from the response; a proxy may be stripping it."`が、一致する値を渡すと警告なしの`"present-and-consistent"`が返りました。
