# Source acquisition and delivery

Operations / High, adaptive-default W-model. M score 6: source1/dependency1/
uncertainty1/test2/ops1. The lock, selected licence/patch members, source index,
offline bundle and audit form one cohesive delivery contract. Independent legal/
distribution acceptance and publication remain #1398/#1400. Reuse
cap-official-website; no new product dependency or runtime/parser change.
Source origin/main 368af83e; branch ops/browser-source-delivery; final PR base main.
Owner and final reviewer Eruhitsuji; executor Codex. Separate implementation/
distribution and integration reviews are pending, not self-approved.

source-lock.json pins ten complete source archives plus one upstream core binary
verification input. SHA256, size, source scope, selected regular member hashes
and upstream port SHA512s bind evidence. read_members never extracts or executes
archives. source_probe verifies release identity, recipes, nine CPython patches
and all 567 regular stdlib files. It uses the patch utility only on temporary
data files with validated relative paths, not on installed Python or this repo.
source-provenance.json is reproducible with the opt-in real-cache regression.

Default PoC build is offline and emits source acquisition links plus source lock
and delivery documentation. --source-cache instead copies all ten verified
source archives. The core binary archive is never labelled or copied as source.
All generated source files enter the artifact manifest and fixed audit allowlist.
Partial/extra/changed source payloads, links or metadata fail even if a caller
rewrites manifest hashes. The local checker builder copies sources and points
its existing source/notice link at the static source index. The official
introduction builder/Pages workflow remain unchanged and never bundle this code.

fetch is a separate, explicit maintainer command using fixed HTTPS origins and
prevalidated redirect origins. Downloads have locked size/hash bounds, temporary
staging, no replacement of existing cache files and no user input data. Failed
or changed bytes are rejected; there is no latest/CDN or silent hash update.
Archive validation is O(total bytes processed); memory for SHA256 is streamed on
Python >=3.11 and bounded by the largest locked archive on Python 3.10. Source
bundle work occurs in maintainer tooling, not the interactive browser Worker.

Security: hostile paths, URLs, symlinks, payload changes, missing licences/patches
and false completeness are rejected. Metadata rendering escapes all dynamic
values and the source page has no scripts. Full source archives preserve their
own per-file terms and may contain tools/tests not linked in the WASM. Source
presence is not a binary-inclusion or legal-completeness assertion.

Test mapping: fixed-source contract -> negative synthetic archive/cache tests;
recipe/release relationship -> real cache probe; delivery -> real bundle audit;
UI acquisition -> real JA/EN Chromium source-navigation/download smoke; product
regression -> existing PoC/checker/website/workflow suites. Source evidence is
not treated as a substitute for independent distribution review.

Rollback is a human-reviewed revert of this PR; no live product was deployed.
Retain prior reviewed runtime manifest/source lock for any future upgrade review.
