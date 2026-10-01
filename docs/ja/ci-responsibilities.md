# CIの責務

lifetxtのcontinuous integrationは、3つの明示的な責務へ分離されています。この分離で変えるのはcheckを実行する時点であり、supported environmentやquality boundaryではありません。

## Pull request: 高速なmerge判定

すべてのpull requestで、Python 3.12によるsource-tree full suite、compile、3つのexample check、basic smoke、承認済みmypy boundary、release documentation validation、traceability gateを実行します。`PR gate`はこれらを集約し、すべて成功した場合だけ成功します。

同じPRのrunは`pr-ci-<number>` concurrencyと`cancel-in-progress: true`を使用します。新しいpushが来ると古いrunをcancelします。`main` push、手動CI、release runは衝突しないgroupを使用し、後続runでcancelされません。

CIは変更path全体を`docs-only`、`python-core`、`web`、`tui`、またはfail-safeな`full`へ分類します。軽量経路を使うのは変更がすべて`docs/`配下の場合だけです。この場合もdocumentation validationとPR traceabilityは実行し、Python suiteとmypyだけを意図的にskipします。Web/TUIの混在、workflow／project-control file、packaging metadata、未知path、空の比較、手動実行はすべて`full`になります。

## Main: compatibilityとregression検出

merge後の`main`では、Python 3.10／3.11／3.12、no-Web、ResourceWarning、Windows／macOS core smoke、coverage regression、Web／TUI dependencyのminimum／upper compatibility、mypy、release documentation validationを実行します。`Main compatibility gate`はこれらすべてをfail-closedで集約します。

docs-onlyのmergeではmain側のcompatibility runnerをskipし、gateはそれらの結果が`skipped`であることを要求します。documentation validationは引き続き成功必須です。それ以外の分類ではすべてのcompatibility結果に`success`を要求するため、意図しないskipで集約gateがgreenになることはありません。

自動管理される`CI failure on main` Issueは、この安定した集約gateだけを監視します。集約失敗時にIssueを作成または更新し、次のmain成功時にcloseします。内部job名の変更は監視contractへ影響しません。

## Release: 配布artifact

tag／manual Release workflowがpublication evidenceを担当します。artifact固有release profile、release evidence build、metadata validation、clean environmentへのwheel install、installed command smokeを実行します。release profileではsource-tree full testsを重複実行しません。詳細は[release-policy-gates.md](release-policy-gates.md)を参照してください。

standalone binary、package manifest、Docker、Homebrew、Conda、desktop installer、lifetxt-mini workflowは独立したままです。特にlifetxt-miniの既存path filterは変更しません。
