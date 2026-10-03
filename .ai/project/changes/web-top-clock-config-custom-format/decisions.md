# Decisions

- M justified: public API bug, restart contract and user-added timezone/format requirements form one acceptance path. Splitting would leave the public path inconsistent; focused tests separate validation, API reload and rendering.
- Standard assurance, complexity 5/10. Owner/reviewer: Eruhitsuji; executor: Codex. Lifecycle: implementation and verification, then independent review.
- Default main timezone follows the explicit additional requirement; browser-local is available to preserve prior viewer-local output.
- Custom date tokens are bounded and never evaluated. Brackets escape literal text. Existing four time formats remain accepted.
- Configuration reload is limited to allowlisted presentation settings; no authorization or write-target reload is introduced.
