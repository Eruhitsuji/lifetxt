# Design

Extend `cap-web-state-surface`, not the Status domain. Reuse Planner's dedicated
manifest route/allowlist/package pattern and canonical life.txt brand icons.
The State identity and start URL are `/state`; `scope` stays `/`, without a
worker, offline cache, background sync, queue, install prompt or new permission.

More gets a normal anchor alongside Planner/Capture, not a workspace-switch
button. The State label remains distinguishable from Status/Team; its Quick
Status suffix reuses the existing EN/JA translation. State already has a small
full-Web return link. Do not crowd the primary actions with extra navigation.

Existing Bearer middleware protects State, its manifest and icons. The root
shell's existing public exemption is unchanged. Standalone browsers may not
share an authenticated proxy/header context: document that limitation instead
of embedding credentials or relaxing auth for installability.

Verification pairs requirements with route/resource tests and the existing
native Chromium CI lane. Expand its probes for safe-area env() overrides,
reachability of tiles/fields/Save/End/footer, native Tab/focus and errors, and
actual server navigation, browser back/reload and API persistence. Emulated
safe areas and an accessibility tree do not demonstrate iOS or screen-reader
acceptance. Keep those gaps in issue #1383, not the closing implementation task.

No runtime CSS/JS, parser, status transition semantics or data format changes.
Shared files are owned by Eruhitsuji; integrate after #1379, one branch/PR into
main. Human final-head review and merge remain required. No data migration;
rollback is a maintainer-approved PR revert.
