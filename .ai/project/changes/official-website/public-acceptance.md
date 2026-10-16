# Public acceptance — #1353

## First publication (observed 2026-10-17 JST)

- Site: https://eruhitsuji.github.io/lifetxt/
- Main commit: `a64e38b373bc95f616babc3b3149a4b038807b8e`.
- Run: https://github.com/Eruhitsuji/lifetxt/actions/runs/38977955823
  (`workflow_dispatch`, main, build and deploy success).
- Approval: [run approvals API](https://api.github.com/repos/Eruhitsuji/lifetxt/actions/runs/38977955823/approvals)
  reports `Eruhitsuji`, `state: approved`, environment `github-pages`.
  This response does not expose an exact approval timestamp; do not invent it.
- [Deploy job](https://github.com/Eruhitsuji/lifetxt/actions/runs/38977955823/job/117231899001)
  started at 2026-10-16 22:49:29 UTC, created the deployment at 22:49:33,
  reported success at **22:49:39 UTC (2026-10-17 07:49:39 JST)**,
  and output the site URL. Artifact ID: `12080001192`.
- Run start: 22:48:55 UTC; completion/update: 22:49:41 UTC.
  Approval occurred before the deploy job started; its precise time is unverified.

## Live HTTP checks

`live-http-20261017.json` retains URLs, response status, byte length and SHA-256
at the recorded UTC observation time. These are checks of the **published
Japanese-root commit above**, not proof of deployment of the English-root PR.
All 22 successful artifact bodies matched a fresh build of that exact commit.

| Surface | Actual result |
| --- | --- |
| Root + six pages each in `/ja/` and `/en/` | All HTTP 200 |
| `/404.html` | HTTP 200, noindex recovery document |
| `/not-found/nested/1353` | HTTP 404, body identical to recovery document |
| Three canonical SVGs, stylesheet, example | All HTTP 200, exact deployed build bytes |
| robots.txt, sitemap.xml, .nojekyll | All HTTP 200 |
| Canonical, hreflang, x-default, sitemap, local fragments/links | No errors using checker from deployed commit |
| Repository, docs (both languages), getting-started, Releases | 18 distinct external destinations, all GET HTTP 200 |

Reproduce HTTP requests with `curl --fail-with-body --location URL` for each
recorded URL (omit `--fail-with-body` when deliberately checking the unknown
404), and inspect status/body. Build/check the deployed ref to compare historical
metadata. The new checker intentionally expects English root and English deep
`x-default`, so it must be used against the new artifact after publication.

Every ordinary page has direct footer links to GitHub, its language's beginner
guide, technical docs and Releases (one click). No new app/API is advertised.

## Browser and accessibility evidence

- Owner's [manual report](https://github.com/Eruhitsuji/lifetxt/issues/1353#issuecomment-6226201180):
  root, Japanese, English, docs/download links and smartphone display normal.
  The report does not identify a device/browser version or prove screen-reader,
  keyboard or 200% zoom acceptance.
- Cloud Chromium live DOM/layout: Japanese root and `/en/` at 1363 CSS pixels;
  main/regions/headings/navigation present, logo loaded, no horizontal overflow.
  Actual English language-switch click reached `/en/` and English heading/copy.
- Keyboard: Shift+Tab from brand reaches the skip link; it is visible at top
  16px with computed 3px solid teal focus outline. Enter focuses `main` and
  navigates to `#main`.
- All generated image elements have alt attributes. The logo's empty alt is
  intentional: the surrounding brand link already supplies the name `lifetxt`.
- Contrast calculated with WCAG relative luminance from the deployed CSS:
  ink/paper 12.29:1, muted/paper 6.17:1, teal/paper 6.38:1,
  white/teal 6.63:1, muted/white 6.41:1, sample/ink 11.60:1,
  file-label/ink 9.64:1, ink/note 11.43:1. These text pairs exceed 4.5:1;
  this is not a claim of full WCAG conformance or logo contrast certification.
- Screenshot capture timed out; no screenshot visual pass is claimed. Local
  Playwright browser installation also failed (download was not a usable ZIP).
  These limitations do not affect the separate successful live HTTP/DOM checks.

## English-root source change (not yet deployed)

Root now renders English at first load (`lang=en`, English copy, English CTAs),
with an explicit Japanese switch. `/ja/` and `/en/` stay available; language
switches retain page identity. Each page retains its canonical URL and sitemap
entry; homepage x-default points to root and deep x-default to `/en/<page>.html`.
OG URL/copy are generated from the same selected language/base. No redirects,
IP/browser-language detection, storage, scripts or dependencies were added.
`website/README.md` describes the final source behavior. The sole canonical
repository README is `readme.md`; no `README_ja.md` exists. Its bilingual live-site
links were added only after successful public HTTP checks.

Developer verification: 31 supported-runtime/site/Pages-guard/traceability/package
tests pass; new tests cover actual English heading, navigation/switches,
canonical/OG and wrong-root/localized-language detection. Build/check validates
14 HTML files and nested/future bases; synthetic sample (4 records), baseline
sample (10 records), Ruff lint/format, approved mypy boundary and diff checks pass.
Full runtime suite and standard evaluation were not rerun for this static-only
change; no runtime or standard is modified. Required PR CI remains separate.

## Remaining acceptance and Owner actions

- [ ] Review the latest PR commit independently and confirm required CI.
- [ ] Merge, then dispatch and approve reviewed main with the existing protected
  Pages workflow. Merge alone does not publish the new English root.
- [ ] Recheck public English root/SEO after that deployment; record new run/commit.
- [ ] Verify actual desktop/mobile rendering, 200% zoom, screen reader reading
  order/links, and Safari/additional browser. Record device/OS/browser/version,
  pass/fail, date and URLs. Existing smartphone report remains valid for its scope.
- [ ] Owner sets repository About → Website to
  `https://eruhitsuji.github.io/lifetxt/` and records completion. This PR does not
  modify live repository metadata; its exact proposed value is reviewable here.
- [ ] Update #1350 and close #1353 only after its remaining acceptance is met.

For manual verification: open root, switch to 日本語, open Features/できること and
switch back; confirm same page. Tab through the page and use the skip link.
Set browser zoom to 200% and confirm all text/actions remain usable. With a
screen reader, inspect main/navigation/headings and ensure the brand is read
once. Test an unknown nested URL and both recovery links.

## Rollback readiness / security review

Existing `website/README.md` runbook is unchanged in authority: Owner reviews a
revert PR, verifies CI, merges and separately dispatches/approves reverted main.
The initial deployment above is a known-good reference, not permission to deploy
an arbitrary old branch. Emergency unpublishing remains an Owner Settings action.
No rollback/deployment/Settings action was executed by this task.

Self-review inspected the generator, checker, test diff and published content:
HTML escaping, relative/base URL boundaries, no-script/no-form/no-telemetry
checks and source/output separation are preserved. No workflow permission,
package dependency, runtime, release or managed-standard changes. Self-review
does not satisfy independent review. Browser-local checking is separately tracked
in #1356 (investigation before a Feature PR); #1353 does not wait for that feature.
