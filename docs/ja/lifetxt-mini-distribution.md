# lifetxt-mini の配布

lifetxt-mini は、Pythonを必要としない小規模・オフラインLinux向けの
strict subsetランタイムです。完全なリファレンス実装はPython版
lifetxtであり、Miniは別形式を定義しません。

公式リリース対象は次の2つです。

| 対象 | artifact |
| --- | --- |
| Linux x86_64 | lifetxt-mini-vX.Y.Z-linux-x86_64 |
| Linux AArch64 | lifetxt-mini-vX.Y.Z-linux-aarch64 |

uname -m の x86_64 は前者、aarch64/arm64 は後者を選びます。GitHub
Releaseから対応binaryと.sha256を取得し、sha256sum -cで検証してから
実行してください。必要なら /usr/local/bin へインストールできます。

提供コマンドは list、show、Mini-profile check、add、done、
today --date YYYY-MM-DD です。Python版のrecurrence、timezone、dependency、
priority、Web、integration機能はMiniには含まれません。Windows、macOS、
ARMv7、RISC-V、Android/iOS、bare metalは公式対象外です。

artifactのversionは対応するrepository release tagと同じです。native
architecture実行、static linkage、conformance、checksum、smoke testを
通過したartifactだけがGitHub Releaseへ公開されます。
