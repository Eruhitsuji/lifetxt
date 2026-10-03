# Decisions

## 2026-10-03 — Feasibility outcome

The temporary Cloudflare Python Worker PoC is classified **GO WITH
CORE-IMPORT REFACTOR**. The authoritative Core semantics and native stateless
adapter ran on Python/Pyodide 3.14.2, including parsing/check, conversion,
quick-input resolution, and priority classification. Package-root import is
successful but eagerly exposes a broad module graph and produces a large
bundle; this must be addressed by a platform-neutral follow-up before a
production Public Utility API is designed.

The follow-up is tracked in GitHub Issue #1055. No Cloudflare-specific import
hack is approved.

## Scope boundary

This change remains an investigation PoC. It does not implement the Public
Utility API, production deployment, custom domains, storage, authentication,
Remote integration, or deployment automation. The temporary Worker remains
until a separate human cleanup decision.

## Review and approval boundary

External Cloudflare deployment was explicitly approved for the named temporary
Worker only. Merge, PR approval, production deployment, and Worker deletion
remain human-controlled decisions.
