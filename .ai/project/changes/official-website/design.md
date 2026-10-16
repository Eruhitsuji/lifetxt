# Design

Static Python-standard-library generator and JSON copy, without a JS bundle or new dependency. Source and output are separate; existing output is refused, never deleted. Only named public assets are copied. Escaped content is rendered into six equivalent pages per language. Root is Japanese with an explicit English link. The 404 uses the configured base path to recover at unknown request depth. Brand SVG geometry remains unchanged. CSS uses system fonts and high-contrast dark teal for text/controls, preserves the original brand asset colors, and keeps visible keyboard focus.

Existing docs and Releases remain authoritative; no hard-coded current version or unverified package channel. Synthetic examples are parser-checked. No record entry, API, JS, analytics, third-party font or cookie is introduced. Offline link validation proves repository paths and local artifacts, not the future external HTTP availability.

PR #1351 task branch targets main. Pages operations have their own #1352 branch/PR including the first branch commits; merge site first, then recheck the second diff. Live settings/publication and promotion remain #1353 follow-up gates.

## Publication boundary (#1352)

The workflow has pull_request validation and workflow_dispatch only. Build/check happens with contents read and nonpersisted credentials; PRs do not upload Pages artifacts. Only official-repository main dispatch can upload/deploy. The deploy job needs build, uses github-pages protection, pages write and OIDC only, and never checks out project source. The public environment GET is checked before upload and again in the deploy job, with bounded size/timeout and no PAT; it requires the sole reviewer to be the human Owner. Missing/API-denied/malformed settings fail closed. Native environment approval remains the actual enforcement boundary. Admin changes during flight or intentional administrative bypass are not authorized. Owner Settings steps and run/commit approvals are explicit in website/README.md.

Direct Actions are SHA pinned after reading the official Pages/Actions guidance and resolving action tags. configure-pages is unnecessary for this fixed static generator, so no action can implicitly enable Pages. A dedicated concurrency group serializes manual main publication; PRs use separate groups. Revert and publication remain separate human decisions.
