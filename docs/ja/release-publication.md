# 承認付きリリース公開

公開の唯一の入口は `main` から手動起動する `release.yml` です。
tag push・`release:published` は公開を開始しません。旧primary/下流の7つの
workflowは呼び出しを拒否します。buildは読み取り専用の
`release-preflight-*.yml` が担当します。

## 通常版・補正版の操作

1. version PRをmergeし、同じsource SHAのpush/main CI成功を確認します。
   通常版は `X.Y.Z`、補正版は人間が選んだ `X.Y.Z.N`。省略Nは0と同じです。
   番号指定は公開承認ではなく、CIはNを自動採番しません。
2. [preflight手順](release-preflight.md)に従い、正確なsource SHA/versionで
   `release-preflight.yml` を実行します。全成功後の
   `preflight-verified-<run>-<attempt>` のartifact IDと
   `preflight-bundle.json` 内の `digest` を控えます。
   ZIP自体のSHA256と、このbundle digestは別物です。
3. Actionsの **Release**（`release.yml`、branch `main`）を
   `preflight_artifact_id` と `bundle_digest` で起動します。
   prepare jobが実ZIPと全13 targetの元payloadをdownloadし、API由来情報、
   source CI、reports、hash、期限、OCI graphを照合してplanを表示します。
   固定sourceに対するstrict release policy/schema/golden/翻訳/書込経路と
   CLI safety release-gateもjsonschema必須で維持し、旧profileのbuild/twine/
   clean-installはpreflightで検証します。
   この段階ではtag/registry/Releaseに書き込みません。
4. prepareのsummaryを確認し、Release Authority `Eruhitsuji` が待機中の
   **pypi** environmentを1回承認します。承認commentには表示された次の文字列を
   **そのまま**入力します。

   ```text
   release <plan-digest> run <release-run-id>/<attempt>
   ```

   API承認履歴の人間login/type、environment、plan、run、attemptを照合します。
   reviewer設定や承認証拠がなければ公開前に停止します。別runや別planの承認は
   再利用できません。スクリプトからの自己承認・bypassはありません。
5. 承認後にもpreflightを実download・再検証し、plan一致を確認します。
   tagをsourceに固定し、GHCR version/v-version、GitHub primary assets、
   PyPI wheel/sdistを**再buildせず**公開します。既存物はdownloadして同じbytesを
   確認した場合のみ省略し、不一致なら停止します。
6. 全primary確認後に単一finalizerが `SHA256SUMS` を確定します。
   別の読み取り専用verify jobがGitHub全asset/PyPI両配布物の公開URLを独立downloadし、GHCRの両platformと
   graph全体を照合。downloadしたLinux Standalone/Miniを実行し、CLI/conformanceを
   検証します。Desktopは認証済みpreflightのmetadata/mapping/bundled Core smokeを保持します。
7. 別runnerのfinish jobが確認済み入力からwinget/Scoop manifestとconda recipeを生成し、既存credentialで
   Homebrewをcompare-and-swap更新・読み戻しします。必須機械検証・生成・Homebrew
   成功後にGHCR latest/major/minorとGitHub Latestを更新します。
   4要素の数値比較で古いretryによるLatest/alias逆行を拒否します。

同時公開は全version共通concurrencyで直列化し、実行中のrunを取消しません。
待機runがGitHub側で置き換わっても、生き残ったrunには固有の承認が必要です。
全段階は中央workflowの明示的な順序なので、GITHUB_TOKEN作成イベントが連鎖しない
制約には依存せず、tag起動用PATも追加しません。
environment/OIDCはpublish-pypi jobのみです。verifyは公開権限・Homebrew credentialを
持たず、finishはproduct binaryを実行しません。1回のrun固有承認を明示needsで
後続段階へ適用するため、追加の承認操作は不要です。

## 外部設定

PyPI Trusted Publisherの owner `Eruhitsuji` / repository `lifetxt` /
workflow `release.yml` / environment `pypi` を維持します。
GitHubの `pypi` environmentにはrequired reviewer `Eruhitsuji` と
branch `main` 制限を設定してください。prevent-self-reviewは別の人間が
起動する体制の場合に使います。単独保守者が起動・承認する場合は有効にできません。
本実装は外部設定を確認済み・設定済みとは扱いません。

Homebrewは既存 `HOMEBREW_TAP_TOKEN`（`Eruhitsuji/homebrew-tap` のみ、
Contents read/write）を再利用します。不足・権限エラーはHomebrewとLatestを停止し、
既に公開したprimaryは保持します。winget/Scoop/condaは生成に外部投稿権限を使いません。

既知の重大欠陥はrepository variable `RELEASE_CRITICAL_BLOCKER` に非空文字列を
設定して公開段階とLatestを停止できます。実行途中に判明した欠陥は人間のincident対応も
必要であり、以前のgreen判定で容認したことにはなりません。

## inventoryと状態記録

`release-inventory.json` はsource/version/candidate digest、公開名・hash・size・
role・targetを記録します。範囲はCore wheel/sdist/SBOM/provenance、Standalone5本、
全Desktop installer、Mini binary/checksum/build-info/notes。
同一bytesの共通Mini notesのみ重複排除し、その他の重複・大小文字衝突は拒否します。
Desktop private bundled CoreとOCI archiveは非公開です。
LFのみの単一 `SHA256SUMS` は全primaryとinventoryを網羅し、自身のみ除外します。
旧workflow別manifestは公開しません。

前段の `release-primary-receipts-<run>-<attempt>` と
`release-verification-receipts-<run>-<attempt>` も失敗を含め証拠を保持します。
最終 `release-receipts-<run>-<attempt>` はplan、機械receipt、失敗receipt、手動提出用生成物を
90日保持します。channelの `verified/generated/blocked/manual_required` を区別し、
全体は `primary_published` → `primary_verified` → 下流も成功した `verified` → Latest読み戻し後の
`accepted` と進みます。失敗receiptの停止stageは、それ以前のreceiptより優先です。
alias部分更新はacceptedではありません。外部登録・審査・installを生成成功と混同せず、
全OS Desktop GUI matrixは `not_verified`。外部手動受入は非blockerですが、
具体的な重大欠陥は停止条件です。

## 失敗時の復旧

| 分類 | 復旧 |
| --- | --- |
| `preflight_failure` | 公開せず停止。修正PR後の新SHAでpreflight。同じ未公開番号は使用可。 |
| `publish_retryable` | 公開先を再照合し、tag/source/bytes/digestを固定したまま欠けた操作だけ再開。 |
| `published_source_defect` | 旧tag/bytesを保持。人間が新versionを選択し、PR/CI/preflight/承認を再実行。 |
| `external_manual_required` | 生成物を外部の通常手順で提出。外部公開済みとは扱わない。 |
| `critical_blocker` | 公開/Latestを停止。撤回等はRelease Authorityが判断し、静かな差替えは禁止。 |

同一bytesのretryは、**同じ元preflight artifact ID/bundle digestで新しいRelease runを
起動し、新planを承認**します。一致する既存tag/Release/assets/PyPI/GHCR/Homebrewは
safe no-opとなり、欠けた処理のみ書き込みます。
GitHubのRe-run failed jobsは古いattemptのprepare planを再利用するため拒否されます。
preflight入力の期限切れ・削除時は停止し、公開先と保持証拠の確認が必要です。
公開番号の再buildは承認済み復旧ではありません。

source/tag不一致、別名 `vX.Y.Z.0` tag、未知asset、重複、CRLF、hash/version不一致、
API/権限エラー、新しいLatestは停止条件です。tag移動、clobber、自動N採番、
registry固定versionの上書きはありません。alias部分更新の修復も、同一検証済みdigestと
全ゲートを再確認して行い、GitHub Latestを最後に更新します。

実例: v1.0.4は一部公開後にsource修正が必要となったため、tag/bytesを保持し、別に
選択したv1.0.4.1で補正しました。一方、下流の順序失敗は同一bytesでretryできました。
Desktop checksum不足は今回のinventory finalizerで止めます。
これらの既存公開版は新pipelineのbindingを持たないため、例示に限り再公開しません。

## 検証の境界

offline試験は全13 producerの実validatorをsynthetic payloadで通し、承認/API/期限/改変/
部分公開/retry/下流順序を検証します。公開済み成功を証明するものではありません。
初回の実公開には別途承認が必要で、PyPI OIDC、GHCR転送、environment、Homebrew権限の
実確認が残ります。実preflight run 38822634032はbuildと非公開artifact転送の証拠であり、
公開承認を持ちません。
