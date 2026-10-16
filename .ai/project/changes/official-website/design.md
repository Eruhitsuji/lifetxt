# Design

Static Python-standard-library generator and JSON copy, without a JS bundle or new dependency. Source and output are separate; existing output is refused, never deleted. Only named public assets are copied. Escaped content is rendered into six equivalent pages per language. Root is Japanese with an explicit English link. The 404 uses the configured base path to recover at unknown request depth. Brand SVG geometry remains unchanged. CSS uses system fonts and high-contrast dark teal for text/controls, preserves the original brand asset colors, and keeps visible keyboard focus.

Existing docs and Releases remain authoritative; no hard-coded current version or unverified package channel. Synthetic examples are parser-checked. No record entry, API, JS, analytics, third-party font or cookie is introduced. Offline link validation proves repository paths and local artifacts, not the future external HTTP availability.

PR #1351 task branch targets main. Pages operations have their own #1352 branch/PR including the first branch commits; merge site first, then recheck the second diff. Live settings/publication and promotion remain #1353 follow-up gates.
