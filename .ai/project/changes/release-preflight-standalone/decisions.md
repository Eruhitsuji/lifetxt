# Decisions

- #1309 architecture approved; #1322/#1323 prerequisites merged before work.
- Refined #1317 to a new read-only reusable producer; no old workflow/spec edits.
- Reuse shared context/source and proof helpers rather than duplicate their
  authority or candidate-version validation.
- Keep target-named artifacts instead of treating matrix outputs as an inventory.
- Isolate frozen smoke workspaces and configuration homes to protect user state.
- Independent implementation/integration reviews and human merge remain pending.
