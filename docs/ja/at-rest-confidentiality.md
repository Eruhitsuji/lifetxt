# 添付ファイルと復旧データの保存時の機密性

## 方針と限界

機密情報を扱う配置では、**OS／ディスク／ファイルシステム／datasetの暗号化と、最小権限・
ホスト分離を基本とし、バックアップ先も別途保護する**ことを推奨します。lifetxt自身は添付
ファイル、transaction artifact、`.ltbackup`を暗号化しません。
[#1098](https://github.com/Eruhitsuji/lifetxt/issues/1098)の設計PRをmergeすることでこの方針を
承認しますが、保存済みデータの自動移行は行いません。通常のローカル利用に鍵管理サービスへの
依存を追加しません。

LinuxのLUKS/dm-cryptやWindowsのBitLockerなど、確立したplatform機能で以下の平文保存先を
**すべて**保護してください。filesystem/dataset方式を使う場合も、内容・metadata・補助ファイル
の保護範囲が脅威モデルを満たす必要があります。最終添付ディレクトリだけを暗号化し、journalや
backupを別の無保護volumeに残す構成では不十分です。既存の`os-private-v1` evidence profileは
`encrypted_at_rest: false`を返し、権限の検査はplatform暗号化の検出ではありません。
private directoryやACLは一部のローカルアクセスを防ぎますが、offline diskへの暗号学的保護ではありません。

## 脅威モデル

稼働中のOS、サービスアカウント、アプリケーションを信頼し、攻撃者がunlock／復旧鍵を取得
できないことを前提とします。

| 攻撃者・事象 | 保護と残る限界 |
| --- | --- |
| 盗難・offline disk | 有効なunlock／復旧鍵がないlocked storageはplatform暗号化で保護できます。無保護volume、過去のコピー、流出した鍵、すでにunlockされた稼働ホストはこの保証の対象外です。 |
| backup盗難・off-host storage読者 | backup先を独立に保護します。unlockされたfilesystemからコピーしたファイルに元diskの暗号化は引き継がれません。provider暗号化の保証はその定義した範囲だけです。providerにも内容を見せたくない場合はclient-side backup暗号化を使用します。 |
| 別の非特権ローカルユーザー | restrictive ACL、専用service identity、process分離が必要です。mountされた暗号化volumeだけでは許可された読み出しを防ぎません。 |
| root/admin・アプリprocess侵害 | 機密性を保証しません。平文を読む権限のあるprocessは流出させられ、特権攻撃者は平文や鍵を取得できます。serverが復号鍵を使えるserver-sideアプリ暗号化もこの脅威を解決しません。 |
| 改ざん・replay・削除・disk喪失 | 暗号化だけではアプリ上の真正性・鮮度・可用性を保証しません。既存のrevision・integrity manifest・復旧検査は一部の衝突や破損を検出しますが、内容とhashの両方を置換できる攻撃者に対してunkeyed hashは証明になりません。検証済みの復旧可能なbackupを保持します。 |

信頼しないserverに対するclient-side **end-to-end encryption（E2EE）**は別の機能です。
clientが保持する鍵、暗号化protocol/storage contract、共有・失効・復旧を設計し、serverの
MIME検査・検索・外部toolアクセスも見直す必要があります。この方針はE2EEを保証しません。

## 平文・metadataの保存先一覧

実際の設定・環境変数・明示的な操作先によって保存先は変わります。解決されたpathと実際の
mountを、link先やremote mountも含めて調べてください。暗号化parentの下にあるdirectory名
だけでは、別途mountされたfilesystemの暗号化を証明できません。以下は現在の実装に基づく
一覧で、自動的な保護範囲検出ではありません。

| コピー・surface | 保存先と作成境界 | 内容・必要な保護 |
| --- | --- | --- |
| 最終local attachment・directory package | `attachments.root`（既定は書き込みlife.txtのdirectory）。Webは`web-uploads/<random-id>/…`。`attachment_transactions.put_attachment`とpackage/reference操作。 | 添付・packageのraw bytes。参照だけのlocal fileも保護します。外部pathは別mount・ownerの場合があります。 |
| authoritative textとmetadata | 書き込みlife.txt・設定したworkspace source、`attachments.open_state_file`（既定`.lifetxt-attachment-open.json`）、設定したstate/config/diagnostic output。 | title、filename、relative reference、hash、activity、private resource metadata。binaryだけでなくmetadataも保護します。 |
| atomic replacementの一時ファイル | `atomic.atomic_write_bytes`の`.lifetxt-*.tmp`は**出力先と同じdirectory**。添付・source・backup・restore先への書き込みに使用。 | 平文replacement bytes。通常のcleanupはsecure eraseではなく、crashで残ることもあります。書き込み前にdirectory/mountを保護します。 |
| live recovery journalとdurable-write temp | `transactions.journal_dir`より`LIFETXT_TRANSACTION_JOURNAL_DIR`が優先。既定は書き込みlife.txtの横の`.lifetxt-transactions`、write targetがない場合は`.cache/lifetxt/transactions`。 | `<transaction-id>/before-NNN.bin`、`after-NNN.bin`は正確な旧／新bytesで、添付targetなら添付内容も含みます。`journal.json`にはpath/hash/error metadata。`.lifetxt-tx-*` tempはjournal/artifact出力先の横です。 |
| terminal journal archive・abandon backup | operatorが指定する`archive_terminal` / `abandon_with_backup`出力先とintegrity manifest。 | journal directoryとbyte artifactのコピー。最終添付を変更・削除しても残り得ます。同じstorage/ACL境界を適用します。 |
| recovery working copy | `restore_backup(..., working_dir=...)`。既定は保持するtransaction backupの横の`<backup-dir>.restore-<random>`。`inspect`だけでは作成しません。 | resume/compensateはartifactを含む別コピーを使ってtargetを書きます。working copyとrestore先の両mountを保護します。 |
| disaster-recovery archive・status・restore出力 | 明示sourceまたは`backup.sources`、明示destinationまたは`backup.destination`。`.ltbackup`、同directoryのatomic temp、status sidecar、明示restore先。 | `.ltbackup`は**非暗号化ZIP**。指定した既存fileだけを含み、life.txtのreferenceから添付/journalを自動・再帰追加しません。manifest/statusは運用metadata。restoreは平文を書きます。 |
| update backup | `server-update`の`backup_paths`とtimestamp付き`backup_dir`。指定した既存fileだけ。 | raw copyとsource属性。暗号化archiveではなく、完全な添付/journal disaster snapshotでもありません。出力先directory/fileのアクセス権を独立に確認します。 |
| off-host backup転送 | `backup.remote` / 明示rclone target。`backup_remote.upload_backup`は完成済みlocal archiveを`rclone copyto`で送信。 | lifetxtはarchive暗号化を追加しません。operatorが設定する暗号化destinationまたは確立したclient-side toolでremote copyを保護します。local `.ltbackup`はauthorized readerに対して平文のままです。 |
| 通常のevidence export・support bundle | 明示出力先、`transaction_journal.export_evidence` / workspace-safety support bundle。 | redactされ、添付payload、authored text、raw absolute target path、error textを含みません。hash/fingerprint、operation/state/timingは残るため共有前に確認します。復旧可能なbyte backupではありません。 |
| raw evidence・operator copy・snapshot・Git履歴 | 手動コピーしたjournal/artifact、storage snapshot、archive、明示commitした場合の`.git` object/remote repository、editor/external viewer。 | 削除後もfull bytes/metadataが残り得ます。Web uploadが自動的にmirrorするものではなく、作成時にinventoryへ追加し出力先を制限します。 |
| 今後のprovider download/cache/staging/spool | future resolverが選ぶcache、system temp、展開先、persistent queue、diagnostic evidence。 | lifetxtがprovider bytesを保存すれば同じ境界に含めます。adapterは機密性を保証する前に保存先・上限・retention・cleanup・暗号化を定義します。この変更で汎用provider cacheを追加しません。 |

現在のWeb uploadは上限付きmemory bufferを使い、multipart spool fileは作りません。
package生成とbackup ZIP生成もmemory bufferを使います。ただしjournalと最終fileへの保存は
行います。OSのswap/pagefile・hibernation・core/crash dump、proxyのrequest-body spoolが
memory/contentを保存する可能性もあるため、platform/runbookに従って保護または無効化してください。
reverse proxyのtemp mountも配置inventoryに含めます。`PrivateTmp`は名前の分離であり暗号化ではありません。

Google Drive、OneDrive、Dropbox、S3、WebDAVだけにあるbytesはlifetxtの保証対象外です。
provider/account/access/key policyは個別adapter・配置の設計に属します。ただしdownload、
staging、cache、journal、backupなどでlocal copyを作れば対象に入ります。reference-only方式は
providerの機密性も隠れたlocal mirrorも意味しません。

## 鍵の保管・rotation・復旧

配置ownerは選んだplatform/backup toolの正規の生成・unlock・復旧手順で鍵を管理します。
unlock／復旧鍵はlife.txt、平文lifetxt設定、repository履歴、log、support bundle、復号対象の
data/backupに入れません。保護されたOS/管理用secret storeや独立に保護されたrecovery escrowを
使い、lifetxtには既存の機密でない設定・credential referenceだけを残します。無人serviceの
自動unlockはホストを信頼する判断で、その稼働ホストからの保護ではありません。

保持する暗号化世代すべての復旧情報を保管し、platformが必要とするheader/keyslot backupも
含めます。共有用記録には機密でないkey/version IDと復旧担当者だけを残します。無人restartに
依存する前に、独立したauthorized recovery環境でdisposable copyのunlock・復旧と、最古の
保持backupの復旧を確認してください。すべての有効な鍵／復旧経路を失うと復号できず、lifetxtは
file hashから鍵を再生成したりplatformを迂回したりできません。

unlock credential/key wrapperの変更とdata keyの変更を区別します。wrapperだけを変更しても、
古いdata keyやheaderを持つ攻撃者が旧ciphertextを読める場合があります。鍵流出が疑われる場合は
platformの正式なre-encryption/re-key手順を使い、保持するsnapshot/backupも対象にしてください。
暗号化backup toolのpasswordだけを編集して旧鍵を破棄しないでください。新しい保護されたコピーと
restoreを検証してから、承認された旧コピー・鍵のretirementを行います。このPRは再暗号化・削除・
retention変更を行いません。

off-host backupには、既存のrclone `crypt` remoteをoperator管理のclient-side layerとして
使用する選択肢があります。local archiveやlifetxt processは暗号化しません。通常のrclone configの
passwordはobscureされるだけで安全なsecret storeではないため、configも別途保護・暗号化します。
新しいcrypt passwordへ移行する場合は両世代を使ってdataを再暗号化・copyする必要があります。
復号するtool経由で保護されたlocal storageにdownloadし、その`.ltbackup`にlifetxt backup
verify / restoreを実行してください。選ぶcrypt/provider構成のretention/listing互換性は削除を
有効にする前に検証します。この方針でproviderや鍵サービスを導入・設定しません。

## Revision・transaction・将来のアプリ暗号化

透過的なplatform暗号化はアプリが読むbytesを変えません。既存の平文SHA-256 attachment digest、
source CAS revision、directory hash、MIME/executable検査、journal integrity、CLI/TUI/Web/MCP、
外部file toolの意味は継続します。disk上のciphertextはplatformの表現であり、そのhashをlife.txtの
attachment referenceへ代入しません。Format・journal・`.ltbackup` versionは変わりません。
unlock/復号後に保護されたstorageでverify/restoreし、integrity検査の成功をvolume暗号化の証拠に
しないでください。data migration、自動鍵生成、`lifetxt encrypt`コマンドは追加しません。

最終fileだけの暗号化ではjournal・旧revision・backup・tempが読めるままになり、完全な方式は
複数のstorage/recovery/access contractを変えるため、アプリ暗号化は保留します。今後の脅威モデルが
必要性を示す場合は、別途承認するHigh assurance設計で次を定義してください。

- 独自cipherではなく、確立したauthenticated encryptionと保守されたlibrary、承認されたoptional dependency方針。
- objectごとの鍵/nonce、認証するobject/version context、鍵保管・rotation・権限・backup escrow・lost-key動作。
- inventoryの全コピーと平文memory/spill上限、検証済みaccess/MIME/recovery境界での復号。
- plaintextのlogical revisionとciphertextのstorage integrityの分離、hash/equality leakage、replay防止、version付きenvelope。
- transaction/crash復旧、保護されたmigration/downgrade、旧鍵retention、外部viewer/export互換性。

serverが復号権限を持つ方式は、そのserverに対するE2EEとは呼べません。

## 運用での確認手順

1. 全inventory path、backup destination、mount、service accountを解決します。共有記録には
   機密でないpath分類だけを残します。
2. platform toolで暗号化とunlock状態を確認し、data/metadata/journal/backup/restore/tempの
   全mountと補助的な保存を調べます。最初の書き込み前にprivate ACL/ownerを設定し、POSIXでは
   `0077`などのprivate service umask、Windowsでは継承ACLを確認します。既存file modeが保持
   されるため、勝手に厳しくなるとは考えないでください。
3. disposableな保護workspaceで無害なsampleをupload/attachし、最終fileとjournal artifactの
   保存先・before/after revisionを確認します。指定fileのbackupとrecovery working copyも
   保護storageで検証します。この確認はコピーの発見で、disk ciphertextの測定ではありません。
4. remote backup暗号化を独立に確認し、download/復号・verify・別の保護先へのrestoreを検証します。
   元diskの暗号化やupload成功をremote暗号化の証拠にしないでください。
5. platformの検証手順でlocked storageが読めず、別保管のescrowで復旧できることを確認します。
   non-terminal journalと必要な過去の鍵を保持し、暗号化試験のためにdataを削除しません。
6. export/logの機密URLとmetadataを確認します。所持でアクセスできるsigned/capability URLは
   一時的なsecretであり、通常のdurable locatorではありません。暗号化を漏洩対策の代わりにせず、
   流出の防止・redactを行ってください。

TLSは別の境界です。[Web通信のセキュリティ](web-transport-security.md)、
[transaction復旧](transaction-recovery-and-strict-timers.md)、
[backup format（英語）](../en/backup-format-v1.md)、[Ubuntu配置](../deployment/ubuntu-server.md)も参照してください。

実装根拠：[attachment transactions](../../lifetxt/attachment_transactions.py)、
[atomic writes](../../lifetxt/atomic.py)、[journals](../../lifetxt/transaction_journal.py)、
[backup](../../lifetxt/backup.py)、[rclone転送](../../lifetxt/backup_remote.py)、
[update backup](../../lifetxt/server_update.py)、[Web upload](../../lifetxt/web_attachment_upload.py)。
platform/toolの資料：[Linux dm-crypt](https://www.kernel.org/doc/html/latest/admin-guide/device-mapper/dm-crypt.html)、
[fscrypt threat model](https://www.kernel.org/doc/html/latest/filesystems/fscrypt.html#threat-model)、
[BitLocker](https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/)、
[復旧鍵](https://support.microsoft.com/en-us/windows/security/encryption/find-your-bitlocker-recovery-key)、
[rclone crypt](https://rclone.org/crypt/)。これらはtool固有の性質を説明するもので、特定のlifetxt配置で
有効になっている証拠ではありません。
