# Decisions and boundaries

- Owner's 2026-10-17 explicit autonomous implementation request supersedes #1348's
  original creation-only scope. Child issues define the concrete implementation.
- Use local opt-in, read-only Core-backed server and VS Code/Neovim adapters.
- No disk discovery or extra-editor release is inferred from the Epic's candidate
  phases. Zed/JetBrains are conditional investigation, not promised integrations.
- `ids.key` is explicit via --id-key. Extension-only settings are authoritative in
  its manifest; Core registry/config explain/migrations do not apply.
- Independent human review and High risk acceptance remain pending on final head.
  Self-review is not independent approval. No autonomous merge/publish/deploy.
