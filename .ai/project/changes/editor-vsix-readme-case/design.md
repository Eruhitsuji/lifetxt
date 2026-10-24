# VSIX README path correction

Run 40081884896 packaged the VSIX successfully with pinned vsce 3.7.1. It stores the source README.md as extension/readme.md. The validator and its synthetic fixture incorrectly required extension/README.md. Require the actual lowercase path and read the same bytes for immutable documentation provenance. Keep all other archive paths exact and retain case-fold collision rejection in checked_archive. No general case-insensitive inventory conversion, dependency upgrade, or workflow change.

Reuse cap-editor-language-support. Bug / High / S; complexity 4/10 (scope 1, dependency 0, uncertainty 0, tests 1, release risk 2). Owner Eruhitsuji, executor ChatGPT. Phase: maintenance, developer verification, independent review, integration. Review correctness, archive ambiguity/provenance, compatibility and scope; test actual normalized packaging plus missing, collision and tampered content.

Source origin/main 381e77a9770ccd89830f50b4d9f2c807f6e7fca6; branch fix/editor-vsix-readme-case; final PR main. Shared validator ownership: this executor until Owner review, no parallel writes. Roll back by revert PR and withhold publication; new main preflight remains required.
