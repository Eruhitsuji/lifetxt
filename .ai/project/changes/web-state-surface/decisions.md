# Decisions

- 2026-10-23: User requested #1379 after merging #1381. Verify dependency merge
  at fca6573, record Ready assessment on #1379, then move to In progress.
- Feature / Standard / S / complexity 6, adaptive-default / Kanban / W-model.
  Branch feature/1379-state-ui from origin/main; one final PR into main.
- Register cap-web-state-surface / req-web-state-surface-v1 as the dedicated
  surface, reusing existing Status authoring/Core/API and revision contracts.
- Package registration and this non-trivial-change evidence package support
  the defined feature; no new runtime dependency or write/security boundary.
- Native viewport/AX tests are conditional on browser availability. Local
  Chromium and headless-shell downloads returned invalid/truncated archives;
  do not describe these unavailable checks as passed. Keep executable probes
  for browser-equipped CI/hosts and report physical-device limitations.
- Independent final-head review and merge belong to the human maintainer.
  Implementer self-review cannot supply independent approval.
- Connect the new State native probes to the existing provisioned real-Chromium
  CI lane and retain synthetic evidence. This verification-only scope refinement
  is recorded on #1379; no new jobs, permissions, triggers or dependencies.
