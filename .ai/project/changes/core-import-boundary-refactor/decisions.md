# Decisions

## 2026-10-03 — Boundary shape

The package root is reduced to the stable model/parser/serializer exports.
Embedding consumers use `lifetxt.core`; CLI dispatch explicitly invokes the
legacy compatibility bootstrap. This preserves existing integration behavior
without putting release, Web, Remote, or workspace-related installers on the
Core import path.

The design is platform-neutral and does not add Cloudflare-specific logic.
Public Utility API implementation and deployment remain out of scope.
