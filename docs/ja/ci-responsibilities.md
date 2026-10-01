# CIの責務

lifetxtのcontinuous integrationは、3つの明示的な責務へ分離されています。この分離で変えるのはcheckを実行する時点であり、supported environmentやquality boundaryではありません。

## Pull request: 高速なmerge判定

すべてのpull requestで、Python 3.12によるsource-tree full suite、compile、3つのexample check、basic smoke、承認済みmypy boundary、release documentation validation、traceability gateを実行します。`PR gate`はこれらを集約し、すべて成功した場合だけ成功します。

同じPRのrunは`pr-ci-<number>` concurrencyと`cancel-in-progress: true`を使用します。新しいpushが来ると古いrunをcancelします。`main` push、手動CI、release runは衝突しないgroupを使用し、後続runでcancelされません。

## Main: compatibilityとregression検出

merge後の`main`では、Python 3.10／3.11／3.12、no-Web、ResourceWarning、Windows／macOS core smoke、coverage regression、Web／TUI dependencyのminimum／upper compatibility、mypy、release documentation validationを実行します。`Main compatibility gate`はこれらすべてをfail-closedで集約します。

自動管理される`CI failure on main` Issueは、この安定した集約gateだけを監視します。集約失敗時にIssueを作成または更新し、次のmain成功時にcloseします。内部job名の変更は監視contractへ影響しません。

## Release: 配布artifact

tag／manual Release workflowがpublication evidenceを担当します。artifact固有release profile、release evidence build、metadata validation、clean environmentへのwheel install、installed command smokeを実行します。release profileではsource-tree full testsを重複実行しません。詳細は[release-policy-gates.md](release-policy-gates.md)を参照してください。

standalone binary、package manifest、Docker、Homebrew、Conda、desktop installer、lifetxt-mini workflowは独立したままです。特にlifetxt-miniの既存path filterは変更しません。
