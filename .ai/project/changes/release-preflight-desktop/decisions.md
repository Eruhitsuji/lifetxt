# Decisions

- Approved #1309 architecture; #1322/#1323/#1324 merged before implementation.
- Refined write scope and assurance on #1318. Existing packaging helpers/specs
  remain unchanged; generated source copy isolates version/build mutations.
- Use internal installer aliases plus sealed original-name mapping rather than
  rename public assets or broaden the common proof schema. Consumer handoff is
  recorded on canonical/aggregate/publication-verification Issues.
- Local Rust/Cargo/WebKit are unavailable; verify real Linux runtime stage but
  retain native installer builds and all GUI coverage as explicit unverified work.
- Independent implementation/integration reviews and human merge remain pending.
