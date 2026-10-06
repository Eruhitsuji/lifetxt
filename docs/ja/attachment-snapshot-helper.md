# 添付chunkの安全な読取り

添付chunk読取りはLinuxを公式対象とし、他OSは当面非公式です。
core parser、CLI、その他の添付操作には既存のOS方針が適用されます。

初期helperはLinux x86_64/glibc、利用可能な`openat2`、信頼したprocfsと
設定rootを必要とします。条件を欠く場合、chunk取得は利用できません。
realpathや旧readerへのfallbackはありません。LinuxというOS名だけでは
有効化しません。

## 明示的なインストール

実行環境と一致する信頼したlifetxtソースから、build時のC compilerで実行します。

```sh
python scripts/build_attachment_snapshot_helper.py
```

既定ではcheckout内のlifetxt moduleと同じdirectoryへ実行ファイルとmanifestを
配置します。インストール済みpackageには
`--output /absolute/package/directory/lifetxt/_attachment_snapshot_helper`
を指定してください。serverが使うPythonのpackage directoryへ配置し、PATHには
配置しません。source distributionにはC sourceとbuild scriptを含めます。
request処理でcompile・download・dependency installは行いません。
coreのpure-Python wheelにはhost固有の実行ファイルとmanifestを含めません。
helperの導入だけで将来のrestricted consumerが有効になることもありません。

package directory・binary・manifestはserver userまたはrootが所有し、group/world
書込みを許可しないでください。SHA-256 manifestは導入時の整合性確認であり、
署名や悪意ある所有者への防御ではありません。導入・更新・削除後はserverを再起動します。

## 安全条件と互換性

設定rootはancestorにsymlinkのない信頼したdirectoryとします。rootとfileは
server userまたはrootが所有し、group/world書込みを拒否します。
各componentのsymlink、hardlink、root以下のmount横断、directory/device/socket/pipeを
拒否します。local filesystemのext4・XFS・Btrfs・tmpfs・overlayをtypeで許可し、
network・FUSE・pseudo filesystemは拒否します。この一覧は全本番環境の認定ではなく、
現時点の実測はLinux x86_64/glibcのoverlay containerです。他filesystem実機、
別libc/architecture、Python 3.10実機は未検証です。敵対的な同一userやprivileged
writerはtrust modelの範囲外です。現在のrootとdeclared file identityも再確認します。

既存chunk response fields、configured file cap、offset/limit clamp、optional expected
revisionの意味を維持します。chunkはサイズを制限した1回のimmutable full snapshotと
そのfull SHA-256に結び付けます。従来読めたsymlink/hardlink/mount横断のfileは拒否される
場合があります。Windows/macOSやhelper未導入Linuxでは、同等readerが検証されるまで
chunk機能を利用できません。他の添付操作を一括無効化する変更ではありません。

## 取消しと運用

server process全体でlive workerは最大2、待ちqueueはありません。準備期限は最大30秒です。
取消し・timeout後も実際の終了/reapまでslotを保持し、停止不能workerの代替を増やしません。
通常fileのkernel I/Oはkill後も停止不能な場合があり、30秒以内の物理cleanup完了は
保証しません。2枠とも停滞した場合は新規readを拒否し、運用者がfilesystemを調査します。
既に配信したbytesは取り消せません。この監視処理は新しい認可engineやdownload endpointでは
ありません。

無効化する場合はserverを止め、binaryとmanifestを削除して再起動します。chunkは安全側で
拒否されます。codeのrevertは旧readerのriskも復元するため、unsafeな自動fallbackとして
使わないでください。source dataのmigrationや書換えはありません。
