# Official product website

Source for #1350 / #1351. This is a static introduction to lifetxt, separate
from the runnable Web UI. The planned URL is
`https://eruhitsuji.github.io/lifetxt/`; this file does not claim it is live.

`content.json` owns bilingual product copy, not technical specifications.
Keep command/format details in `docs/{ja,en}/` and link to those authoritative
guides. Update corresponding Japanese and English pages together. `example.txt`
is synthetic public sample data, not a user's record.

```sh
python scripts/build_website.py --output .cache/website
python scripts/check_website.py .cache/website
python -m lifetxt check website/example.txt
python -m http.server 8080 --directory .cache/website
```

Open `http://localhost:8080/`. To reproduce the project prefix, build into
`.cache/preview/lifetxt` and serve `.cache/preview`, then open `/lifetxt/`.
Output must be outside source directories and must not already exist: choose
a new directory for each build. The builder never deletes an output directory.

Root is a Japanese introduction with an English link, without browser-language
redirects or persistence. Stable language URLs use `/ja/` and `/en/`; language
links keep the same page. All ordinary local links are relative. The self-contained
404 recovery page uses the configured base path because unknown URL depth cannot
be resolved with relative links. `--site-url` changes canonical URLs, sitemap,
robots and that 404 base for a future host/domain (default: the planned URL).

Build copies only the three named canonical brand SVGs from `assets/brand/`.
No JavaScript, telemetry, cookies, external fonts, network build calls, runtime
APIs or user data are included. GitHub Pages itself is third-party hosting;
external documentation/release links use their destination services' policies.
Native binaries/Desktop installation and current support limitations stay in
the distribution guide, rather than being inferred from a package-manager recipe.

Publication, live checks and README/homepage promotion require separate human
approval and are tracked by #1352 and #1353.

## Pages publication runbook (#1352)

The site is not published by merging these PRs. The dedicated
`Official website Pages` workflow validates relevant pull requests and has no
push deployment trigger. `workflow_dispatch` is the only publication entry.
The deployment job runs only for `Eruhitsuji/lifetxt`, `refs/heads/main`, after
build/check success, and uses the `github-pages` environment. PR jobs have only
`contents: read`, no persisted checkout credentials, and do not upload a Pages
artifact. The deploy job has only `pages: write` and `id-token: write` and does
not check out or execute project source. Direct action references are pinned.

Before the first dispatch, **the human Owner** must:

1. Merge #1351's site PR before #1352's operations PR, with required checks,
   independent latest-head implementation/security/integration reviews and a
   healthy main/recovery check. Recheck the stacked PR diff after the first merge.
2. In Settings → Environments, create `github-pages`, set **Required reviewers**
   to the human `Eruhitsuji` account, and limit deployment branches to `main`.
   Do not add bot reviewers or bypass the approval gate. For a sole maintainer
   initiating the run, “Prevent self-review” must be off so that the same human
   can explicitly approve deployment; this does not waive independent PR review.
3. In Settings → Pages, select **GitHub Actions** as the publishing source.
   Do not select `main/docs`, add a custom domain, or change DNS for this slice.
4. Verify the reviewed main commit and its green CI. In Actions → Official
   website Pages → Run workflow, select **main**. Review the generated artifact
   and approve the waiting `github-pages` deployment job for that run/commit.

The workflow checks the public, read-only environment API before artifact
upload and again inside the deployment job. Missing protection, a non-human or
unexpected reviewer, HTTP/rate-limit failure, or a non-main dispatch refuses
publication. It never creates/modifies environments or enables Pages. GitHub's
native required-reviewer protection is the actual approval gate; the API check
prevents an accidentally unprotected first run. Do not change environment
protection while a deployment is in flight. No PAT or additional secret is used.

After approval, record the deployment run URL, commit, approver and UTC time
in #1353. Open the returned Pages URL and check root, `/ja/`, `/en/`, all twelve
pages, assets and a nonexistent deep path for the recovery 404. Check the
rendered canonical URLs, language switching, docs/guide/releases destinations,
mobile/desktop layout, keyboard/zoom/screen reader and browser-engine coverage.
Only then add a live-site link to the repository README/homepage through #1353.
No successful live smoke test or public URL is claimed by the implementation PR.

For failed build/check: read its job output, fix source through an ordinary PR,
then dispatch reviewed main again. For a failed deploy: verify Pages source,
environment protection and GitHub status; do not bypass gates or alter release
workflows. The previous published site remains the last successful deployment;
verify it separately rather than assuming a failed run changed nothing. For a
bad published update: the human Owner reviews a revert PR, checks CI, merges,
and dispatches/approves that reverted main through the same workflow. Do not
publish an arbitrary old branch or upload the whole repository. For emergency
unpublishing, the Owner uses Pages Settings and records the decision in #1353.

## 公開手順（日本語）

mergeだけでは公開されません。PRでは検証のみを行い、公開にはmainからの
手動実行と `github-pages` environmentでの人間の承認が必要です。

1. サイト本体 #1351、公開運用 #1352 のPRをこの順でレビュー・mergeします。
   最新headの独立レビュー、required CI、mainの健全性を確認してください。
2. Settings → Environmentsで `github-pages` を作り、Required reviewersを
   人間の `Eruhitsuji` のみに設定し、デプロイ可能branchを `main` に制限します。
   単独管理者が自分で実行して承認する場合、Prevent self-reviewはオフにします。
   これはPRの独立レビューを省略する許可ではありません。botや承認迂回は使いません。
3. Settings → Pagesの公開元を **GitHub Actions** にします。`main/docs`や
   独自ドメインは設定しません。これらの設定変更はOwner作業です。
4. Actions → Official website Pagesでmainを指定してRun workflowを実行。
   対象commitと成果物を確認し、待機中のenvironment deploymentを承認します。
5. 公開後は #1353 にrun URL・commit・承認者・時刻と、日英ページ・404・
   モバイル/キーボード等の実確認を記録します。その後に公式サイトリンクを追加します。

environmentが未保護、reviewerが不適切、API確認に失敗、またはmain以外の場合は
公開を拒否します。workflow自身はPages/environmentを作成・変更しません。
実行中に保護設定を変更しないでください。秘密情報やPATの追加は不要です。
障害時はジョブログを確認して通常のPRで修正し、承認済みmainを再実行します。
公開内容を戻す場合も、人間がrevert PRを確認・mergeし、同じ承認手順で再公開します。
緊急の非公開化はOwnerがSettingsから実施し、判断を記録します。
