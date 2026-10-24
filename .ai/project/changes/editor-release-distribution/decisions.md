# Decisions and residual risks

- 2026-10-24 Owner: approve the #1389 13+1 design and execute 3 right-sized tasks, then propose a single main PR. Explicitly **not** an authorization to tag, publish, deploy or merge.
- Prefer reusing `release.yml` unmodified to preserve the protected `pypi` approval environment and audited release state.
- Keep the existing 13 target contracts intact. New mandatory editor producer fails before approval if missing or altered.
- Use `@vscode/vsce` for actual installable VSIX rather than a hand-made ZIP named VSIX. Include the optional runtime Node client; LSP must remain Python opt-in.
- Keep extension SemVer independent from 3/4-part lifetxt release version; enforce equality of embedded provenance with sealed candidate.
- Risks: builder needs npm registry access during non-public preflight; optional package resolution and real VSIX installability must be verified by CI and Windows acceptance. No claim of successful test/Release until the execution evidence exists.
- Independent implementation/integration reviews and Owner risk acceptance are pending; no auto-approval.
