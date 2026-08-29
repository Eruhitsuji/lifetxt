---
name: release-distribution-runbook
description: Cut a lifetxt release across every distribution channel (PyPI, GHCR, GitHub Release, standalone binaries, desktop installers, Homebrew Tap, winget/Scoop, conda-forge) and diagnose channel failures without guessing.
---

# Release Distribution Runbook Skill

Packages the operational sequence for running a `cap-distribution-channels`
release (see `.ai/project/CAPABILITIES.yml`) end to end: which workflows to
trigger, in what order, how to verify each channel independently instead of
trusting "workflow succeeded", and how to tell a real bug apart from an
ordering issue or a human-only account problem when something fails.

This is a runbook, not a bug list. It does not encode workarounds for any
specific defect — those belong in the workflow files themselves once fixed.
It encodes the *procedure and the diagnostic habits*, so a future release
does not have to re-derive them from scratch.

## When to use this skill

- Cutting a new lifetxt release (version bump already merged, about to push
  or having just pushed a `vX.Y.Z` tag).
- A release-automation workflow run failed or is behaving unexpectedly.
- Verifying that a past release actually reached every channel it claims to.

## The channel graph

```text
git tag vX.Y.Z pushed
  |
  +--> release.yml            (build wheel/sdist -> PyPI -> GitHub Release)
  +--> docker-publish.yml     (build+smoke-test -> GHCR)
  +--> desktop-installers.yml (build per-OS Tauri installers -> GitHub Release)
  +--> standalone-binaries.yml (build per-OS PyInstaller binaries -> GitHub Release,
                                 combined SHA256SUMS over all 5 platforms)
       |
       | ONLY after this one's github-release job has completed and its
       | SHA256SUMS is visible on the release -- see "The release: published
       | trap" below for why these three do not fire on their own:
       v
  +--> homebrew-tap.yml       (needs 4 non-Windows binary checksums; pushes
  |                            Formula/lifetxt.rb to Eruhitsuji/homebrew-tap)
  +--> package-manifests.yml  (needs the Windows binary checksum; generates
  |                            winget+Scoop manifests as a build artifact)
  +--> conda-recipe.yml       (needs only the published PyPI sdist, so it can
                               run any time after release.yml's PyPI publish)
```

## Procedure

### 1. Trigger the four primary workflows

These are `push: tags: v*.*.*` triggered, so a tag push fires all four
automatically. To re-run any of them against an existing tag (after a fix,
or because one failed), use `workflow_dispatch`:

```
gh workflow run release.yml --repo Eruhitsuji/lifetxt -f tag=vX.Y.Z -f publish_pypi=true -f publish_github_release=true
gh workflow run docker-publish.yml --repo Eruhitsuji/lifetxt -f tag=vX.Y.Z -f push=true
gh workflow run desktop-installers.yml --repo Eruhitsuji/lifetxt -f tag=vX.Y.Z -f publish_github_release=true
gh workflow run standalone-binaries.yml --repo Eruhitsuji/lifetxt -f tag=vX.Y.Z -f publish_github_release=true
```

Monitor with a bounded background wait, never a manual polling loop:

```
until s=$(gh run view <run-id> --repo Eruhitsuji/lifetxt --json status,conclusion --jq '.status + "/" + (.conclusion // "")'); [[ "$s" == completed* ]]; do sleep 20; done
echo "$s"
```

### 2. Verify each channel independently

Do not treat "workflow run: success" as proof a channel actually received
the release. Check the channel itself:

- **PyPI**: `curl -s https://pypi.org/pypi/lifetxt/json | jq '.info.version, .releases | keys'`
- **GHCR**: the `docker-publish.yml` run succeeding is sufficient (it pushes
  and the smoke tests already exercise the pulled image).
- **GitHub Release**: `gh release view vX.Y.Z --repo Eruhitsuji/lifetxt` and
  confirm every expected asset name is listed (wheel, sdist, 5 standalone
  binaries, desktop installer files per OS, `SHA256SUMS`, `sbom.cdx.json`,
  `provenance.json`).

### 3. The `release: published` trap

`homebrew-tap.yml`, `package-manifests.yml`, and `conda-recipe.yml` all
trigger on `release: types: [published]`. GitHub Actions does **not** fire
that event for a release created by a workflow run authenticated with the
default `GITHUB_TOKEN` (documented anti-recursion behavior) -- so these
three never start on their own after `release.yml`'s `gh release create`.
They must always be triggered explicitly:

```
gh workflow run homebrew-tap.yml --repo Eruhitsuji/lifetxt -f tag=vX.Y.Z
gh workflow run package-manifests.yml --repo Eruhitsuji/lifetxt -f tag=vX.Y.Z
gh workflow run conda-recipe.yml --repo Eruhitsuji/lifetxt -f tag=vX.Y.Z
```

Do this only *after* confirming `standalone-binaries.yml`'s `github-release`
job has actually completed (step 1) -- both `homebrew-tap.yml` and
`package-manifests.yml` read the combined `SHA256SUMS` and fail with a
self-diagnosing message ("... not found in this release's SHA256SUMS -- has
standalone-binaries.yml run for this tag yet?") if triggered too early. That
specific failure is expected/informative when it happens *before*
standalone-binaries.yml finishes; if it happens *after*, do not assume the
same explanation -- inspect the actual `SHA256SUMS` bytes (step 5).

### 4. Triaging a workflow failure

Read the actual log before hypothesizing:

```
gh run view <run-id> --repo Eruhitsuji/lifetxt --log-failed
```

Classify the failure before acting:

- **A real bug in this repository's workflow/script code**: fix it following
  this project's normal process -- new branch off `main`, fix, add a
  regression test that reproduces the defect (not just asserts the fix),
  `ruff format`/`ruff check`, open a GitHub Issue describing the live
  evidence, open a PR referencing it, add a `.ai/project/TRACEABILITY.yml`
  entry (`pull_request: null` at first, filled in with the real PR URL once
  it exists, in a follow-up commit), wait for CI, merge, sync local `main`,
  re-trigger the fixed workflow. See PRs #580/#582/#585/#587 in this
  project's history for four worked examples of this exact cycle.
- **An ordering/dependency issue** (e.g. the `release: published` trap
  above, or a downstream workflow racing ahead of an upstream one): re-run
  after the dependency actually completes, do not "fix" working code.
- **A human-only account/credential problem**: recognize this quickly and
  stop trying to fix it via code. A GitHub PAT permission error
  (`remote: Permission ... denied ..., 403`) cannot be fixed by re-running
  the workflow or editing repository files -- it needs the token's actual
  scope corrected in GitHub's own settings UI by the account owner. Give
  precise remediation (exact permission name, e.g. "Contents: Read and
  write", not just "check the token"), and re-verify immediately after the
  human reports a fix rather than assuming it worked.

### 5. Two diagnostic habits that saved real time

- **A runner label queued far longer than every sibling job in the same
  matrix** (other jobs start within seconds; one sits in `queued` for
  10+ minutes with no `started_at` progress) is not "the runner pool is
  busy today" -- it is a strong signal the `runs-on:` label has been
  retired by GitHub. Confirm via GitHub's own changelog before waiting
  longer; a retired label queues forever, it never eventually gets a
  runner. (Concrete precedent: `macos-13` was retired 2025-12-04; the
  replacement Intel-macOS label is `macos-15-intel`.)
- **When a downstream consumer's exact-match logic mysteriously fails
  against a file that visibly "looks right"**, do not trust `cat`/`od -c`
  glances -- download the actual asset and check for CRLF explicitly
  (`grep -c $'\r' FILE`, or `cat -A FILE` and look for `^M$` instead of a
  bare `$` at line end). A file assembled by concatenating outputs from
  jobs on different operating systems (e.g. `cat *.sha256 > SHA256SUMS`
  across a Windows job and several Linux/macOS jobs) can have one line's
  line-ending silently differ from the rest, because a plain text-mode
  `open(path, 'w')` in Python (or most languages) translates `\n` to the
  host platform's newline convention on write. Fix with an explicit
  `newline='\n'` (or equivalent) at the point the file is written, not by
  patching the downstream regex to tolerate `\r`.

### 6. Non-blocking findings

If you find a real defect that does not block the current release (e.g. two
workflows both uploading a release asset with the same name via `--clobber`,
so whichever runs last silently wins instead of merging), file it as its
own GitHub Issue and move on -- do not let a non-blocking finding stall the
channels that are actually waiting on you. See Issue #583 in this project's
history for a worked example.

## Output

When reporting status to the user, always report per-channel state (which of
PyPI/GHCR/GitHub Release/Homebrew Tap/winget+Scoop/conda-forge actually
succeeded, not just "the workflows ran"), and clearly separate:

- items you fixed and verified,
- items still in progress,
- items that are genuinely blocked on a human action, stated as a concrete
  next step the human can take (not "something is wrong with the token").
