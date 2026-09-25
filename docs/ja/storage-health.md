# Storage HealthとスケジュールされたMaintenance

`lifetxt storage health PATH...`は読み取り専用の診断です。active/archiveの
バイト数・record数、parse診断、計測したparse時間、threshold、推奨statusを
報告します。workspaceへの書き込み、backup作成、archive planの適用は行いません。

#944のbaselineに基づく初期thresholdはactive 16 MiBまたは200,000 recordです。
これは説明可能な助言値であり、全環境共通の上限ではありません。

server-init JSONでは`maintenance_schedule`を明示的に有効化できます。
既定値は`off`です。`warn`はStorage Healthの結果だけを記録し、`plan`は
maintenance推奨時にreview可能な`archive-plan-v1`を生成しますが、適用はしません。
生成されるsystemd timerは`Persistent=true`で、再起動後に未実行分を試行します。
専用oneshot serviceにより重複実行はsystemdのunit単位で直列化されます。
scheduled backupは別の操作として扱います。
