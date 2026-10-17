# Decisions

- Keep this investigation independent of #1362's notice inventory PR.
- Firefox page creation hits an OS sandbox permission failure; do not work around
  that restriction. WebKit lacks OS libraries; do not modify host libraries here.
- Add reproducible probes and record blocked, not an unsupported compatibility claim.
- Validate the portable runner in existing Chromium with its documented container
  launch flags. This is not Firefox/WebKit/Safari or physical mobile acceptance.
- Latest-head review, merge, OS preparation and publication remain human decisions.
