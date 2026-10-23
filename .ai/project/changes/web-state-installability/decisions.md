# Decisions

- Reuse rather than duplicate Status APIs and installability infrastructure.
  Existing manifest auth may limit standalone access, but auth is not weakened.
- Register the manifest in `pyproject.toml`: source-only success would not prove
  that installed wheels expose the new route.
- Reuse the existing `Quick Status` translation in the new State link, avoiding
  a JS dictionary change or renaming Status/Team. The invariant app name State
  has its own `lang="en"` span, separate from the translatable description and
  separator; the existing full-page translation audit remains enforced.
- Keep State's existing full-Web footer link; no additional competing controls.
- Extend existing Chromium probes and evidence filenames, without changing CI
  jobs, permissions, dependency installation or triggers.
- A native root-navigation link intentionally changes the assembled HTML hash;
  update that snapshot only after checking the diff is the one new anchor.
- Report actual-device gaps through issue #1383. No assertion that manifest
  delivery or emulated safe areas prove home-screen installation on iOS/Android.
